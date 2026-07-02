"""Metadata model dataclasses.

This package was split from a single ``models.py`` module for readability.
Every public name is re-exported here so that existing
``from src.core.models import X`` imports keep working unchanged.
"""

from __future__ import annotations

from src.core.models.automation import (
    ApexArtifact,
    FlowConnector,
    FlowElementInfo,
    FlowInfo,
)
from src.core.models.components import (
    AgentInfo,
    AuraInfo,
    Dependency,
    DeviationItem,
    DuplicateRuleInfo,
    GenAiPromptInfo,
    InnovationItem,
    LwcInfo,
    OrphanInfo,
    PmdViolation,
    RedundantFlowGroup,
    ReviewResult,
    SharingRuleInfo,
    TechnicalDebtItem,
)
from src.core.models.metadata import (
    FieldInfo,
    ObjectInfo,
    RecordTypeInfo,
    RelationshipInfo,
    ValidationRuleInfo,
)
from src.core.models.metrics import (
    DEFAULT_ADOPT_ADAPT_THRESHOLDS,
    DEFAULT_ADOPT_ADAPT_WEIGHTS,
    DEFAULT_DATA_MODEL_THRESHOLDS,
    DEFAULT_PROFILES_PS_RATIO_THRESHOLDS,
    DEFAULT_PROFILES_THRESHOLDS,
    DEFAULT_SCORING_THRESHOLDS,
    DEFAULT_SCORING_WEIGHTS,
    CustomizationMetrics,
)
from src.core.models.security import (
    FieldPermission,
    NamedAccess,
    ObjectPermission,
    PermissionSetGroupInfo,
    RecordTypeVisibility,
    SecurityArtifact,
    UserPermission,
    VisibilityItem,
)
from src.core.models.snapshot import MetadataSnapshot

__all__ = [
    "AgentInfo",
    "ApexArtifact",
    "AuraInfo",
    "CustomizationMetrics",
    "DEFAULT_ADOPT_ADAPT_THRESHOLDS",
    "DEFAULT_ADOPT_ADAPT_WEIGHTS",
    "DEFAULT_DATA_MODEL_THRESHOLDS",
    "DEFAULT_PROFILES_PS_RATIO_THRESHOLDS",
    "DEFAULT_PROFILES_THRESHOLDS",
    "DEFAULT_SCORING_THRESHOLDS",
    "DEFAULT_SCORING_WEIGHTS",
    "Dependency",
    "DeviationItem",
    "DuplicateRuleInfo",
    "FieldInfo",
    "FieldPermission",
    "FlowConnector",
    "FlowElementInfo",
    "FlowInfo",
    "GenAiPromptInfo",
    "InnovationItem",
    "LwcInfo",
    "MetadataSnapshot",
    "NamedAccess",
    "ObjectInfo",
    "ObjectPermission",
    "OrphanInfo",
    "PermissionSetGroupInfo",
    "PmdViolation",
    "RecordTypeInfo",
    "RecordTypeVisibility",
    "RedundantFlowGroup",
    "RelationshipInfo",
    "ReviewResult",
    "SecurityArtifact",
    "SharingRuleInfo",
    "TechnicalDebtItem",
    "UserPermission",
    "ValidationRuleInfo",
    "VisibilityItem",
]
