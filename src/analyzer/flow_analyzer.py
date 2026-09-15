from __future__ import annotations

from src.analyzer.models import Finding
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import FAULT_CAPABLE_ELEMENTS, FlowInfo

_MAX_FAULT_DETAILS = 20


def analyze_flow(flow: FlowInfo, catalog: RuleCatalog) -> list[Finding]:
    findings: list[Finding] = []

    rule = catalog.get("FLOW-READ-001")
    if rule and rule.enabled and not flow.description:
        findings.append(
            Finding(
                rule=rule,
                target_kind="Flow",
                target_name=flow.name,
                message=catalog.t("flow.no_description.message"),
                source_path=flow.source_path,
            )
        )

    rule = catalog.get("FLOW-READ-002")
    if rule and rule.enabled and flow.total_elements > 0:
        described_ratio = flow.described_elements / flow.total_elements
        if described_ratio < 0.5:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Flow",
                    target_name=flow.name,
                    message=catalog.t(
                        "flow.described_ratio.message", ratio=f"{described_ratio:.0%}"
                    ),
                    details=[
                        catalog.t(
                            "flow.described_ratio.detail",
                            described=flow.described_elements,
                            total=flow.total_elements,
                        ),
                    ],
                    source_path=flow.source_path,
                )
            )

    rule = catalog.get("FLOW-MAINT-001")
    if rule and rule.enabled and flow.total_elements > 40:
        findings.append(
            Finding(
                rule=rule,
                target_kind="Flow",
                target_name=flow.name,
                message=catalog.t("flow.size.message", count=flow.total_elements),
                source_path=flow.source_path,
            )
        )

    rule = catalog.get("FLOW-MAINT-002")
    if rule and rule.enabled:
        decisions = flow.element_counts.get("decisions", 0)
        if decisions > 8:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Flow",
                    target_name=flow.name,
                    message=catalog.t("flow.decisions.message", count=decisions),
                    source_path=flow.source_path,
                )
            )

    rule = catalog.get("FLOW-PERF-001")
    if rule and rule.enabled:
        data_ops = sum(
            flow.element_counts.get(name, 0)
            for name in ("recordCreates", "recordUpdates", "recordDeletes", "recordLookups")
        )
        if data_ops > 6:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Flow",
                    target_name=flow.name,
                    message=catalog.t("flow.data_ops.message", count=data_ops),
                    details=[
                        catalog.t(
                            "flow.data_ops.detail",
                            lookups=flow.element_counts.get("recordLookups", 0),
                            creates=flow.element_counts.get("recordCreates", 0),
                            updates=flow.element_counts.get("recordUpdates", 0),
                            deletes=flow.element_counts.get("recordDeletes", 0),
                        ),
                    ],
                    source_path=flow.source_path,
                )
            )

    # FLOW-PERF-002 : SOQL in loop
    rule = catalog.get("FLOW-PERF-002")
    if rule and rule.enabled and flow.soql_in_loop:
        findings.append(
            Finding(
                rule=rule,
                target_kind="Flow",
                target_name=flow.name,
                message=catalog.t("flow.soql_in_loop.message"),
                source_path=flow.source_path,
            )
        )

    # FLOW-PERF-003 : DML in loop
    rule = catalog.get("FLOW-PERF-003")
    if rule and rule.enabled and flow.dml_in_loop:
        findings.append(
            Finding(
                rule=rule,
                target_kind="Flow",
                target_name=flow.name,
                message=catalog.t("flow.dml_in_loop.message"),
                source_path=flow.source_path,
            )
        )

    # FLOW-PERF-004 : External Service action call in loop
    rule = catalog.get("FLOW-PERF-004")
    if rule and rule.enabled and flow.api_call_in_loop:
        actions = ", ".join(flow.api_call_in_loop_actions) or catalog.t(
            "flow.api_in_loop.unknown_action"
        )
        findings.append(
            Finding(
                rule=rule,
                target_kind="Flow",
                target_name=flow.name,
                message=catalog.t("flow.api_in_loop.message"),
                details=[catalog.t("flow.api_in_loop.detail", actions=actions)],
                source_path=flow.source_path,
            )
        )

    # FLOW-REL-001 : elements faillibles sans fault path
    rule = catalog.get("FLOW-REL-001")
    if rule and rule.enabled:
        eligible = flow.fault_capable_elements
        unprotected = flow.unprotected_fault_elements
        if unprotected:
            details = [
                catalog.t(
                    "flow.fault_path.detail",
                    kind=FAULT_CAPABLE_ELEMENTS[element.element_type],
                    name=element.label or element.name,
                )
                for element in unprotected[:_MAX_FAULT_DETAILS]
            ]
            remaining = len(unprotected) - len(details)
            if remaining > 0:
                details.append(
                    catalog.t("flow.fault_path.detail_more", count=remaining)
                )
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Flow",
                    target_name=flow.name,
                    message=catalog.t(
                        "flow.fault_path.message",
                        unprotected=len(unprotected),
                        total=len(eligible),
                    ),
                    details=details,
                    source_path=flow.source_path,
                )
            )

    rule = catalog.get("FLOW-MAINT-003")
    if rule and rule.enabled and flow.max_depth > 4:
        findings.append(
            Finding(
                rule=rule,
                target_kind="Flow",
                target_name=flow.name,
                message=catalog.t("flow.depth.message", depth=flow.max_depth),
                source_path=flow.source_path,
            )
        )

    rule = catalog.get("FLOW-ADAPT-001")
    if rule and rule.enabled:
        status = (flow.status or "").lower()
        if status and status not in {"active", "obsolete"}:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Flow",
                    target_name=flow.name,
                    message=catalog.t(
                        "flow.status.message",
                        status=flow.status or catalog.t("flow.status.unknown"),
                    ),
                    source_path=flow.source_path,
                )
            )

    return findings
