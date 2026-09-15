from __future__ import annotations

import re

from src.analyzer.models import Finding
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import ObjectInfo, ValidationRuleInfo, DuplicateRuleInfo


def analyze_object(obj: ObjectInfo, catalog: RuleCatalog) -> list[Finding]:
    findings: list[Finding] = []

    rule = catalog.get("OBJ-READ-001")
    if rule and rule.enabled and obj.custom and not obj.description:
        findings.append(
            Finding(
                rule=rule,
                target_kind="Object",
                target_name=obj.api_name,
                message=catalog.t("object.no_description.message"),
                source_path=obj.source_path,
            )
        )

    rule = catalog.get("OBJ-ADAPT-001")
    if rule and rule.enabled:
        custom_fields = [f for f in obj.fields if f.custom]
        if len(custom_fields) > 50:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Object",
                    target_name=obj.api_name,
                    message=catalog.t(
                        "object.too_many_fields.message", count=len(custom_fields)
                    ),
                    source_path=obj.source_path,
                )
            )

    rule = catalog.get("OBJ-MAINT-001")
    if rule and rule.enabled:
        active_vrs = [vr for vr in obj.validation_rules if vr.active]
        if len(active_vrs) > 10:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Object",
                    target_name=obj.api_name,
                    message=catalog.t(
                        "object.too_many_validation_rules.message",
                        count=len(active_vrs),
                    ),
                    source_path=obj.source_path,
                )
            )

    rule = catalog.get("OBJ-MAINT-002")
    if rule and rule.enabled:
        active_rts = [rt for rt in obj.record_types if rt.active]
        if len(active_rts) > 3:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Object",
                    target_name=obj.api_name,
                    message=catalog.t(
                        "object.too_many_record_types.message", count=len(active_rts)
                    ),
                    source_path=obj.source_path,
                )
            )

    # FIELD-READ-001 : champs custom sans description (agrege au niveau de l'objet)
    rule = catalog.get("FIELD-READ-001")
    if rule and rule.enabled:
        undocumented = [
            field.api_name
            for field in obj.fields
            if field.custom and not field.description
        ]
        if undocumented:
            details: list[str] = []
            preview = ", ".join(undocumented[:10])
            if len(undocumented) > 10:
                preview += f", ... (+{len(undocumented) - 10})"
            details.append(catalog.t("field.no_description.detail", preview=preview))
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Field",
                    target_name=obj.api_name,
                    message=catalog.t(
                        "field.no_description.message", count=len(undocumented)
                    ),
                    details=details,
                    source_path=obj.source_path,
                )
            )

    return findings


def analyze_validation_rule(
    vr: ValidationRuleInfo, object_name: str, catalog: RuleCatalog
) -> list[Finding]:
    findings: list[Finding] = []
    target_name = f"{object_name}.{vr.full_name}"

    rule = catalog.get("VR-READ-001")
    if rule and rule.enabled and not vr.description:
        findings.append(
            Finding(
                rule=rule,
                target_kind="ValidationRule",
                target_name=target_name,
                message=catalog.t("validation_rule.no_description.message"),
            )
        )

    rule = catalog.get("VR-MAINT-001")
    if rule and rule.enabled:
        score = vr.complexity_score
        if score > 15:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ValidationRule",
                    target_name=target_name,
                    message=catalog.t(
                        "validation_rule.complexity.message", score=score
                    ),
                    details=[
                        catalog.t(
                            "validation_rule.complexity.detail_length",
                            length=len(vr.error_condition_formula or ""),
                        ),
                        catalog.t("validation_rule.complexity.detail_advice"),
                    ]
                )
            )

    return findings


def analyze_duplicate_rule(
    dr: DuplicateRuleInfo, object_name: str, catalog: RuleCatalog
) -> list[Finding]:
    findings: list[Finding] = []
    target_name = f"{object_name}.{dr.full_name}"

    rule = catalog.get("DR-READ-001")
    if rule and rule.enabled and not dr.description:
        findings.append(
            Finding(
                rule=rule,
                target_kind="DuplicateRule",
                target_name=target_name,
                message=catalog.t("duplicate_rule.no_description.message"),
            )
        )

    rule = catalog.get("DR-SEC-001")
    if rule and rule.enabled and dr.security_enforcement == "EnforceSharingRules":
        findings.append(
            Finding(
                rule=rule,
                target_kind="DuplicateRule",
                target_name=target_name,
                message=catalog.t("duplicate_rule.sharing.message"),
                details=[catalog.t("duplicate_rule.sharing.detail")],
            )
        )

    return findings
