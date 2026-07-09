"""
SfConfigService — Mode B
Loads rule catalog, config, and exclusions from Salesforce Custom Objects.
"""
from __future__ import annotations

import dataclasses
import json
import subprocess
from pathlib import Path
from typing import Any

# ── Public dataclasses ─────────────────────────────────────────────────────────

class SfConfig:
    """Thin wrapper around DeweyConfig__c key/value pairs."""

    def __init__(self, raw: dict[str, str]) -> None:
        self._data = raw

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._data.get(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        val = self._data.get(key)
        try:
            return int(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        val = self._data.get(key)
        try:
            return float(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    def as_dict(self) -> dict[str, str]:
        return dict(self._data)


# ── Main service ───────────────────────────────────────────────────────────────

class SfConfigService:
    """Loads Dewey configuration from a Salesforce org via the SF CLI."""

    def __init__(self, org_alias: str) -> None:
        self.org_alias = org_alias

    # ── Public API ─────────────────────────────────────────────────────────────

    def load_rule_catalog(self):
        """
        Returns a RuleCatalog built from rules.xml overlaid with DeweyRule__c records.
        SF overrides: IsEnabled__c, Severity__c, Message__c, Remediation__c.
        SF-only rules (not in rules.xml) are added as-is.
        """
        from src.analyzer.rule_catalog import RuleCatalog
        from src.analyzer.models import Rule

        base_catalog = RuleCatalog.load()
        sf_rules = self._query_rules()

        if not sf_rules:
            return base_catalog

        base_by_id: dict[str, Rule] = {r.id: r for r in base_catalog.all}
        merged: dict[str, Rule] = dict(base_by_id)

        for sf in sf_rules:
            rule_id: str = sf.get("RuleId__c") or ""
            if not rule_id:
                continue

            if rule_id in merged:
                base = merged[rule_id]
                overrides: dict[str, Any] = {}
                if sf.get("IsEnabled__c") is not None:
                    overrides["enabled"] = bool(sf["IsEnabled__c"])
                if sf.get("Severity__c"):
                    overrides["severity"] = sf["Severity__c"]
                if sf.get("Message__c"):
                    overrides["description"] = sf["Message__c"]
                if sf.get("Remediation__c"):
                    overrides["remediation"] = sf["Remediation__c"]
                if sf.get("Category__c"):
                    overrides["category"] = sf["Category__c"]
                if sf.get("Subcategory__c"):
                    overrides["subcategory"] = sf["Subcategory__c"]
                if overrides:
                    merged[rule_id] = dataclasses.replace(base, **overrides)
            else:
                # SF-only rule — create a new Rule from scratch
                merged[rule_id] = Rule(
                    id=rule_id,
                    enabled=bool(sf.get("IsEnabled__c", True)),
                    scope=(sf.get("Scope__c") or ""),
                    category=(sf.get("Category__c") or ""),
                    subcategory=(sf.get("Subcategory__c") or ""),
                    severity=(sf.get("Severity__c") or "Info"),
                    source=(sf.get("Source__c") or "Salesforce"),
                    reference="",
                    title=rule_id,
                    description=(sf.get("Message__c") or ""),
                    rationale="",
                    remediation=(sf.get("Remediation__c") or ""),
                )

        return RuleCatalog(list(merged.values()))

    def load_config(self) -> SfConfig:
        """Returns a SfConfig populated from DeweyConfig__c."""
        records = self._query(
            "SELECT ConfigKey__c, ConfigValue__c FROM DeweyConfig__c"
        )
        raw = {r["ConfigKey__c"]: r["ConfigValue__c"] for r in records
               if r.get("ConfigKey__c")}
        return SfConfig(raw)

    def load_exclusions(self) -> dict[str, set[str]]:
        """
        Returns exclusions as dict[rule_id, set[component_name]].
        Only non-expired exclusions are returned.
        """
        records = self._query(
            "SELECT RuleId__c, ComponentName__c FROM DeweyExclusion__c "
            "WHERE ExpiryDate__c = null OR ExpiryDate__c >= TODAY"
        )
        exclusions: dict[str, set[str]] = {}
        for r in records:
            rule_id = r.get("RuleId__c") or ""
            component = r.get("ComponentName__c") or ""
            if rule_id and component:
                exclusions.setdefault(rule_id, set()).add(component)
        return exclusions

    # ── Internal helpers ───────────────────────────────────────────────────────

    def load_pmd_ref_map(self) -> dict[str, str]:
        """Returns {pmd_rule_name: dewey_rule_id} for enabled rules with PmdRuleRef__c set."""
        records = self._query(
            "SELECT RuleId__c, PmdRuleRef__c FROM DeweyRule__c "
            "WHERE PmdRuleRef__c != null AND IsEnabled__c = true"
        )
        return {r["PmdRuleRef__c"]: r["RuleId__c"] for r in records if r.get("PmdRuleRef__c")}

    def load_sfca_ref_map(self) -> dict[str, str]:
        """Returns {sfca_rule_name: dewey_rule_id} for enabled rules with SfcaRuleRef__c set."""
        records = self._query(
            "SELECT RuleId__c, SfcaRuleRef__c FROM DeweyRule__c "
            "WHERE SfcaRuleRef__c != null AND IsEnabled__c = true"
        )
        return {r["SfcaRuleRef__c"]: r["RuleId__c"] for r in records if r.get("SfcaRuleRef__c")}

    def load_posture_signal_map(self) -> dict[str, str]:
        """Returns {rule_id: signal} for rules with PostureSignal__c set (excluding Neutral)."""
        records = self._query(
            "SELECT RuleId__c, PostureSignal__c FROM DeweyRule__c "
            "WHERE PostureSignal__c != null AND PostureSignal__c != 'Neutral' "
            "AND IsEnabled__c = true"
        )
        return {
            r["RuleId__c"]: r["PostureSignal__c"]
            for r in records
            if r.get("RuleId__c") and r.get("PostureSignal__c")
        }

    def _query_rules(self) -> list[dict]:
        return self._query(
            "SELECT RuleId__c, IsEnabled__c, Severity__c, Category__c, "
            "Subcategory__c, Source__c, Message__c, Remediation__c, "
            "PmdRuleRef__c, SfcaRuleRef__c, PostureSignal__c "
            "FROM DeweyRule__c"
        )

    def _query(self, soql: str) -> list[dict]:
        cmd = [
            "sf", "data", "query",
            "--query", soql,
            "--json",
            "-o", self.org_alias,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        records = data.get("result", {}).get("records", [])
        # Strip Salesforce-added attributes key
        return [{k: v for k, v in r.items() if k != "attributes"} for r in records]
