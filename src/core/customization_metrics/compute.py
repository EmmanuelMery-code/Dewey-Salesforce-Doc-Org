"""Evaluate the capability catalogue and aggregate the adoption posture."""

from __future__ import annotations

from src.core.models import MetadataSnapshot

from src.core.customization_metrics.assessors import _ASSESSORS
from src.core.customization_metrics.catalog import (
    CAPABILITY_CATALOG,
    SNAPSHOT_METRIC_KEYS,
    PostureCapabilityConfig,
    snapshot_metric_count,
)
from src.core.customization_metrics.posture_types import (
    AdoptionStats,
    CapabilityAssessment,
    CapabilityDefinition,
    CapabilityLevel,
)


def _evaluate_builtin(
    definition: CapabilityDefinition,
    snapshot: MetadataSnapshot,
    override: PostureCapabilityConfig | None,
) -> CapabilityAssessment | None:
    """Build the assessment for a builtin capability, applying overrides."""

    assessor = _ASSESSORS.get(definition.capability_id)
    detected_level: CapabilityLevel
    evidence: list[str]
    if assessor is None:
        detected_level = CapabilityLevel.ADOPT
        evidence = []
    else:
        detected_level, evidence = assessor(snapshot)

    weight = definition.weight
    level = detected_level
    if override is not None:
        weight = override.weight if override.weight > 0 else weight
        if override.level is not None:
            level = override.level
            if level is not detected_level:
                evidence = [
                    f"Niveau force par configuration ({level.value})",
                    *evidence,
                ]
    label = override.label if override is not None and override.label else definition.label
    return CapabilityAssessment(
        capability_id=definition.capability_id,
        label=label,
        weight=weight,
        level=level,
        evidence=evidence,
    )


def _evaluate_custom(
    config: PostureCapabilityConfig,
    snapshot: MetadataSnapshot,
) -> CapabilityAssessment:
    """Build the assessment for a user-defined capability."""

    level = config.level or CapabilityLevel.ADOPT
    evidence: list[str] = []
    if config.metadata_key:
        count = snapshot_metric_count(snapshot, config.metadata_key)
        label = SNAPSHOT_METRIC_KEYS.get(config.metadata_key, config.metadata_key)
        evidence.append(f"{label} : {count}")
    evidence.append(f"Capacite definie par l'utilisateur ({level.value})")
    return CapabilityAssessment(
        capability_id=config.capability_id,
        label=config.label or config.capability_id,
        weight=max(config.weight, 0),
        level=level,
        evidence=evidence,
    )


def compute_adoption_stats(
    snapshot: MetadataSnapshot,
    posture_config: list[PostureCapabilityConfig] | None = None,
) -> AdoptionStats:
    """Run each capability assessor against ``snapshot`` and return the stats.

    When ``posture_config`` is provided the iteration order, weights,
    levels and label of each capability come from the configuration. New
    user-defined capabilities (``custom=True``) are evaluated from a
    metadata counter so they can contribute to the percentage even though
    no heuristic assessor exists for them.
    """

    stats = AdoptionStats()

    if not posture_config:
        for definition in CAPABILITY_CATALOG:
            assessment = _evaluate_builtin(definition, snapshot, None)
            if assessment is not None:
                stats.assessments.append(assessment)
        return stats

    builtin_by_id = {d.capability_id: d for d in CAPABILITY_CATALOG}
    seen_ids: set[str] = set()
    for entry in posture_config:
        if entry.capability_id in seen_ids:
            continue
        seen_ids.add(entry.capability_id)
        if entry.custom:
            stats.assessments.append(_evaluate_custom(entry, snapshot))
            continue
        definition = builtin_by_id.get(entry.capability_id)
        if definition is None:
            # Stale config pointing at a removed builtin: skip silently
            # rather than break the report.
            continue
        assessment = _evaluate_builtin(definition, snapshot, entry)
        if assessment is not None:
            stats.assessments.append(assessment)

    # Append any builtin capability the configuration does not mention so
    # the catalogue stays exhaustive even after an upgrade introduces new
    # default capabilities.
    for definition in CAPABILITY_CATALOG:
        if definition.capability_id in seen_ids:
            continue
        assessment = _evaluate_builtin(definition, snapshot, None)
        if assessment is not None:
            stats.assessments.append(assessment)
    return stats
