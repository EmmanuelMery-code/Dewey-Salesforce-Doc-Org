"""Adopt vs Adapt posture data types (approach B).

Defines the capability level enum and the aggregate statistics produced
when evaluating a fixed catalogue of Salesforce capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CapabilityLevel(str, Enum):
    """Maturity of a capability on the Adopt-Adapt axis.

    Stored as ``str`` so the enum values serialise naturally to JSON and
    compare directly against the labels rendered on the report.

    Two levels count as *adoption* (``ADOPT`` for out-of-the-box usage and
    ``ADOPT_DECLARATIVE`` for standard Salesforce features used through
    declarative tooling), while ``ADAPT_LOW`` / ``ADAPT_HIGH`` count as
    *adaptation*.
    """

    ADOPT = "Adopt (OOTB)"
    ADOPT_DECLARATIVE = "Adopt declaratif"
    ADAPT_LOW = "Adapt (declaratif)"
    ADAPT_HIGH = "Adapt (code)"


# All level identifiers exposed to the configuration UI. Order matters: it
# is the order used to render dropdowns and to scan for "auto" detection.
CAPABILITY_LEVEL_ORDER: tuple[CapabilityLevel, ...] = (
    CapabilityLevel.ADOPT,
    CapabilityLevel.ADOPT_DECLARATIVE,
    CapabilityLevel.ADAPT_LOW,
    CapabilityLevel.ADAPT_HIGH,
)


_ADOPTION_LEVELS: frozenset[CapabilityLevel] = frozenset(
    {CapabilityLevel.ADOPT, CapabilityLevel.ADOPT_DECLARATIVE}
)


def _is_adoption(level: CapabilityLevel) -> bool:
    return level in _ADOPTION_LEVELS


@dataclass(slots=True, frozen=True)
class CapabilityDefinition:
    """Static metadata describing one capability to evaluate.

    The catalogue (see :data:`CAPABILITY_CATALOG`) is intentionally kept
    in code rather than in configuration: the detection rules call
    arbitrary snapshot attributes and have to be coupled to the parser
    schema, so a JSON/YAML representation would not be expressive enough
    without becoming a mini-DSL.
    """

    capability_id: str
    label: str
    weight: int


@dataclass(slots=True)
class CapabilityAssessment:
    """Result of evaluating one capability against the snapshot."""

    capability_id: str
    label: str
    weight: int
    level: CapabilityLevel
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AdoptionStats:
    """Aggregate adoption posture across all evaluated capabilities."""

    assessments: list[CapabilityAssessment] = field(default_factory=list)

    @property
    def total_weight(self) -> int:
        return sum(a.weight for a in self.assessments)

    def _weight_for(self, level: CapabilityLevel) -> int:
        return sum(a.weight for a in self.assessments if a.level is level)

    @property
    def adopt_ootb_weight(self) -> int:
        return self._weight_for(CapabilityLevel.ADOPT)

    @property
    def adopt_declarative_weight(self) -> int:
        return self._weight_for(CapabilityLevel.ADOPT_DECLARATIVE)

    @property
    def adopt_weight(self) -> int:
        # Aggregate weight of the two "adoption" levels (OOTB + declarative).
        # Existing renderers and tests rely on this name representing the
        # full adoption side of the scale.
        return self.adopt_ootb_weight + self.adopt_declarative_weight

    @property
    def adapt_low_weight(self) -> int:
        return self._weight_for(CapabilityLevel.ADAPT_LOW)

    @property
    def adapt_high_weight(self) -> int:
        return self._weight_for(CapabilityLevel.ADAPT_HIGH)

    @property
    def adapt_weight(self) -> int:
        return self.adapt_low_weight + self.adapt_high_weight

    def _count_for(self, level: CapabilityLevel) -> int:
        return sum(1 for a in self.assessments if a.level is level)

    @property
    def adopt_ootb_count(self) -> int:
        return self._count_for(CapabilityLevel.ADOPT)

    @property
    def adopt_declarative_count(self) -> int:
        return self._count_for(CapabilityLevel.ADOPT_DECLARATIVE)

    @property
    def adopt_count(self) -> int:
        # Total number of capabilities classified as adoption (OOTB or
        # declarative). Kept for backwards compatibility with the renderers.
        return self.adopt_ootb_count + self.adopt_declarative_count

    @property
    def adapt_low_count(self) -> int:
        return self._count_for(CapabilityLevel.ADAPT_LOW)

    @property
    def adapt_high_count(self) -> int:
        return self._count_for(CapabilityLevel.ADAPT_HIGH)

    @property
    def adapt_count(self) -> int:
        return self.adapt_low_count + self.adapt_high_count

    @property
    def total_count(self) -> int:
        return len(self.assessments)

    @property
    def percent_adoption(self) -> float:
        return (
            self.adopt_weight / self.total_weight * 100.0
            if self.total_weight
            else 0.0
        )

    @property
    def percent_adaptation(self) -> float:
        return 100.0 - self.percent_adoption if self.total_weight else 0.0

    @property
    def percent_adopt_ootb(self) -> float:
        return (
            self.adopt_ootb_weight / self.total_weight * 100.0
            if self.total_weight
            else 0.0
        )

    @property
    def percent_adopt_declarative(self) -> float:
        return (
            self.adopt_declarative_weight / self.total_weight * 100.0
            if self.total_weight
            else 0.0
        )

    @property
    def percent_adapt_low(self) -> float:
        return (
            self.adapt_low_weight / self.total_weight * 100.0
            if self.total_weight
            else 0.0
        )

    @property
    def percent_adapt_high(self) -> float:
        return (
            self.adapt_high_weight / self.total_weight * 100.0
            if self.total_weight
            else 0.0
        )
