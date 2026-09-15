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
                message="Le flow ne porte pas de description globale.",
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
                    message=f"Seulement {described_ratio:.0%} des elements du flow portent une description.",
                    details=[
                        f"{flow.described_elements}/{flow.total_elements} elements documentes.",
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
                message=f"Flow comportant {flow.total_elements} elements (seuil recommande : 40).",
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
                    message=f"{decisions} decisions detectees dans le flow (seuil recommande : 8).",
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
                    message=f"{data_ops} operations de donnees (create/update/delete/lookup) detectees.",
                    details=[
                        f"Lookups = {flow.element_counts.get('recordLookups', 0)}, "
                        f"Creates = {flow.element_counts.get('recordCreates', 0)}, "
                        f"Updates = {flow.element_counts.get('recordUpdates', 0)}, "
                        f"Deletes = {flow.element_counts.get('recordDeletes', 0)}.",
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
                message="Une operation de lecture (Get Records) apparait dans une boucle.",
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
                message="Une operation d'ecriture (Create/Update/Delete) apparait dans une boucle.",
                source_path=flow.source_path,
            )
        )

    # FLOW-PERF-004 : External Service action call in loop
    rule = catalog.get("FLOW-PERF-004")
    if rule and rule.enabled and flow.api_call_in_loop:
        actions = ", ".join(flow.api_call_in_loop_actions) or "action non identifiee"
        findings.append(
            Finding(
                rule=rule,
                target_kind="Flow",
                target_name=flow.name,
                message="Un appel d'action External Service apparait potentiellement dans une boucle.",
                details=[f"Action(s) concernee(s) : {actions}."],
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
                f"{FAULT_CAPABLE_ELEMENTS[element.element_type]} "
                f"'{element.label or element.name}' : aucun chemin d'erreur."
                for element in unprotected[:_MAX_FAULT_DETAILS]
            ]
            remaining = len(unprotected) - len(details)
            if remaining > 0:
                details.append(f"... et {remaining} autre(s) element(s) non protege(s).")
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Flow",
                    target_name=flow.name,
                    message=(
                        f"{len(unprotected)} element(s) sur {len(eligible)} pouvant echouer "
                        "ne declarent pas de chemin d'erreur (fault path)."
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
                message=f"Profondeur maximale = {flow.max_depth} (seuil recommande : 4).",
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
                    message=f"Le flow est au statut '{flow.status or 'Non renseigne'}'.",
                    source_path=flow.source_path,
                )
            )

    return findings
