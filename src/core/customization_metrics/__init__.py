"""Customisation and adoption metrics derived from a metadata snapshot.

This package was split from a single ``customization_metrics.py`` module
for readability. It exposes two complementary indicators that round out
the existing absolute scores (``CustomizationMetrics.score`` and
``CustomizationMetrics.adopt_adapt_score``):

* :class:`DataModelCustomisationStats` quantifies the *data model
  footprint* by comparing custom objects/fields to the standard ones
  present in the snapshot (approach A in the design discussion).
* :class:`AdoptionStats` evaluates the *Adopt vs Adapt posture* across a
  fixed catalogue of nine Salesforce capabilities (approach B).
* :class:`SelectedUsageStats` measures how much of that footprint the Data
  Dictionary selection actually covers.

Every public name is re-exported here so existing
``from src.core.customization_metrics import X`` imports keep working.
"""

from __future__ import annotations

from src.core.customization_metrics.catalog import (
    CAPABILITY_CATALOG,
    SNAPSHOT_METRIC_KEYS,
    PostureCapabilityConfig,
    snapshot_metric_count,
)
from src.core.customization_metrics.compute import compute_adoption_stats
from src.core.customization_metrics.data_model import (
    DataModelCustomisationStats,
    compute_data_model_stats,
)
from src.core.customization_metrics.posture_types import (
    CAPABILITY_LEVEL_ORDER,
    AdoptionStats,
    CapabilityAssessment,
    CapabilityDefinition,
    CapabilityLevel,
)
from src.core.customization_metrics.selected_usage import (
    SelectedUsageStats,
    UsageBucket,
    UsageTable,
    compute_selected_usage_stats,
)

__all__ = [
    "AdoptionStats",
    "CAPABILITY_CATALOG",
    "CAPABILITY_LEVEL_ORDER",
    "CapabilityAssessment",
    "CapabilityDefinition",
    "CapabilityLevel",
    "DataModelCustomisationStats",
    "PostureCapabilityConfig",
    "SNAPSHOT_METRIC_KEYS",
    "SelectedUsageStats",
    "UsageBucket",
    "UsageTable",
    "compute_adoption_stats",
    "compute_data_model_stats",
    "compute_selected_usage_stats",
    "snapshot_metric_count",
]
