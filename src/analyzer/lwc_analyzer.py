from __future__ import annotations

from src.analyzer.models import Finding
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import LwcInfo


def analyze_lwc(lwc: LwcInfo, catalog: RuleCatalog) -> list[Finding]:
    findings: list[Finding] = []

    # LWC-MAINT-001 : Component complexity (JS lines)
    rule = catalog.get("LWC-MAINT-001")
    if rule and rule.enabled and lwc.line_count_js > 300:
        findings.append(
            Finding(
                rule=rule,
                target_kind="LWC",
                target_name=lwc.name,
                message=f"Composant JS volumineux ({lwc.line_count_js} lignes).",
                details=["Considerez un decoupage en sous-composants ou l'utilisation de modules de service."],
                source_path=lwc.source_path,
            )
        )

    # LWC-MAINT-002 : Template complexity (HTML lines)
    rule = catalog.get("LWC-MAINT-002")
    if rule and rule.enabled and lwc.line_count_html > 200:
        findings.append(
            Finding(
                rule=rule,
                target_kind="LWC",
                target_name=lwc.name,
                message=f"Template HTML volumineux ({lwc.line_count_html} lignes).",
                source_path=lwc.source_path,
            )
        )

    # LWC-SEC-001 : @AuraEnabled usage
    rule = catalog.get("LWC-SEC-001")
    if rule and rule.enabled and lwc.has_aura_enabled:
        findings.append(
            Finding(
                rule=rule,
                target_kind="LWC",
                target_name=lwc.name,
                message="Le composant utilise @AuraEnabled pour appeler de l'Apex.",
                details=["Verifiez que les classes Apex appelees respectent les regles de securite (CRUD/FLS)."],
                source_path=lwc.source_path,
            )
        )

    return findings
