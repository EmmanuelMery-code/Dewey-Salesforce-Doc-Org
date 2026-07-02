"""Aggregate snapshot dataclass tying together all parsed metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core.models.automation import ApexArtifact, FlowInfo
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
    RedundantFlowGroup,
    SharingRuleInfo,
    TechnicalDebtItem,
)
from src.core.models.metadata import ObjectInfo
from src.core.models.metrics import CustomizationMetrics
from src.core.models.security import PermissionSetGroupInfo, SecurityArtifact


@dataclass(slots=True)
class MetadataSnapshot:
    source_dir: Path
    package_roots: list[Path]
    objects: list[ObjectInfo] = field(default_factory=list)
    profiles: list[SecurityArtifact] = field(default_factory=list)
    permission_sets: list[SecurityArtifact] = field(default_factory=list)
    permission_set_groups: list[PermissionSetGroupInfo] = field(default_factory=list)
    apex_artifacts: list[ApexArtifact] = field(default_factory=list)
    flows: list[FlowInfo] = field(default_factory=list)
    agents: list[AgentInfo] = field(default_factory=list)
    gen_ai_prompts: list[GenAiPromptInfo] = field(default_factory=list)
    sharing_rules: list[SharingRuleInfo] = field(default_factory=list)
    duplicate_rules: list[DuplicateRuleInfo] = field(default_factory=list)
    lwc: list[LwcInfo] = field(default_factory=list)
    aura: list[AuraInfo] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    orphans: list[OrphanInfo] = field(default_factory=list)
    redundant_flows: list[RedundantFlowGroup] = field(default_factory=list)
    technical_debt: list[TechnicalDebtItem] = field(default_factory=list)
    deviations: list[DeviationItem] = field(default_factory=list)
    innovations: list[InnovationItem] = field(default_factory=list)
    innovation_colors: dict[str, str] = field(default_factory=dict)
    metrics: CustomizationMetrics = field(default_factory=CustomizationMetrics)
    inventory: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    ai_usage_stats: Any | None = None
    data_model_stats: Any | None = None
    adoption_stats: Any | None = None
    findings_summary: dict[str, int] = field(default_factory=dict)
