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
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Maps Dewey target_kind values → ComponentType__c picklist
_COMPONENT_TYPE_MAP: dict[str, str] = {
    "apex_class":       "Apex",
    "apexclass":        "Apex",
    "apex_trigger":     "Apex",
    "apextrigger":      "Apex",
    "flow":             "Flow",
    "lwc":              "LWC",
    "lwccomponent":     "LWC",
    "aura":             "LWC",
    "auracomponent":    "LWC",
    "object":           "Object",
    "customobject":     "Object",
    "validationrule":   "Object",
    "duplicaterule":    "Object",
    "profile":          "Security",
    "permissionset":    "Security",
    "permissionsetgroup": "Security",
    "securityartifact": "Security",
    "omni_script":      "OmniStudio",
    "omniscript":       "OmniStudio",
    "dataraptorextract": "OmniStudio",
    "dataraptortransform": "OmniStudio",
    "data_transform":   "OmniStudio",
    "integrationprocedure": "OmniStudio",
    "flexcard":         "OmniStudio",
}

# Statuses that prevent a finding from being reused (must be recreated if re-detected)
_TERMINAL_STATUSES = {"Résolu", "Accepté"}

# Statuses that indicate the finding is still active (not yet addressed)
_ACTIVE_STATUSES = {"Découvert", "Pris en charge", "Disparu"}

# Maximum scoring weight in DEFAULT_SCORING_WEIGHTS (custom_objects = 8).
# Used to compute ScoreMax: total_artifacts × _SCORE_MAX_WEIGHT.
_SCORE_MAX_WEIGHT = 8

# Ordered posture levels — lower index = closer to OOTB (better for a Salesforce org)
_LEVEL_ORDER: dict[str, int] = {
    "Adopt (OOTB)": 0,
    "Adopt declaratif": 1,
    "Adapt (declaratif)": 2,
    "Adapt (code)": 3,
}


def _map_component_type(target_kind: str) -> str:
    return _COMPONENT_TYPE_MAP.get((target_kind or "").lower(), "Other")


def _compute_score_max(metrics) -> int:
    """
    Theoretical maximum score for this org's artifact volume.
    = total artifact count × max scoring weight (8 = custom_objects).
    Used as denominator for ScoreRatio__c formula field.
    """
    total = (
        metrics.apex_classes + metrics.apex_triggers
        + metrics.flows
        + metrics.custom_objects + metrics.custom_fields
        + metrics.record_types + metrics.validation_rules
        + metrics.layouts + metrics.custom_tabs + metrics.custom_apps
        + metrics.omni_scripts + metrics.omni_integration_procedures
        + metrics.omni_ui_cards + metrics.omni_data_transforms
        + metrics.bre_decision_matrices + metrics.bre_expression_sets
        + metrics.agents + metrics.gen_ai_prompts + metrics.einstein_predictions
        + metrics.lwc_count + metrics.flexipage_count
    )
    return total * _SCORE_MAX_WEIGHT


_API_VERSION = "v66.0"
_BATCH_SIZE = 200


class SfFindingsService:
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
            self._rest("PATCH", f"/sobjects/DeweyAnalysis__c/{analysis_id}", {
                "PreviousAnalysis__c": prev_id,
                "ScoreDelta__c": ratio_delta,
                "NewFindings__c": n_new,
                "DisparuFindings__c": n_disparu,
                "CriticalDelta__c": crit_delta,
                "MajorDelta__c": maj_delta,
            })

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

    # ── Finding deduplication ──────────────────────────────────────────────────

    def _fetch_active_findings(
        self, project: str
    ) -> dict[str, dict]:
        """
        Returns all DeweyFinding__c for this project (regardless of status).
        Key = "RuleId::ComponentName", value = {"Id": str, "Status__c": str}.
        Scoped via junction: findings linked to any analysis with Project__c = project.
        """
        soql = (
            f"SELECT Id, Rule__r.RuleId__c, ComponentName__c, Status__c "
            f"FROM DeweyFinding__c "
            f"WHERE Id IN ("
            f"SELECT DeweyFinding__c FROM DeweyAnalysisFinding__c "
            f"WHERE DeweyAnalysis__r.Project__c = '{project}'"
            f")"
        )
        cmd = ["sf", "data", "query", "--query", soql, "--json", "-o", self.org_alias]
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(out.stdout)
        records = data.get("result", {}).get("records", [])
        return {
            self._key(
                (r.get("Rule__r") or {}).get("RuleId__c", ""),
                r.get("ComponentName__c", ""),
            ): {
                "Id": r["Id"],
                "Status__c": r.get("Status__c", "Découvert"),
            }
            for r in records
        }

    def _process_findings(
        self,
        report,
        analysis_id: str,
        source: str,
        existing: dict[str, dict],
        now_iso: str,
        source_root=None,           # Path | None
    ) -> tuple[set[str], int]:
        """
        For each finding in the current run:
          - If already exists with non-terminal status → create junction only.
          - If new, or previously Résolu/Accepté → create DeweyFinding__c + junction.
        Returns (current_keys, n_new).
        """
        all_findings = list(report.all_findings())
        current_keys: set[str] = set()
        n_new = 0

        # Findings to insert as new DeweyFinding__c records
        new_finding_records: list[tuple[dict, dict]] = []  # (finding_payload, finding_obj)
        # Junction records for existing findings
        junction_reuse: list[dict] = []

        for finding in all_findings:
            key = self._finding_key(finding)
            current_keys.add(key)
            entry = existing.get(key)

            if entry and entry["Status__c"] not in _TERMINAL_STATUSES:
                # Reuse existing finding — create junction only
                junction_reuse.append({
                    "attributes": {"type": "DeweyAnalysisFinding__c"},
                    "DeweyAnalysis__c": analysis_id,
                    "DeweyFinding__c": entry["Id"],
                    "IsNewInRun__c": False,
                })
            else:
                # Create new DeweyFinding__c
                n_new += 1
                rec: dict[str, Any] = {
                    "Rule__r": {"RuleId__c": finding.rule.id},
                    "Severity__c": finding.rule.severity,
                    "ComponentType__c": _map_component_type(finding.target_kind),
                    "ComponentName__c": (finding.target_name or "")[:255],
                    "Message__c": (finding.message or finding.rule.description or "")[:32768],
                    "Remediation__c": (finding.rule.remediation or "")[:32768],
                    "Status__c": "Découvert",
                    "FirstSeenDate__c": now_iso,
                    "DeweyAnalysis__c": analysis_id,
                }
                if finding.source_path:
                    if source_root:
                        try:
                            rel = Path(finding.source_path).relative_to(source_root)
                            rec["FilePath__c"] = str(rel)[:255]
                        except ValueError:
                            rec["FilePath__c"] = str(finding.source_path)[:255]
                    else:
                        rec["FilePath__c"] = str(finding.source_path)[:255]
                if finding.line is not None:
                    rec["LineNumber__c"] = finding.line
                new_finding_records.append((rec, finding))

        # Bulk insert new DeweyFinding__c records
        new_finding_ids: list[str] = []
        for i in range(0, len(new_finding_records), _BATCH_SIZE):
            batch_payloads = [r for r, _ in new_finding_records[i: i + _BATCH_SIZE]]
            batch_with_attrs = [
                {"attributes": {"type": "DeweyFinding__c"}, **p}
                for p in batch_payloads
            ]
            results = self._rest(
                "POST",
                "/composite/sobjects",
                {"allOrNone": False, "records": batch_with_attrs},
            )
            errors = [r for r in results if not r.get("success")]
            if errors:
                raise RuntimeError(
                    f"DeweyFinding__c batch insert errors: {json.dumps(errors[:3])}"
                )
            new_finding_ids.extend(r["id"] for r in results)

        # Build junction records for newly created findings
        junction_new = [
            {
                "attributes": {"type": "DeweyAnalysisFinding__c"},
                "DeweyAnalysis__c": analysis_id,
                "DeweyFinding__c": fid,
                "IsNewInRun__c": True,
            }
            for fid in new_finding_ids
        ]

        # Bulk insert all junction records
        all_junctions = junction_reuse + junction_new
        for i in range(0, len(all_junctions), _BATCH_SIZE):
            batch = all_junctions[i: i + _BATCH_SIZE]
            results = self._rest(
                "POST",
                "/composite/sobjects",
                {"allOrNone": False, "records": batch},
            )
            errors = [r for r in results if not r.get("success")]
            if errors:
                raise RuntimeError(
                    f"DeweyAnalysisFinding__c batch insert errors: {json.dumps(errors[:3])}"
                )

        return current_keys, n_new

    # ── Disparu logic ─────────────────────────────────────────────────────────

    def _mark_disparu(
        self, existing: dict[str, dict], current_keys: set[str], analysis_id: str
    ) -> int:
        """
        Findings that were active (Découvert or Pris en charge) but are no longer
        detected in this run → set Status__c = "Disparu" and create junction records
        with IsDisparuInRun__c = True for component-level delta tracking.
        Returns count of findings marked Disparu.
        """
        disparu_ids = [
            entry["Id"]
            for key, entry in existing.items()
            if key not in current_keys
            and entry["Status__c"] in {"Découvert", "Pris en charge"}
        ]
        if not disparu_ids:
            return 0

        for i in range(0, len(disparu_ids), _BATCH_SIZE):
            batch = disparu_ids[i: i + _BATCH_SIZE]
            records = [
                {
                    "attributes": {"type": "DeweyFinding__c"},
                    "Id": fid,
                    "Status__c": "Disparu",
                }
                for fid in batch
            ]
            self._rest(
                "PATCH",
                "/composite/sobjects",
                {"allOrNone": False, "records": records},
            )

        # Create junction records for disparu findings (delta tracking per component)
        junction_disparu = [
            {
                "attributes": {"type": "DeweyAnalysisFinding__c"},
                "DeweyAnalysis__c": analysis_id,
                "DeweyFinding__c": fid,
                "IsNewInRun__c": False,
                "IsDisparuInRun__c": True,
            }
            for fid in disparu_ids
        ]
        for i in range(0, len(junction_disparu), _BATCH_SIZE):
            batch = junction_disparu[i: i + _BATCH_SIZE]
            self._rest(
                "POST",
                "/composite/sobjects",
                {"allOrNone": False, "records": batch},
            )

        return len(disparu_ids)

    # ── Delta helpers ──────────────────────────────────────────────────────────

    def _fetch_previous_analysis_id(
        self, project: str, exclude_id: str = ""
    ) -> str | None:
        """Returns the Id of the most recent completed analysis before the current one."""
        where = f"Project__c = '{project}' AND Status__c = 'Completed'"
        if exclude_id:
            where += f" AND Id != '{exclude_id}'"
        soql = (
            f"SELECT Id FROM DeweyAnalysis__c "
            f"WHERE {where} "
            f"ORDER BY AnalysisDate__c DESC LIMIT 1"
        )
        cmd = ["sf", "data", "query", "--query", soql, "--json", "-o", self.org_alias]
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(out.stdout)
        records = data.get("result", {}).get("records", [])
        return records[0]["Id"] if records else None

    def _fetch_previous_counts(self, prev_id: str) -> dict:
        soql = (
            f"SELECT ScoreRatio__c, FindingCritical__c, FindingMajor__c "
            f"FROM DeweyAnalysis__c WHERE Id = '{prev_id}'"
        )
        cmd = ["sf", "data", "query", "--query", soql, "--json", "-o", self.org_alias]
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(out.stdout)
        records = data.get("result", {}).get("records", [])
        if not records:
            return {}
        r = records[0]
        return {
            "ScoreRatio__c": float(r.get("ScoreRatio__c") or 0),
            "FindingCritical__c": int(r.get("FindingCritical__c") or 0),
            "FindingMajor__c": int(r.get("FindingMajor__c") or 0),
        }

    # ── Posture push ──────────────────────────────────────────────────────────

    def _push_posture(
        self, analysis_id: str, adoption_stats, snapshot=None, source: str = ""
    ) -> None:
        """Creates one DeweyPosture__c record per capability assessment,
        including PreviousLevel__c and LevelChange__c for trend tracking."""
        from src.core.posture_enricher import get_decisive_component

        prev_posture = self._fetch_previous_posture_levels(source, analysis_id) if source else {}

        records = []
        for a in adoption_stats.assessments:
            ctype, cname = (
                get_decisive_component(a.capability_id, a.level, snapshot)
                if snapshot is not None else ("", "")
            )
            current_val = a.level.value
            prev_level = prev_posture.get(a.capability_id)
            if prev_level is None:
                change = "Premier run"
            elif current_val == prev_level:
                change = "Stable"
            elif _LEVEL_ORDER.get(current_val, 99) < _LEVEL_ORDER.get(prev_level, 99):
                change = "Amélioré"
            else:
                change = "Dégradé"

            records.append({
                "attributes": {"type": "DeweyPosture__c"},
                "DeweyAnalysis__c": analysis_id,
                "CapabilityId__c": a.capability_id[:50],
                "CapabilityLabel__c": a.label[:100],
                "Level__c": current_val,
                "Weight__c": a.weight,
                "Evidence__c": "\n".join(a.evidence)[:32768] if a.evidence else "",
                "ComponentType__c": ctype[:80] if ctype else "",
                "ComponentName__c": cname[:255] if cname else "",
                "PreviousLevel__c": prev_level or "",
                "LevelChange__c": change,
            })
        if not records:
            return
        results = self._rest(
            "POST",
            "/composite/sobjects",
            {"allOrNone": False, "records": records},
        )
        errors = [r for r in results if not r.get("success")]
        if errors:
            raise RuntimeError(
                f"DeweyPosture__c batch insert errors: {json.dumps(errors[:3])}"
            )

    def _push_component_posture(
        self,
        analysis_id: str,
        report,
        posture_signal_map: dict[str, str],
        source: str = "",
    ) -> None:
        """
        Creates one DeweyPosture__c per unique component that has at least one
        non-Neutral PostureSignal on its findings.

        Signal priority: AdaptCode > AdaptDecl > AdoptDecl
        Level mapping:
          AdaptCode  → "Adapt (code)"
          AdaptDecl  → "Adapt (declaratif)"
          AdoptDecl  → "Adopt declaratif"
        """
        from collections import defaultdict

        _SIGNAL_ORDER: dict[str, int] = {
            "AdaptCode": 3,
            "AdaptDecl": 2,
            "AdoptDecl": 1,
        }
        _SIGNAL_TO_LEVEL: dict[str, str] = {
            "AdaptCode": "Adapt (code)",
            "AdaptDecl": "Adapt (declaratif)",
            "AdoptDecl": "Adopt declaratif",
        }

        # Compute worst signal per (component_type, component_name)
        comp_signal: dict[tuple[str, str], int] = defaultdict(int)
        for finding in report.all_findings():
            signal = posture_signal_map.get(finding.rule.id)
            if not signal or signal not in _SIGNAL_ORDER:
                continue
            key = (_map_component_type(finding.target_kind), finding.target_name or "")
            comp_signal[key] = max(comp_signal[key], _SIGNAL_ORDER[signal])

        if not comp_signal:
            return

        # Fetch previous component posture for LevelChange
        prev_posture = (
            self._fetch_previous_component_posture(source, analysis_id) if source else {}
        )

        _ORDER_TO_SIGNAL = {v: k for k, v in _SIGNAL_ORDER.items()}
        records = []
        for (comp_type, comp_name), signal_val in comp_signal.items():
            signal_key = _ORDER_TO_SIGNAL[signal_val]
            current_level = _SIGNAL_TO_LEVEL[signal_key]
            prev_level = prev_posture.get((comp_type, comp_name))

            if prev_level is None:
                change = "Premier run"
            elif current_level == prev_level:
                change = "Stable"
            elif _LEVEL_ORDER.get(current_level, 99) < _LEVEL_ORDER.get(prev_level, 99):
                change = "Amélioré"
            else:
                change = "Dégradé"

            records.append({
                "attributes": {"type": "DeweyPosture__c"},
                "DeweyAnalysis__c": analysis_id,
                "CapabilityId__c": "component_posture",
                "CapabilityLabel__c": f"{comp_type}: {comp_name}"[:100],
                "Level__c": current_level,
                "Weight__c": 1,
                "Evidence__c": "",
                "ComponentType__c": comp_type[:80],
                "ComponentName__c": comp_name[:255],
                "PreviousLevel__c": prev_level or "",
                "LevelChange__c": change,
            })

        for i in range(0, len(records), _BATCH_SIZE):
            batch = records[i: i + _BATCH_SIZE]
            results = self._rest(
                "POST",
                "/composite/sobjects",
                {"allOrNone": False, "records": batch},
            )
            errors = [r for r in results if not r.get("success")]
            if errors:
                print(
                    f"      [posture] {len(errors)} error(s) in component posture batch: "
                    f"{json.dumps(errors[:2])}"
                )

        print(f"      [posture] {len(records)} component posture record(s) pushed")

    def _fetch_previous_component_posture(
        self, source: str, exclude_id: str
    ) -> dict[tuple[str, str], str]:
        """Returns {(component_type, component_name): level} from the previous analysis."""
        prev_id = self._fetch_previous_analysis_id(source, exclude_id=exclude_id)
        if not prev_id:
            return {}
        soql = (
            f"SELECT ComponentType__c, ComponentName__c, Level__c FROM DeweyPosture__c "
            f"WHERE DeweyAnalysis__c = '{prev_id}' AND CapabilityId__c = 'component_posture'"
        )
        cmd = ["sf", "data", "query", "--query", soql, "--json", "-o", self.org_alias]
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
        records = json.loads(out.stdout).get("result", {}).get("records", [])
        return {
            (r.get("ComponentType__c", ""), r.get("ComponentName__c", "")): r["Level__c"]
            for r in records
        }

    def _fetch_previous_posture_levels(
        self, source: str, exclude_id: str
    ) -> dict[str, str]:
        """Returns {capability_id: level_value} from the most recent previous analysis."""
        prev_id = self._fetch_previous_analysis_id(source, exclude_id=exclude_id)
        if not prev_id:
            return {}
        soql = (
            f"SELECT CapabilityId__c, Level__c FROM DeweyPosture__c "
            f"WHERE DeweyAnalysis__c = '{prev_id}'"
        )
        cmd = ["sf", "data", "query", "--query", soql, "--json", "-o", self.org_alias]
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
        records = json.loads(out.stdout).get("result", {}).get("records", [])
        return {r["CapabilityId__c"]: r["Level__c"] for r in records}

    # ── Static helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _key(rule_id: str, component_name: str) -> str:
        return f"{rule_id}::{component_name}"

    @staticmethod
    def _finding_key(finding) -> str:
        return f"{finding.rule.id}::{finding.target_name or ''}"
