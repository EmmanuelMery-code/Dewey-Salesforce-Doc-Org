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
                message=catalog.t("lwc.js_size.message", lines=lwc.line_count_js),
                details=[catalog.t("lwc.js_size.detail")],
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
                message=catalog.t("lwc.html_size.message", lines=lwc.line_count_html),
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
                message=catalog.t("lwc.aura_enabled.message"),
                details=[catalog.t("lwc.aura_enabled.detail")],
                source_path=lwc.source_path,
            )
        )

    # LWC-MAINT-003 : console.log usage
    rule = catalog.get("LWC-MAINT-003")
    if rule and rule.enabled:
        js_file = lwc.source_path / f"{lwc.name}.js"
        if js_file.exists():
            try:
                content = js_file.read_text(encoding="utf-8")
                if "console.log" in content or "console.error" in content:
                    findings.append(
                        Finding(
                            rule=rule,
                            target_kind="LWC",
                            target_name=lwc.name,
                            message=catalog.t("lwc.console.message"),
                            source_path=lwc.source_path,
                        )
                    )
            except OSError:
                pass

    # LWC-READ-001 : missing label or description
    rule = catalog.get("LWC-READ-001")
    if rule and rule.enabled and (not lwc.label or not lwc.description):
        findings.append(
            Finding(
                rule=rule,
                target_kind="LWC",
                target_name=lwc.name,
                message=catalog.t("lwc.metadata.message"),
                source_path=lwc.source_path,
            )
        )

    return findings
