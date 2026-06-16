from __future__ import annotations

from src.analyzer.models import Finding
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import AuraInfo


def analyze_aura(aura: AuraInfo, catalog: RuleCatalog) -> list[Finding]:
    findings: list[Finding] = []

    # AURA-MAINT-001 : Component complexity
    rule = catalog.get("AURA-MAINT-001")
    if rule and rule.enabled and (aura.line_count_cmp > 200 or aura.line_count_js > 300):
        findings.append(
            Finding(
                rule=rule,
                target_kind="Aura",
                target_name=aura.name,
                message="Composant Aura volumineux.",
                details=[
                    f"CMP: {aura.line_count_cmp} lignes, JS: {aura.line_count_js} lignes.",
                    "Considerez une migration vers LWC pour de meilleures performances et maintenabilite."
                ],
                source_path=aura.source_path,
            )
        )

    return findings
