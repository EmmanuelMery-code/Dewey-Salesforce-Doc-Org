"""Capability catalogue, snapshot metric keys and posture configuration."""

from __future__ import annotations

from dataclasses import dataclass

from src.core.models import MetadataSnapshot

from src.core.customization_metrics.posture_types import (
    CapabilityDefinition,
    CapabilityLevel,
)


CAPABILITY_CATALOG: tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition("data_model", "Modele de donnees", 3),
    CapabilityDefinition("security", "Securite", 3),
    CapabilityDefinition("automation", "Automatisation", 3),
    CapabilityDefinition("validation", "Validation metier", 2),
    CapabilityDefinition("ui_layout", "UI / Layout", 2),
    CapabilityDefinition("integration", "Integration", 2),
    CapabilityDefinition("reporting", "Reporting", 2),
    CapabilityDefinition("notifications", "Notifications & Email", 2),
    CapabilityDefinition("omnistudio", "OmniStudio", 1),
)


# Catalogue of metadata counters that can drive a custom user-defined
# capability. The label is what the configuration UI shows; the resolver
# returns the count for a given snapshot (so we can produce evidence
# automatically). Each entry is small and self-contained on purpose so
# callers can iterate the dict without importing other modules.
SNAPSHOT_METRIC_KEYS: dict[str, str] = {
    "custom_objects": "Objets custom",
    "custom_fields": "Champs custom",
    "record_types": "Record types",
    "validation_rules": "Regles de validation",
    "layouts": "Page layouts",
    "custom_tabs": "Onglets custom",
    "custom_apps": "Applications custom",
    "flows": "Flows",
    "apex_classes": "Classes Apex",
    "apex_triggers": "Triggers Apex",
    "omni_scripts": "OmniScripts",
    "omni_integration_procedures": "Integration Procedures Omni",
    "omni_ui_cards": "UI Cards / FlexCards",
    "omni_data_transforms": "Data Transforms Omni",
    "lwc_count": "Composants LWC",
    "flexipage_count": "FlexiPages (pages Lightning)",
}


def snapshot_metric_count(snapshot: MetadataSnapshot, key: str) -> int:
    """Return the integer count stored on ``snapshot.metrics`` for ``key``."""

    metrics = getattr(snapshot, "metrics", None)
    if metrics is None:
        return 0
    value = getattr(metrics, key, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


@dataclass(slots=True)
class PostureCapabilityConfig:
    """User-provided configuration overlay for a posture capability.

    The configuration screen edits a list of these entries: each one
    targets a builtin capability (matching ``CAPABILITY_CATALOG``) or a
    custom user-defined capability (``custom=True``).

    ``level`` controls the override:

    * ``None``  : use the heuristic assessor (only meaningful for builtin
      capabilities since custom ones have no assessor).
    * any :class:`CapabilityLevel` value: force that level regardless of
      the snapshot. The assessor still runs to gather evidence.

    For custom capabilities ``metadata_key`` points at one of
    :data:`SNAPSHOT_METRIC_KEYS`; the count is used to build an evidence
    line so the report stays auditable.
    """

    capability_id: str
    label: str
    weight: int
    level: CapabilityLevel | None = None
    custom: bool = False
    metadata_key: str = ""
