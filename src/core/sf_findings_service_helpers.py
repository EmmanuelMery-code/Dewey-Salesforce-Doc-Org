"""Shared constants and pure helper functions for :mod:`sf_findings_service`.

Kept side-effect free (no Salesforce REST/CLI calls) so the mapping tables
and small computations used across the finding-dedup and posture mixins
live in one place without introducing import cycles.
"""
from __future__ import annotations

import re

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Maps Dewey target_kind values → ComponentType__c picklist
_COMPONENT_TYPE_MAP: dict[str, str] = {
    "apex_class":       "Apex",
    "apexclass":        "Apex",
    "apex_trigger":     "Apex",
    "apextrigger":      "Apex",
    "flow":             "Flow",
    "lwc":              "LWC",
    "lwccomponent":     "LWC",
    "aura":             "LWC",
    "auracomponent":    "LWC",
    "object":           "Object",
    "customobject":     "Object",
    "validationrule":   "Object",
    "duplicaterule":    "Object",
    "profile":          "Security",
    "permissionset":    "Security",
    "permissionsetgroup": "Security",
    "securityartifact": "Security",
    "omni_script":      "OmniStudio",
    "omniscript":       "OmniStudio",
    "dataraptorextract": "OmniStudio",
    "dataraptortransform": "OmniStudio",
    "data_transform":   "OmniStudio",
    "integrationprocedure": "OmniStudio",
    "flexcard":         "OmniStudio",
}

# Statuses that prevent a finding from being reused (must be recreated if re-detected)
_TERMINAL_STATUSES = {"Résolu", "Accepté"}

# Statuses that indicate the finding is still active (not yet addressed)
_ACTIVE_STATUSES = {"Découvert", "Pris en charge", "Disparu"}

# Maximum scoring weight in DEFAULT_SCORING_WEIGHTS (custom_objects = 8).
# Used to compute ScoreMax: total_artifacts × _SCORE_MAX_WEIGHT.
_SCORE_MAX_WEIGHT = 8

# Ordered posture levels — lower index = closer to OOTB (better for a Salesforce org)
_LEVEL_ORDER: dict[str, int] = {
    "Adopt (OOTB)": 0,
    "Adopt declaratif": 1,
    "Adapt (declaratif)": 2,
    "Adapt (code)": 3,
}

_API_VERSION = "v66.0"
_BATCH_SIZE = 200


def _map_component_type(target_kind: str) -> str:
    return _COMPONENT_TYPE_MAP.get((target_kind or "").lower(), "Other")


def _compute_score_max(metrics) -> int:
    """
    Theoretical maximum score for this org's artifact volume.
    = total artifact count × max scoring weight (8 = custom_objects).
    Used as denominator for ScoreRatio__c formula field.
    """
    total = (
        metrics.apex_classes + metrics.apex_triggers
        + metrics.flows
        + metrics.custom_objects + metrics.custom_fields
        + metrics.record_types + metrics.validation_rules
        + metrics.layouts + metrics.custom_tabs + metrics.custom_apps
        + metrics.omni_scripts + metrics.omni_integration_procedures
        + metrics.omni_ui_cards + metrics.omni_data_transforms
        + metrics.bre_decision_matrices + metrics.bre_expression_sets
        + metrics.agents + metrics.gen_ai_prompts + metrics.einstein_predictions
        + metrics.lwc_count + metrics.flexipage_count
    )
    return total * _SCORE_MAX_WEIGHT
