"""Shared state declaration for the orchestrator mixins.

The generator is split into thematic mixins (history persistence, pipeline
steps, metadata loading). They all read the same instance attributes set in
:meth:`SalesforceDocumentationGenerator.__init__`. Declaring those attributes
here (annotations only, no values) gives the mixins a common, type-checkable
base without duplicating the attribute list in every file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.core.customization_metrics import PostureCapabilityConfig
from src.core.index_card_visibility import IndexCardVisibility

LogCallback = Callable[[str], None]


class _OrchestratorState:
    """Instance attributes shared across the generator mixins.

    Values are assigned in :meth:`SalesforceDocumentationGenerator.__init__`;
    this class only carries the annotations so ``self.*`` accesses inside the
    mixins resolve for static analysis.
    """

    source_dir: Path
    output_dir: Path
    exclusion_config_path: Path | None
    pmd_enabled: bool
    pmd_ruleset_path: Path | None
    generate_excels: bool
    generate_html: bool
    generate_data_dictionary_word: bool
    generate_summary_word: bool
    generate_audit_summary_rtf: bool
    generate_sarif: bool
    scoring_weights: dict[str, int] | None
    adopt_adapt_weights: dict[str, int] | None
    scoring_thresholds: tuple[int, int, int] | None
    adopt_adapt_thresholds: tuple[int, int, int] | None
    data_model_thresholds: tuple[int, int, int] | None
    profiles_thresholds: tuple[int, int, int] | None
    profiles_ps_ratio_thresholds: tuple[int, int, int] | None
    analyzer_rules_path: Path | None
    ai_usage_tags: list[str]
    posture_config: list[PostureCapabilityConfig]
    test_coverage_data: dict
    technical_debt_path: Path | None
    innovation_path: Path | None
    innovation_colors: dict[str, str]
    one_page_max_depth: int | None
    one_page_hub_threshold: int | None
    index_card_visibility: IndexCardVisibility
    language: str
    log: LogCallback
    alias: str
    include_comparison: bool
    comparison_target: str
