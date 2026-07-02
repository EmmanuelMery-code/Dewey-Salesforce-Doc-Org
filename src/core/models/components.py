"""Miscellaneous metadata dataclasses (components, reviews, findings, tracking)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ReviewResult:
    summary: str
    positives: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    metrics: list[tuple[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class PmdViolation:
    file_path: Path
    rule: str
    ruleset: str = ""
    priority: str = ""
    begin_line: int = 0
    end_line: int = 0
    message: str = ""


@dataclass(slots=True)
class SharingRuleInfo:
    full_name: str
    object_name: str
    rule_type: str  # "criteria", "owner", "guest"
    label: str = ""
    description: str = ""


@dataclass(slots=True)
class AgentInfo:
    name: str
    label: str = ""
    description: str = ""
    agent_type: str = ""
    source_path: Path | None = None


@dataclass(slots=True)
class GenAiPromptInfo:
    name: str
    label: str = ""
    description: str = ""
    source_path: Path | None = None


@dataclass(slots=True)
class TechnicalDebtItem:
    label: str
    date_creation: str
    date_resolution: str
    accepted_solution: str
    target_solution: str


@dataclass(slots=True)
class DeviationItem:
    label: str
    date_creation: str
    explanation: str


@dataclass(slots=True)
class InnovationItem:
    label: str
    theme: str
    date_start: str
    date_end: str
    date_presentation: str
    description: str
    conclusion: str
    not_started: bool = False
    color: str = ""  # "positive", "neutral", "negative" or empty


@dataclass(slots=True)
class LwcInfo:
    name: str
    label: str = ""
    description: str = ""
    api_version: str = ""
    is_exposed: bool = False
    targets: list[str] = field(default_factory=list)
    has_aura_enabled: bool = False
    line_count_js: int = 0
    line_count_html: int = 0
    source_path: Path | None = None


@dataclass(slots=True)
class AuraInfo:
    name: str
    label: str = ""
    description: str = ""
    api_version: str = ""
    line_count_cmp: int = 0
    line_count_js: int = 0
    source_path: Path | None = None


@dataclass(slots=True)
class Dependency:
    source_name: str
    source_kind: str
    target_name: str
    target_kind: str


@dataclass(slots=True)
class DuplicateRuleInfo:
    full_name: str
    object_name: str
    action_on_insert: str = ""
    action_on_update: str = ""
    active: bool = False
    description: str = ""
    security_enforcement: str = ""

    @property
    def complexity_score(self) -> int:
        # Basic complexity for duplicate rules
        score = 1
        if self.action_on_insert == "Block": score += 2
        if self.action_on_update == "Block": score += 2
        if self.description: score -= 1
        return max(1, score)


@dataclass(slots=True)
class OrphanInfo:
    name: str
    kind: str
    source_path: Path | None = None


@dataclass(slots=True)
class RedundantFlowGroup:
    object_name: str
    trigger_type: str
    flows: list[str]
