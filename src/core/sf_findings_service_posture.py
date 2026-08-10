"""DeweyPosture__c push mixin (capability-level and component-level posture).

Extracted from :mod:`sf_findings_service` to keep that file under the
repo's 500-line convention. :class:`_PostureMixin` is mixed into
``SfFindingsService`` and relies on ``self._rest`` provided by the main
class.
"""
from __future__ import annotations

import json
import subprocess

from src.core.sf_findings_service_helpers import (
    _BATCH_SIZE,
    _LEVEL_ORDER,
    _map_component_type,
)


class _PostureMixin:
    """Push capability-level and component-level DeweyPosture__c records."""

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

            rec = {
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
            }
            records.append(rec)
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

            rec = {
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
            }
            records.append(rec)

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
