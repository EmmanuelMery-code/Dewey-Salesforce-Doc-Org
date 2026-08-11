"""Automation and code metadata dataclasses (Apex, Flows)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ApexArtifact:
    name: str
    kind: str
    body: str
    source_path: Path
    api_version: str = ""
    status: str = ""
    line_count: int = 0
    method_count: int = 0
    soql_count: int = 0
    sosl_count: int = 0
    dml_count: int = 0
    comment_line_count: int = 0
    system_debug_count: int = 0
    has_try_catch: bool = False
    sharing_declaration: str = ""
    is_test: bool = False
    is_interface: bool = False
    query_in_loop: bool = False
    query_in_loop_line: int | None = None
    dml_in_loop: bool = False
    dml_in_loop_line: int | None = None
    callout_in_loop: bool = False
    callout_in_loop_line: int | None = None
    test_coverage: float | None = None  # Percentage 0-100
    test_coverage_lines_covered: int = 0  # Nombre de lignes couvertes
    test_coverage_lines_uncovered: int = 0  # Nombre de lignes non couvertes


@dataclass(slots=True)
class FlowConnector:
    target: str
    label: str = ""


@dataclass(slots=True)
class FlowElementInfo:
    element_type: str
    name: str
    label: str = ""
    description: str = ""
    connectors: list[FlowConnector] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    target: str = ""  # Legacy, for backward compatibility if needed
    covered_by: list[str] = field(default_factory=list)  # Apex test class names


@dataclass(slots=True)
class FlowInfo:
    name: str
    label: str = ""
    description: str = ""
    process_type: str = ""
    status: str = ""
    api_version: str = ""
    trigger_type: str = ""
    start_object: str = ""
    start_node: str = ""
    source_path: Path | None = None
    element_counts: dict[str, int] = field(default_factory=dict)
    described_elements: int = 0
    undocumented_elements: int = 0
    total_elements: int = 0
    variable_total: int = 0
    variable_input: int = 0
    variable_output: int = 0
    max_width: int = 1
    min_height: int = 0
    max_height: int = 0
    max_depth: int = 0
    elements: list[FlowElementInfo] = field(default_factory=list)
    test_coverage: float | None = None  # Percentage 0-100
    test_coverage_elements_covered: int = 0  # Nombre d'éléments couverts
    test_coverage_elements_uncovered: int = 0  # Nombre d'éléments non couverts
    dml_in_loop: bool = False
    soql_in_loop: bool = False
    api_call_in_loop: bool = False
    api_call_in_loop_actions: list[str] = field(default_factory=list)

    @property
    def complexity_score(self) -> int:
        decision_count = self.element_counts.get("decisions", 0)
        loop_count = self.element_counts.get("loops", 0)
        subflow_count = self.element_counts.get("subflows", 0)
        data_ops = sum(
            self.element_counts.get(name, 0)
            for name in ("recordCreates", "recordUpdates", "recordDeletes", "recordLookups")
        )
        return (
            self.total_elements
            + decision_count * 3
            + loop_count * 4
            + subflow_count * 2
            + data_ops * 2
            + self.max_depth * 4
            + max(0, self.max_width - 1) * 2
            + self.undocumented_elements
        )

    @property
    def complexity_level(self) -> str:
        score = self.complexity_score
        if score < 20:
            return "Simple"
        if score < 45:
            return "Moyen"
        if score < 80:
            return "Complexe"
        return "Tres complexe"
