"""
posture_enricher — Mode B
Derives (ComponentType, ComponentName) for the decisive component of each
DeweyPosture__c record without modifying customization_metrics.py.

CapabilityAssessment uses @dataclass(slots=True) — fields cannot be added at
runtime. This module re-inspects the MetadataSnapshot using the same logic as
the built-in assessors to identify the component that drove the level.
"""
from __future__ import annotations

try:
    from src.core.customization_metrics import (
        CapabilityLevel,
        _APEX_CALLOUT_PATTERNS,
        _APEX_VALIDATION_PATTERNS,
        _APEX_EMAIL_PATTERNS,
        _STANDARD_PROFILE_NAMES,
    )
    _IMPORTS_OK = True
except ImportError:
    _IMPORTS_OK = False
    CapabilityLevel = None  # type: ignore[assignment,misc]


def get_decisive_component(
    capability_id: str, level, snapshot
) -> tuple[str, str]:
    """
    Returns (component_type, component_name) for the component that drove the
    Adopt/Adapt level for this capability.
    Returns ("", "") for ADOPT (OOTB) — no decisive customisation present.
    """
    if not _IMPORTS_OK or level is CapabilityLevel.ADOPT:
        return "", ""

    if capability_id == "data_model":
        objs = [o for o in snapshot.objects if o.custom]
        return ("CustomObject", objs[0].api_name) if objs else ("CustomObject", "")

    if capability_id == "security":
        custom_profiles = [
            p for p in snapshot.profiles
            if p.name.casefold() not in _STANDARD_PROFILE_NAMES
        ]
        if custom_profiles:
            return ("Profile", custom_profiles[0].name)
        psets = snapshot.permission_sets
        return ("PermissionSet", psets[0].name) if psets else ("", "")

    if capability_id == "automation":
        triggers = [a for a in snapshot.apex_artifacts if a.kind == "trigger"]
        if triggers:
            return ("ApexTrigger", triggers[0].name)
        flows = snapshot.flows
        return ("Flow", flows[0].name) if flows else ("", "")

    if capability_id == "validation":
        for artifact in snapshot.apex_artifacts:
            if artifact.kind == "trigger" and artifact.body:
                if _APEX_VALIDATION_PATTERNS.search(artifact.body):
                    return ("ApexTrigger", artifact.name)
        for obj in snapshot.objects:
            if obj.validation_rules:
                vr = obj.validation_rules[0]
                return ("ValidationRule", f"{obj.api_name}.{vr.full_name}")
        return "", ""

    if capability_id == "ui_layout":
        if snapshot.metrics.lwc_count:
            return ("LWC", f"{snapshot.metrics.lwc_count} composant(s)")
        flexipages = snapshot.inventory.get("lightning_pages", [])
        if flexipages:
            name = flexipages[0].get("Label") or flexipages[0].get("NomAPI") or ""
            return ("FlexiPage", name)
        return "", ""

    if capability_id == "integration":
        for artifact in snapshot.apex_artifacts:
            if artifact.body and _APEX_CALLOUT_PATTERNS.search(artifact.body):
                t = "ApexTrigger" if artifact.kind == "trigger" else "ApexClass"
                return (t, artifact.name)
        return "", ""

    if capability_id == "reporting":
        dashboards = snapshot.inventory.get("dashboards", [])
        if dashboards:
            name = dashboards[0].get("Label") or dashboards[0].get("NomAPI") or ""
            return ("Dashboard", name)
        reports = snapshot.inventory.get("reports", [])
        if reports:
            name = reports[0].get("Label") or reports[0].get("NomAPI") or ""
            return ("Report", name)
        return "", ""

    if capability_id == "notifications":
        for artifact in snapshot.apex_artifacts:
            if artifact.body and _APEX_EMAIL_PATTERNS.search(artifact.body):
                return ("ApexClass", artifact.name)
        alerts = (
            snapshot.inventory.get("email_alerts", [])
            + snapshot.inventory.get("workflow_email_alerts", [])
        )
        if alerts:
            name = alerts[0].get("Label") or alerts[0].get("NomAPI") or ""
            return ("EmailAlert", name)
        return "", ""

    if capability_id == "omnistudio":
        m = snapshot.metrics
        if m.omni_scripts:
            return ("OmniScript", f"{m.omni_scripts} composant(s)")
        if m.omni_integration_procedures:
            return ("IntegrationProcedure", f"{m.omni_integration_procedures} composant(s)")
        if m.omni_ui_cards:
            return ("UICard", f"{m.omni_ui_cards} composant(s)")
        if m.omni_data_transforms:
            return ("DataTransform", f"{m.omni_data_transforms} composant(s)")
        return "", ""

    return "", ""
