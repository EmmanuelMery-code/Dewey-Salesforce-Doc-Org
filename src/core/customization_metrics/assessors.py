"""Heuristic per-capability detection against a metadata snapshot."""

from __future__ import annotations

import re
from typing import Any

from src.core.models import ApexArtifact, MetadataSnapshot, SecurityArtifact

from src.core.customization_metrics.posture_types import CapabilityLevel


# Standard Salesforce profiles that should never count as custom. The
# list covers the ones a typical Sales/Service/Platform retrieve will
# expose; anything outside the set is treated as a custom profile,
# which is a conservative-but-useful heuristic. Comparison is done
# case-insensitively.
_STANDARD_PROFILE_NAMES: frozenset[str] = frozenset(
    name.casefold()
    for name in (
        "Standard User",
        "System Administrator",
        "Read Only",
        "Solution Manager",
        "Marketing User",
        "Contract Manager",
        "Standard Platform User",
        "Force.com - App Subscription User",
        "Force.com - Free User",
        "Authenticated Website",
        "Chatter External User",
        "Chatter Free User",
        "Chatter Moderator User",
        "Cross Org Data Proxy User",
        "Customer Portal Manager Custom",
        "Customer Portal Manager Standard",
        "Customer Community User",
        "Customer Community Plus User",
        "Customer Community Login User",
        "Partner Community User",
        "Partner Community Login User",
        "External Apps Login User",
        "External Apps Plus User",
        "External Identity User",
        "Gold Partner User",
        "Silver Partner User",
        "High Volume Customer Portal",
        "High Volume Customer Portal User",
        "Identity User",
        "Minimum Access - Salesforce",
        "Salesforce API Only System Integrations",
        "Work.com Only User",
        "Analytics Cloud Integration User",
        "Analytics Cloud Security User",
    )
)


_APEX_CALLOUT_PATTERNS = re.compile(
    r"\b(?:HttpRequest\b|new\s+Http\s*\(|@future\s*\(\s*callout\s*=\s*true|"
    r"WebServiceCallout\b|Database\.executeBatch\b|Queueable\b|Crypto\.|"
    r"EncodingUtil\.)",
    re.IGNORECASE,
)

_APEX_VALIDATION_PATTERNS = re.compile(
    r"\.\s*addError\s*\(|SObjectException", re.IGNORECASE
)

_APEX_EMAIL_PATTERNS = re.compile(
    r"Messaging\.\s*(?:SingleEmailMessage|MassEmailMessage|sendEmail)",
    re.IGNORECASE,
)


def _is_custom_profile(profile: SecurityArtifact) -> bool:
    return profile.name.casefold() not in _STANDARD_PROFILE_NAMES


def _has_apex_pattern(
    artifacts: list[ApexArtifact], pattern: re.Pattern[str], *, kinds: set[str] | None = None
) -> tuple[bool, list[str]]:
    """Return ``(found, names)`` for artifacts matching ``pattern``.

    ``names`` lists the matching artifact names (capped at five so the
    UI evidence stays readable). When ``kinds`` is provided, only Apex
    artifacts of the listed kinds (e.g. ``{"trigger"}``) are scanned.
    """

    matches: list[str] = []
    for artifact in artifacts:
        if kinds is not None and artifact.kind not in kinds:
            continue
        if not artifact.body:
            continue
        if pattern.search(artifact.body):
            matches.append(artifact.name)
    return bool(matches), matches[:5]


def _format_evidence(label: str, items: list[str]) -> str:
    if not items:
        return label
    sample = ", ".join(items[:3])
    suffix = "..." if len(items) > 3 else ""
    return f"{label} : {sample}{suffix}"


def _assess_data_model(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    from src.core.models import DEFAULT_DATA_MODEL_THRESHOLDS

    custom_objects = [obj for obj in snapshot.objects if obj.custom]
    custom_fields_total = sum(
        1 for obj in snapshot.objects for f in obj.fields if f.custom
    )

    evidence: list[str] = []
    if custom_objects:
        evidence.append(
            _format_evidence(
                f"{len(custom_objects)} objet(s) custom", [o.api_name for o in custom_objects]
            )
        )
    if custom_fields_total:
        evidence.append(f"{custom_fields_total} champ(s) custom au total")
    if not evidence:
        evidence = ["Aucun objet ni champ custom detecte"]

    thresholds = (
        getattr(getattr(snapshot, "metrics", None), "data_model_thresholds", None)
        or DEFAULT_DATA_MODEL_THRESHOLDS
    )
    low, medium, high = thresholds
    count = len(custom_objects)

    if count < low:
        return CapabilityLevel.ADOPT, evidence
    if count < medium:
        return CapabilityLevel.ADOPT_DECLARATIVE, evidence
    if count < high:
        return CapabilityLevel.ADAPT_LOW, evidence
    return CapabilityLevel.ADAPT_HIGH, evidence


def _assess_security(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    from src.core.models import DEFAULT_PROFILES_THRESHOLDS

    custom_profiles = [p for p in snapshot.profiles if _is_custom_profile(p)]
    permission_sets = snapshot.permission_sets

    evidence: list[str] = []
    if custom_profiles:
        evidence.append(
            _format_evidence(
                f"{len(custom_profiles)} profile(s) custom",
                [p.name for p in custom_profiles],
            )
        )
    if permission_sets:
        evidence.append(
            _format_evidence(
                f"{len(permission_sets)} permission set(s)",
                [p.name for p in permission_sets],
            )
        )
    if not evidence:
        evidence = ["Profils standards uniquement, pas de permission set"]

    thresholds = (
        getattr(getattr(snapshot, "metrics", None), "profiles_thresholds", None)
        or DEFAULT_PROFILES_THRESHOLDS
    )
    low, medium, high = thresholds
    count = len(custom_profiles)

    if count < low:
        return CapabilityLevel.ADOPT, evidence
    if count < medium:
        return CapabilityLevel.ADOPT_DECLARATIVE, evidence
    if count < high:
        return CapabilityLevel.ADAPT_LOW, evidence
    return CapabilityLevel.ADAPT_HIGH, evidence


def _assess_automation(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    triggers = [a for a in snapshot.apex_artifacts if a.kind == "trigger"]
    flows = snapshot.flows

    evidence: list[str] = []
    if flows:
        evidence.append(
            _format_evidence(f"{len(flows)} flow(s)", [f.name for f in flows])
        )
    if triggers:
        evidence.append(
            _format_evidence(
                f"{len(triggers)} trigger(s)", [t.name for t in triggers]
            )
        )

    if triggers:
        return CapabilityLevel.ADAPT_HIGH, evidence
    if flows:
        return CapabilityLevel.ADAPT_LOW, evidence
    return CapabilityLevel.ADOPT, ["Aucun flow ni trigger Apex detecte"]


def _assess_validation(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    validation_rules = [
        (obj.api_name, vr.full_name)
        for obj in snapshot.objects
        for vr in obj.validation_rules
    ]
    has_apex_validation, apex_names = _has_apex_pattern(
        snapshot.apex_artifacts, _APEX_VALIDATION_PATTERNS, kinds={"trigger"}
    )

    evidence: list[str] = []
    if validation_rules:
        sample = [f"{a}.{b}" for a, b in validation_rules[:3]]
        suffix = "..." if len(validation_rules) > 3 else ""
        evidence.append(
            f"{len(validation_rules)} validation rule(s) : {', '.join(sample)}{suffix}"
        )
    if has_apex_validation:
        evidence.append(
            _format_evidence(
                f"{len(apex_names)} trigger(s) avec addError", apex_names
            )
        )

    if has_apex_validation:
        return CapabilityLevel.ADAPT_HIGH, evidence
    if validation_rules:
        return CapabilityLevel.ADAPT_LOW, evidence
    return CapabilityLevel.ADOPT, ["Aucune validation rule ni trigger de validation"]


def _assess_ui_layout(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    metrics = snapshot.metrics
    flexipages: list[dict[str, Any]] = snapshot.inventory.get("lightning_pages", [])
    layouts: list[dict[str, Any]] = snapshot.inventory.get("layouts", [])

    evidence: list[str] = []
    if metrics.lwc_count:
        evidence.append(f"{metrics.lwc_count} LWC")
    if flexipages:
        names = [str(row.get("Label") or row.get("NomAPI") or "") for row in flexipages]
        evidence.append(_format_evidence(f"{len(flexipages)} FlexiPage(s)", names))
    if layouts:
        evidence.append(f"{len(layouts)} layout(s) deploye(s)")

    if metrics.lwc_count:
        return CapabilityLevel.ADAPT_HIGH, evidence
    if flexipages:
        return CapabilityLevel.ADAPT_LOW, evidence
    return CapabilityLevel.ADOPT, evidence or ["Layouts standards uniquement"]


def _assess_integration(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    has_callout, names = _has_apex_pattern(
        snapshot.apex_artifacts, _APEX_CALLOUT_PATTERNS
    )
    evidence: list[str] = []
    if has_callout:
        evidence.append(
            _format_evidence(
                f"{len(names)} classe(s)/trigger(s) avec callout ou async",
                names,
            )
        )

    # We currently do not parse Named Credentials / External Services. If a
    # future inventory category is added, the Adapt-Low branch can detect
    # the declarative case (Named Credentials without callout). Until
    # then we only distinguish Adopt vs Adapt-High.
    if has_callout:
        return CapabilityLevel.ADAPT_HIGH, evidence
    return CapabilityLevel.ADOPT, ["Aucun callout Apex detecte"]


def _assess_reporting(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    reports: list[dict[str, Any]] = snapshot.inventory.get("reports", [])
    dashboards: list[dict[str, Any]] = snapshot.inventory.get("dashboards", [])

    evidence: list[str] = []
    if reports:
        evidence.append(f"{len(reports)} report(s) custom")
    if dashboards:
        evidence.append(f"{len(dashboards)} dashboard(s) custom")

    if dashboards:
        return CapabilityLevel.ADAPT_HIGH, evidence
    if reports:
        return CapabilityLevel.ADAPT_LOW, evidence
    return CapabilityLevel.ADOPT, ["Aucun report ni dashboard custom"]


def _assess_notifications(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    has_email_apex, names = _has_apex_pattern(
        snapshot.apex_artifacts, _APEX_EMAIL_PATTERNS
    )
    email_alerts: list[dict[str, Any]] = []
    for key in ("email_alerts", "workflow_email_alerts"):
        email_alerts.extend(snapshot.inventory.get(key, []))

    evidence: list[str] = []
    if has_email_apex:
        evidence.append(
            _format_evidence(
                f"{len(names)} classe(s) avec Messaging.sendEmail", names
            )
        )
    if email_alerts:
        evidence.append(f"{len(email_alerts)} email alert(s)/template(s) custom")

    if has_email_apex:
        return CapabilityLevel.ADAPT_HIGH, evidence
    if email_alerts:
        return CapabilityLevel.ADAPT_LOW, evidence
    return CapabilityLevel.ADOPT, ["Aucune notification Apex/email alert detectee"]


def _assess_omnistudio(snapshot: MetadataSnapshot) -> tuple[CapabilityLevel, list[str]]:
    metrics = snapshot.metrics
    has_high = metrics.omni_scripts + metrics.omni_integration_procedures > 0
    has_low = metrics.omni_data_transforms + metrics.omni_ui_cards > 0

    evidence: list[str] = []
    if metrics.omni_scripts:
        evidence.append(f"{metrics.omni_scripts} OmniScript(s)")
    if metrics.omni_integration_procedures:
        evidence.append(
            f"{metrics.omni_integration_procedures} Integration Procedure(s)"
        )
    if metrics.omni_ui_cards:
        evidence.append(f"{metrics.omni_ui_cards} UI Card(s)")
    if metrics.omni_data_transforms:
        evidence.append(f"{metrics.omni_data_transforms} DataRaptor(s)/Transform(s)")

    if has_high:
        return CapabilityLevel.ADAPT_HIGH, evidence
    if has_low:
        return CapabilityLevel.ADAPT_LOW, evidence
    return CapabilityLevel.ADOPT, ["Pas de composant OmniStudio detecte"]


_ASSESSORS = {
    "data_model": _assess_data_model,
    "security": _assess_security,
    "automation": _assess_automation,
    "validation": _assess_validation,
    "ui_layout": _assess_ui_layout,
    "integration": _assess_integration,
    "reporting": _assess_reporting,
    "notifications": _assess_notifications,
    "omnistudio": _assess_omnistudio,
}
