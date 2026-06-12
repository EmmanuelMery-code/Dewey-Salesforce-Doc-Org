"""Analyse statique des Profils et Permission Sets Salesforce.

Produit des findings SEC-001 à SEC-005 en inspectant les permissions
accordées et le ratio profils custom / Permission Sets.
"""

from __future__ import annotations

from pathlib import Path

from src.analyzer.models import Finding
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import SecurityArtifact

_DANGEROUS_USER_PERMS = {"ModifyAllData", "ManageUsers"}
_SENSITIVE_OBJECTS = {
    "Account", "Contact", "Opportunity", "Lead", "Order",
    "Case", "Contract", "User", "Event", "Task",
}


def analyze_profile(artifact: SecurityArtifact, catalog: RuleCatalog) -> list[Finding]:
    """Analyze a single profile and return findings."""
    findings: list[Finding] = []

    if not artifact.is_custom:
        return findings

    # SEC-001 : ModifyAllData user permission
    rule = catalog.get("SEC-001")
    if rule and rule.enabled:
        has_mad = any(
            up.enabled and up.name == "ModifyAllData"
            for up in artifact.user_permissions
        )
        if has_mad:
            findings.append(Finding(
                rule=rule,
                target_kind="Profile",
                target_name=artifact.name,
                message=f"Le profil '{artifact.name}' dispose de la permission ModifyAllData.",
                source_path=artifact.source_path,
            ))

    # SEC-002 : ManageUsers user permission
    rule = catalog.get("SEC-002")
    if rule and rule.enabled:
        has_mu = any(
            up.enabled and up.name == "ManageUsers"
            for up in artifact.user_permissions
        )
        if has_mu:
            findings.append(Finding(
                rule=rule,
                target_kind="Profile",
                target_name=artifact.name,
                message=f"Le profil '{artifact.name}' dispose de la permission ManageUsers.",
                source_path=artifact.source_path,
            ))

    # SEC-003 : ModifyAllRecords on any object
    rule = catalog.get("SEC-003")
    if rule and rule.enabled:
        mar_objects = [
            op.object_name for op in artifact.object_permissions
            if op.modify_all_records
        ]
        if mar_objects:
            objects_str = ", ".join(sorted(mar_objects)[:5])
            if len(mar_objects) > 5:
                objects_str += f" (+ {len(mar_objects) - 5} autres)"
            findings.append(Finding(
                rule=rule,
                target_kind="Profile",
                target_name=artifact.name,
                message=(
                    f"Le profil '{artifact.name}' a ModifyAllRecords sur {len(mar_objects)} "
                    f"objet(s) : {objects_str}."
                ),
                source_path=artifact.source_path,
            ))

    return findings


def analyze_permission_set(artifact: SecurityArtifact, catalog: RuleCatalog) -> list[Finding]:
    """Analyze a single permission set and return findings."""
    findings: list[Finding] = []

    # SEC-004 : ModifyAllRecords on sensitive objects
    rule = catalog.get("SEC-004")
    if rule and rule.enabled:
        sensitive_mar = [
            op.object_name for op in artifact.object_permissions
            if op.modify_all_records and op.object_name in _SENSITIVE_OBJECTS
        ]
        if sensitive_mar:
            findings.append(Finding(
                rule=rule,
                target_kind="PermissionSet",
                target_name=artifact.name,
                message=(
                    f"Le Permission Set '{artifact.name}' a ModifyAllRecords sur "
                    f"{', '.join(sorted(sensitive_mar))}."
                ),
                source_path=artifact.source_path,
            ))

    return findings


def analyze_org_security(
    profiles: list[SecurityArtifact],
    permission_sets: list[SecurityArtifact],
    catalog: RuleCatalog,
    ratio_threshold: int = 60,
) -> list[Finding]:
    """Produce org-level security findings (SEC-005 ratio)."""
    findings: list[Finding] = []

    rule = catalog.get("SEC-005")
    if not rule or not rule.enabled:
        return findings

    custom_profiles = [p for p in profiles if p.is_custom]
    ps_count = len(permission_sets)
    cp_count = len(custom_profiles)

    if ps_count == 0 and cp_count == 0:
        return findings

    ratio = int(cp_count / max(1, ps_count) * 100)
    if ratio >= ratio_threshold:
        findings.append(Finding(
            rule=rule,
            target_kind="Org",
            target_name="_org_",
            message=(
                f"Ratio profils custom / Permission Sets = {ratio}% "
                f"({cp_count} profils custom, {ps_count} Permission Sets). "
                f"Seuil recommande : < {ratio_threshold}%."
            ),
            source_path=None,
        ))

    return findings
