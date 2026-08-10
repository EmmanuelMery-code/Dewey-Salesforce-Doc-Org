"""
SfFindingsService — Mode B
Pushes DeweyAnalysis__c + DeweyFinding__c + DeweyAnalysisFinding__c.

Finding lifecycle:
  - DeweyFinding__c is a unique entity per (OrgAlias, RuleId, ComponentName).
  - On each run, existing non-resolved findings are REUSED via junction records
    (DeweyAnalysisFinding__c) instead of duplicated.
  - Findings no longer detected (and not already Résolu/Accepté) are set to "Disparu".
  - A new finding is created only when truly new, or when a previously Résolu finding
    reappears.

Persistence for finding deduplication/lifecycle and for DeweyPosture__c live in the
sibling ``sf_findings_service_dedup`` and ``sf_findings_service_posture`` modules
(mixed in below) to keep this file under the repo's 500-line convention.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.sf_findings_service_dedup import _FindingsDedupMixin
from src.core.sf_findings_service_helpers import (
    _ANSI_RE,
    _API_VERSION,
    _compute_score_max,
)
from src.core.sf_findings_service_posture import _PostureMixin


class SfFindingsService(_FindingsDedupMixin, _PostureMixin):
    """Pushes assessment results to a Salesforce org."""

    def __init__(self, org_alias: str) -> None:
        self.org_alias = org_alias

    # ── Public API ─────────────────────────────────────────────────────────────

    def push(
        self,
        result,                     # AssessmentResult
        source: str,
        source_branch: str = "",
        scope: str = "all",
        source_root=None,           # Path | None — git root for relative file paths
        project: str = "",          # Stable project key for finding deduplication
        posture_signal_map: dict[str, str] | None = None,  # {rule_id: signal}
        version: str = "",
    ) -> tuple[str, str | None]:
        """
        1. Fetch all active DeweyFinding__c for this source (deduplicate by key).
        2. Create DeweyAnalysis__c.
        3. For each finding in current run:
             - Existing non-terminal → create DeweyAnalysisFinding__c only (reuse).
             - New or was Résolu/Accepté → create DeweyFinding__c + junction.
        4. Mark findings absent from this run (non-terminal) as "Disparu".
        Returns (analysis_id, delta_summary).
        """
        report = result.report
        snapshot = result.snapshot
        counts = report.severity_counts()
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000")
        adoption_stats = getattr(snapshot, "adoption_stats", None)

        # ── Step 1 : load all existing findings for this project ─────────────
        # Returns dict: "RuleId::ComponentName" -> {"Id": str, "Status__c": str}
        # Uses project key (stable across snapshots) for deduplication.
        dedup_key = project or source
        existing = self._fetch_active_findings(dedup_key)

        # ── Step 2 : create DeweyAnalysis__c ──────────────────────────────────
        metrics = snapshot.metrics
        analysis_payload: dict[str, Any] = {
            "Source__c": source[:255] if source else "",
            "Project__c": dedup_key[:80] if dedup_key else "",
            "AnalysisDate__c": now_iso,
            "Scope__c": scope,
            "ScoreGlobal__c": metrics.score if hasattr(metrics, "score") else None,
            "ApexCount__c": metrics.apex_classes + metrics.apex_triggers,
            "FlowCount__c": metrics.flows,
            "LwcCount__c": metrics.lwc_count,
            "FindingCritical__c": counts.get("Critical", 0),
            "FindingMajor__c": counts.get("Major", 0),
            "FindingMinor__c": counts.get("Minor", 0),
            "FindingInfo__c": counts.get("Info", 0),
            "Status__c": "Completed",
            "ScoreAdopt__c": round(adoption_stats.percent_adoption) if adoption_stats else None,
            "ScoreAdapt__c": round(adoption_stats.percent_adaptation) if adoption_stats else None,
            "ScoreMax__c": _compute_score_max(metrics),
        }
        test_coverage = getattr(metrics, "test_coverage", None)
        if test_coverage is not None:
            analysis_payload["TestCoveragePct__c"] = round(test_coverage, 1)
        if source_branch:
            analysis_payload["SourceBranch__c"] = source_branch[:255]
        if version:
            analysis_payload["Version__c"] = version[:50]
        analysis_payload = {k: v for k, v in analysis_payload.items() if v is not None}

        analysis_id = self._create_record("DeweyAnalysis__c", analysis_payload)

        # ── Step 3 : process findings ──────────────────────────────────────────
        current_keys, n_new = self._process_findings(
            report, analysis_id, source, existing, now_iso, source_root
        )

        # ── Step 4 : mark Disparu ─────────────────────────────────────────────
        n_disparu = self._mark_disparu(existing, current_keys, analysis_id)

        # ── Step 5 : push DeweyPosture__c records ────────────────────────────
        if adoption_stats:
            self._push_posture(analysis_id, adoption_stats, snapshot=snapshot, source=dedup_key)
        if posture_signal_map:
            self._push_component_posture(analysis_id, report, posture_signal_map, source=dedup_key)

        # ── Step 6 : create DeweyDelta__c ──────────────────────────────────────
        prev_id = self._fetch_previous_analysis_id(dedup_key, exclude_id=analysis_id)
        delta_summary: str | None = None
        if prev_id:
            prev_counts = self._fetch_previous_counts(prev_id)
            curr_max = analysis_payload.get("ScoreMax__c") or 0
            curr_score = analysis_payload.get("ScoreGlobal__c") or 0
            curr_ratio = round(curr_score / curr_max * 100, 1) if curr_max else 0.0
            ratio_delta = round(curr_ratio - prev_counts.get("ScoreRatio__c", 0.0), 1)
            crit_delta = counts.get("Critical", 0) - prev_counts.get("FindingCritical__c", 0)
            maj_delta = counts.get("Major", 0) - prev_counts.get("FindingMajor__c", 0)

            sign = lambda n: f"+{n}" if n > 0 else str(n)
            delta_summary = (
                f"ratio {sign(ratio_delta)}%, "
                f"new {n_new}, disparu {n_disparu}, "
                f"critical {sign(crit_delta)}, major {sign(maj_delta)}"
            )
            patch_payload: dict[str, Any] = {
                "PreviousAnalysis__c": prev_id,
                "ScoreDelta__c": ratio_delta,
                "NewFindings__c": n_new,
                "DisparuFindings__c": n_disparu,
                "CriticalDelta__c": crit_delta,
                "MajorDelta__c": maj_delta,
            }
            prev_coverage = prev_counts.get("TestCoveragePct__c")
            if test_coverage is not None and prev_coverage is not None:
                coverage_delta = round(test_coverage - prev_coverage, 1)
                patch_payload["CoverageDelta__c"] = coverage_delta
                delta_summary += f", coverage {sign(coverage_delta)}%"
            self._rest("PATCH", f"/sobjects/DeweyAnalysis__c/{analysis_id}", patch_payload)

        return analysis_id, delta_summary

    # ── REST helpers ───────────────────────────────────────────────────────────

    def _rest(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
    ) -> Any:
        """Calls Salesforce REST API via sf api request rest."""
        cmd = [
            "sf", "api", "request", "rest",
            "--method", method,
            "-o", self.org_alias,
            f"/services/data/{_API_VERSION}{path}",
        ]
        if payload is not None:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as tmp:
                json.dump(payload, tmp)
                tmp_path = tmp.name
            cmd += ["--body", f"@{tmp_path}"]
        else:
            tmp_path = None

        try:
            out = subprocess.run(cmd, capture_output=True, text=True)
            if out.returncode == 0:
                return json.loads(out.stdout) if out.stdout.strip() else {}
            combined = out.stdout + "\n" + out.stderr
            clean = _ANSI_RE.sub("", combined)
            start = next(
                (i for i, c in enumerate(clean) if c in ("{", "[")), None
            )
            detail = clean[start:].strip()[:600] if start is not None else clean.strip()[:600]
            raise RuntimeError(
                f"Salesforce REST {method} {path} → {detail}"
            )
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

    def _create_record(self, sobject: str, payload: dict) -> str:
        """Creates a single SObject record and returns its new Id."""
        result = self._rest("POST", f"/sobjects/{sobject}/", payload)
        if not result.get("success"):
            raise RuntimeError(f"Failed to create {sobject}: {result}")
        return result["id"]

    # ── Static helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _key(rule_id: str, component_name: str) -> str:
        return f"{rule_id}::{component_name}"

    @staticmethod
    def _finding_key(finding) -> str:
        return f"{finding.rule.id}::{finding.target_name or ''}"
