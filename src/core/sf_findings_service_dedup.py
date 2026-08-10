"""Finding deduplication, creation and "Disparu" lifecycle mixin.

Extracted from :mod:`sf_findings_service` to keep that file under the
repo's 500-line convention. :class:`_FindingsDedupMixin` is mixed into
``SfFindingsService`` and relies on ``self._rest``, ``self._key`` and
``self._finding_key`` provided by the main class.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from src.core.sf_findings_service_helpers import (
    _BATCH_SIZE,
    _TERMINAL_STATUSES,
    _map_component_type,
)


class _FindingsDedupMixin:
    """Fetch/create/resolve DeweyFinding__c records and their junctions."""

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
                    try:
                        rel = Path(finding.source_path).relative_to(source_root)
                        rec["FilePath__c"] = ("/" + str(rel))[:255]
                    except (ValueError, TypeError):
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
            f"SELECT ScoreRatio__c, FindingCritical__c, FindingMajor__c, TestCoveragePct__c "
            f"FROM DeweyAnalysis__c WHERE Id = '{prev_id}'"
        )
        cmd = ["sf", "data", "query", "--query", soql, "--json", "-o", self.org_alias]
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(out.stdout)
        records = data.get("result", {}).get("records", [])
        if not records:
            return {}
        r = records[0]
        result: dict[str, Any] = {
            "ScoreRatio__c": float(r.get("ScoreRatio__c") or 0),
            "FindingCritical__c": int(r.get("FindingCritical__c") or 0),
            "FindingMajor__c": int(r.get("FindingMajor__c") or 0),
        }
        if r.get("TestCoveragePct__c") is not None:
            result["TestCoveragePct__c"] = float(r["TestCoveragePct__c"])
        return result
