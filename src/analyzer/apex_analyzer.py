from __future__ import annotations

from src.analyzer.apex_analyzer_helpers import (
    _count_code_lines,
    _detect_self_recursive_methods,
    _detect_soql_injection,
    _detect_trigger_after_save_recursion,
    _find_hardcoded_ids,
    _has_security_enforcement,
    _strip_comments_and_strings,
)
from src.analyzer.models import Finding
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import ApexArtifact


def analyze_apex_artifact(artifact: ApexArtifact, catalog: RuleCatalog) -> list[Finding]:
    if artifact.kind == "trigger":
        return _analyze_trigger(artifact, catalog)
    return _analyze_class(artifact, catalog)


# ------------------------------------------------------------------ classes


def _analyze_class(artifact: ApexArtifact, catalog: RuleCatalog) -> list[Finding]:
    findings: list[Finding] = []

    # APEX-SEC-001 : sharing declaration
    if not artifact.is_test and not artifact.is_interface:
        rule = catalog.get("APEX-SEC-001")
        if rule and rule.enabled and not artifact.sharing_declaration:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message=catalog.t("apex.sharing.message"),
                    details=[catalog.t("apex.sharing.detail")],
                    source_path=artifact.source_path,
                )
            )

    # APEX-SEC-002 : hardcoded Id
    rule = catalog.get("APEX-SEC-002")
    if rule and rule.enabled:
        hardcoded = _find_hardcoded_ids(artifact.body)
        if hardcoded:
            sample = ", ".join(sorted(hardcoded)[:5])
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message=catalog.t("apex.hardcoded_id.message", count=len(hardcoded)),
                    details=[catalog.t("apex.hardcoded_id.detail", sample=sample)],
                    source_path=artifact.source_path,
                )
            )

    # APEX-SEC-003 : SOQL injection
    rule = catalog.get("APEX-SEC-003")
    if rule and rule.enabled and not artifact.is_test:
        injection_lines = _detect_soql_injection(artifact.body)
        if injection_lines:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message=catalog.t("apex.soql_injection.message"),
                    details=[catalog.t("apex.soql_injection.detail")],
                    source_path=artifact.source_path,
                    line=injection_lines[0],
                )
            )

    # APEX-SEC-004 : CRUD/FLS enforcement
    rule = catalog.get("APEX-SEC-004")
    if rule and rule.enabled and not artifact.is_test:
        if (artifact.dml_count > 0 or artifact.soql_count > 0) and not _has_security_enforcement(artifact.body):
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message=catalog.t("apex.crud_fls.message"),
                    details=[catalog.t("apex.crud_fls.detail")],
                    source_path=artifact.source_path,
                )
            )

    # APEX-REL-001 : try/catch around DML/SOQL
    rule = catalog.get("APEX-REL-001")
    if rule and rule.enabled and not artifact.is_test:
        if (artifact.dml_count > 0 or artifact.soql_count > 0) and not artifact.has_try_catch:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message=catalog.t("apex.no_try_catch.message"),
                    details=[
                        catalog.t(
                            "apex.soql_dml_counts.detail",
                            soql=artifact.soql_count,
                            dml=artifact.dml_count,
                        ),
                    ],
                    source_path=artifact.source_path,
                )
            )

    # APEX-PERF-001 : SOQL in loop
    rule = catalog.get("APEX-PERF-001")
    if rule and rule.enabled and artifact.query_in_loop:
        findings.append(
            Finding(
                rule=rule,
                target_kind="ApexClass",
                target_name=artifact.name,
                message=catalog.t("apex.soql_in_loop.message"),
                source_path=artifact.source_path,
                line=artifact.query_in_loop_line,
            )
        )

    # APEX-PERF-002 : DML in loop
    rule = catalog.get("APEX-PERF-002")
    if rule and rule.enabled and artifact.dml_in_loop:
        findings.append(
            Finding(
                rule=rule,
                target_kind="ApexClass",
                target_name=artifact.name,
                message=catalog.t("apex.dml_in_loop.message"),
                source_path=artifact.source_path,
                line=artifact.dml_in_loop_line,
            )
        )

    # APEX-PERF-003 : HTTP callout in loop
    rule = catalog.get("APEX-PERF-003")
    if rule and rule.enabled and artifact.callout_in_loop:
        findings.append(
            Finding(
                rule=rule,
                target_kind="ApexClass",
                target_name=artifact.name,
                message=catalog.t("apex.callout_in_loop.message"),
                source_path=artifact.source_path,
                line=artifact.callout_in_loop_line,
            )
        )

    # APEX-REL-002 : method self-recursion without visible guard
    rule = catalog.get("APEX-REL-002")
    if rule and rule.enabled and not artifact.is_test:
        recursive_methods = _detect_self_recursive_methods(artifact.body)
        if recursive_methods:
            sample = ", ".join(sorted(recursive_methods)[:5])
            details = [catalog.t("apex.recursion.detail_methods", sample=sample)]
            if len(recursive_methods) > 5:
                details.append(
                    catalog.t(
                        "apex.recursion.detail_more",
                        count=len(recursive_methods) - 5,
                    )
                )
            details.append(catalog.t("apex.recursion.detail_no_guard"))
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message=catalog.t(
                        "apex.recursion.message", count=len(recursive_methods)
                    ),
                    details=details,
                    source_path=artifact.source_path,
                )
            )

    # APEX-MAINT-001 : class length
    rule = catalog.get("APEX-MAINT-001")
    if rule and rule.enabled:
        code_lines = _count_code_lines(artifact.body)
        if code_lines > 500:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message=catalog.t("apex.class_length.message", lines=code_lines),
                    details=[
                        catalog.t(
                            "apex.class_length.detail",
                            code=code_lines,
                            total=artifact.line_count,
                        )
                    ],
                    source_path=artifact.source_path,
                )
            )

    # APEX-MAINT-002 : comment density
    rule = catalog.get("APEX-MAINT-002")
    if rule and rule.enabled and artifact.line_count > 80:
        ratio = artifact.comment_line_count / max(1, artifact.line_count)
        if ratio < 0.05:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexClass",
                    target_name=artifact.name,
                    message=catalog.t(
                        "apex.comment_density.message", ratio=f"{ratio:.1%}"
                    ),
                    details=[
                        catalog.t(
                            "apex.comment_density.detail",
                            commented=artifact.comment_line_count,
                            total=artifact.line_count,
                        )
                    ],
                    source_path=artifact.source_path,
                )
            )

    # APEX-MAINT-003 : too many System.debug
    rule = catalog.get("APEX-MAINT-003")
    if rule and rule.enabled and artifact.system_debug_count > 10:
        findings.append(
            Finding(
                rule=rule,
                target_kind="ApexClass",
                target_name=artifact.name,
                message=catalog.t(
                    "apex.system_debug.message", count=artifact.system_debug_count
                ),
                source_path=artifact.source_path,
            )
        )

    return findings


# ------------------------------------------------------------------ triggers


def _analyze_trigger(artifact: ApexArtifact, catalog: RuleCatalog) -> list[Finding]:
    findings: list[Finding] = []

    # TRIG-MAINT-001 : business logic in trigger
    rule = catalog.get("TRIG-MAINT-001")
    if rule and rule.enabled:
        code_lines = _count_code_lines(artifact.body)
        has_dml_or_soql = artifact.dml_count > 0 or artifact.soql_count > 0
        if code_lines > 10 or has_dml_or_soql:
            details = [
                catalog.t("trigger.business_logic.detail_lines", count=code_lines)
            ]
            if has_dml_or_soql:
                details.append(
                    catalog.t(
                        "apex.soql_dml_counts.detail",
                        soql=artifact.soql_count,
                        dml=artifact.dml_count,
                    )
                )
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexTrigger",
                    target_name=artifact.name,
                    message=catalog.t("trigger.business_logic.message"),
                    details=details,
                    source_path=artifact.source_path,
                )
            )

    # TRIG-REL-001 : after insert/update trigger rewriting Trigger.new (recursion risk)
    rule = catalog.get("TRIG-REL-001")
    if rule and rule.enabled:
        detection = _detect_trigger_after_save_recursion(artifact.body)
        if detection is not None:
            events, dml_sample = detection
            details = [
                catalog.t(
                    "trigger.after_save_recursion.detail_events",
                    events=", ".join(sorted(events)),
                ),
                catalog.t(
                    "trigger.after_save_recursion.detail_operation",
                    operation=dml_sample,
                ),
                catalog.t("trigger.after_save_recursion.detail_no_guard"),
            ]
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ApexTrigger",
                    target_name=artifact.name,
                    message=catalog.t("trigger.after_save_recursion.message"),
                    details=details,
                    source_path=artifact.source_path,
                )
            )

    # TRIG-PERF-001 : SOQL or DML in loop
    rule = catalog.get("TRIG-PERF-001")
    if rule and rule.enabled and (artifact.query_in_loop or artifact.dml_in_loop):
        parts = []
        candidate_lines = []
        if artifact.query_in_loop:
            parts.append(catalog.t("trigger.part.soql_in_loop"))
            if artifact.query_in_loop_line is not None:
                candidate_lines.append(artifact.query_in_loop_line)
        if artifact.dml_in_loop:
            parts.append(catalog.t("trigger.part.dml_in_loop"))
            if artifact.dml_in_loop_line is not None:
                candidate_lines.append(artifact.dml_in_loop_line)
        findings.append(
            Finding(
                rule=rule,
                target_kind="ApexTrigger",
                target_name=artifact.name,
                message=catalog.t(
                    "trigger.data_ops_in_loop.message", parts=", ".join(parts)
                ),
                source_path=artifact.source_path,
                line=min(candidate_lines) if candidate_lines else None,
            )
        )

    return findings
