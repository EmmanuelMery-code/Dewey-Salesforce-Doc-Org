"""Structured payload returned by the documentation generator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.analyzer.engine import AnalyzerReport
from src.core.ai_usage import AIUsageEntry, AIUsageStats
from src.core.customization_metrics import (
    AdoptionStats,
    DataModelCustomisationStats,
    SelectedUsageStats,
)
from src.core.models import MetadataSnapshot


@dataclass
class GenerationResult:
    """Structured payload returned by :meth:`SalesforceDocumentationGenerator.generate`.

    Every field is optional because the user can disable individual outputs
    (Excel, HTML, Word). Callers should check for ``None`` / empty mappings
    before reading.
    """

    snapshot: MetadataSnapshot | None = None
    analyzer_report: AnalyzerReport | None = None
    #: Org alias the run was filed under, so the caller stores its outcome
    #: where the run read its own history from.
    alias: str = ""
    permission_excel: Path | None = None
    profile_excel: Path | None = None
    inventory_excel: Path | None = None
    data_dictionary_excels: list[Path] = field(default_factory=list)
    selected_data_dictionary_excels: list[Path] = field(default_factory=list)
    findings_excel: Path | None = None
    picklists_excel: Path | None = None
    psg_summary_excel: Path | None = None
    pmd_excel: Path | None = None
    data_dictionary_word: Path | None = None
    summary_word: Path | None = None
    sarif_path: Path | None = None
    data_model_drawio: Path | None = None
    index: Path | None = None
    ai_usage_page: Path | None = None
    ai_usage_entries: list[AIUsageEntry] = field(default_factory=list)
    ai_usage_stats: AIUsageStats | None = None
    data_model_stats: DataModelCustomisationStats | None = None
    #: ``None`` when the Data Dictionary screen holds no object selection.
    selected_usage_stats: SelectedUsageStats | None = None
    adoption_stats: AdoptionStats | None = None
    customisation_page: Path | None = None
    adoption_page: Path | None = None
    debt_page: Path | None = None
    innovation_page: Path | None = None
    picklists_page: Path | None = None
    methodology_page: Path | None = None
    findings_report_page: Path | None = None
    object_pages: dict = field(default_factory=dict)
    apex_pages: dict = field(default_factory=dict)
    flow_pages: dict = field(default_factory=dict)
    omni_pages: dict = field(default_factory=dict)
    agent_pages: dict = field(default_factory=dict)
    prompt_pages: dict = field(default_factory=dict)
    listing_pages: dict = field(default_factory=dict)
    security_pages: dict = field(default_factory=dict)
    excel_preview_pages: dict = field(default_factory=dict)

    # The UI historically consumed this object via ``result["index"]``-style
    # subscripts. The two helpers below keep that contract working without
    # forcing every existing call site to migrate at once.
    def __getitem__(self, item: str):
        return getattr(self, item)

    def get(self, item: str, default=None):
        return getattr(self, item, default)
