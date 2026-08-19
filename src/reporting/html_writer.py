"""Public facade over the ``src.reporting.html`` package.

The orchestrator instantiates :class:`HtmlReportWriter` and calls a handful
of ``write_*`` methods. Historically all of the rendering logic lived in
this module (~2,100 lines mixing CSS, JS runtimes, Mermaid helpers,
dependency analysis and per-page renderers). It has now been split into
the focused modules under ``src.reporting.html``; this file simply
forwards the public API so existing callers keep working unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.core.ai_usage import AIUsageEntry, AIUsageStats
from src.core.customization_metrics import (
    AdoptionStats,
    DataModelCustomisationStats,
    PostureCapabilityConfig,
)
from src.core.index_card_visibility import IndexCardVisibility
from src.core.models import (
    MetadataSnapshot,
    PmdViolation,
    ReviewResult,
)

from src.reporting.html import assets
from src.reporting.html.renderers import (
    adoption as adoption_renderer,
    ai_usage as ai_usage_renderer,
    apex as apex_renderer,
    customisation as customisation_renderer,
    debt as debt_renderer,
    excel_preview as excel_preview_renderer,
    findings_report as findings_report_renderer,
    flows as flows_renderer,
    ai_components as ai_components_renderer,
    innovation as innovation_renderer,
    index as index_renderer,
    listing as listing_renderer,
    methodology as methodology_renderer,
    objects as objects_renderer,
    omni as omni_renderer,
    picklists as picklists_renderer,
    security as security_renderer,
    security_matrix as security_matrix_renderer,
    psg as psg_renderer,
)


LogCallback = Callable[[str], None]


class HtmlReportWriter:
    """Write the static HTML documentation site.

    The class owns the shared output directory layout (``assets/``,
    ``objects/``, ``apex/``, ``flows/``, ``omni/``) and exposes a small
    set of ``write_*`` methods that emit one HTML page per
    object/class/trigger/flow/Omni component plus the home page. Every
    method delegates to a focused renderer module under
    ``src.reporting.html``; this class only wires paths and log callback
    together.
    """

    def __init__(
        self,
        output_dir: str | Path,
        log_callback: LogCallback | None = None,
    ) -> None:
        self.root_output_dir = Path(output_dir)
        self.output_dir = self.root_output_dir / "html"
        self.log: LogCallback = log_callback or (lambda message: None)
        self.assets_dir = self.output_dir / "assets"
        self.objects_dir = self.output_dir / "objects"
        self.apex_dir = self.output_dir / "apex"
        self.flows_dir = self.output_dir / "flows"
        self.omni_dir = self.output_dir / "omni"
        self.agents_dir = self.output_dir / "agents"
        self.prompts_dir = self.output_dir / "prompts"

    def write_assets(self) -> None:
        assets.write_assets(self.assets_dir)

    def write_object_pages(
        self,
        snapshot: MetadataSnapshot,
        *,
        analyzer_report=None,
        apex_pages: dict[str, Path] | None = None,
        flow_pages: dict[str, Path] | None = None,
        include_comment: bool = True,
        include_piloted_by: bool = True,
        include_status: bool = True,
        include_squad: bool = True,
        concat_description: bool = True,
    ) -> dict[str, Path]:
        return objects_renderer.write_object_pages(
            snapshot,
            self.objects_dir,
            self.output_dir,
            self.assets_dir,
            self.log,
            analyzer_report=analyzer_report,
            apex_pages=apex_pages,
            flow_pages=flow_pages,
            include_comment=include_comment,
            include_piloted_by=include_piloted_by,
            include_status=include_status,
            include_squad=include_squad,
            concat_description=concat_description,
        )

    def write_combined_data_dictionary_html(
        self,
        snapshot: MetadataSnapshot,
        output_path: Path,
        *,
        analyzer_report=None,
        include_comment: bool = True,
        include_piloted_by: bool = True,
        include_status: bool = True,
        include_squad: bool = True,
        concat_description: bool = True,
    ) -> Path:
        content = objects_renderer.render_combined_objects_page(
            snapshot,
            output_path,
            self.output_dir,
            self.assets_dir,
            analyzer_report=analyzer_report,
            include_comment=include_comment,
            include_piloted_by=include_piloted_by,
            include_status=include_status,
            include_squad=include_squad,
            concat_description=concat_description,
        )
        from src.core.utils import write_text
        write_text(output_path, content)
        self.log(f"Data Dictionary HTML combine genere : {output_path}")
        return output_path

    def write_apex_pages(
        self,
        snapshot: MetadataSnapshot,
        reviews: dict[str, ReviewResult],
        pmd_results: dict[str, list[PmdViolation]],
        *,
        analyzer_report=None,
    ) -> dict[str, Path]:
        return apex_renderer.write_apex_pages(
            snapshot,
            reviews,
            pmd_results,
            self.apex_dir,
            self.output_dir,
            self.assets_dir,
            self.log,
            analyzer_report=analyzer_report,
        )

    def write_flow_pages(
        self,
        snapshot: MetadataSnapshot,
        reviews: dict[str, ReviewResult],
        object_pages: dict[str, Path],
        apex_pages: dict[str, Path],
        *,
        analyzer_report=None,
    ) -> dict[str, Path]:
        return flows_renderer.write_flow_pages(
            snapshot,
            reviews,
            object_pages,
            apex_pages,
            self.flows_dir,
            self.output_dir,
            self.assets_dir,
            self.log,
            analyzer_report=analyzer_report,
        )

    def write_omni_pages(
        self,
        snapshot: MetadataSnapshot,
        *,
        analyzer_report=None,
    ) -> dict[str, list[dict[str, object]]]:
        return omni_renderer.write_omni_pages(
            snapshot,
            self.omni_dir,
            self.output_dir,
            self.assets_dir,
            self.log,
            analyzer_report=analyzer_report,
        )

    def write_ai_pages(
        self,
        snapshot: MetadataSnapshot,
        *,
        analyzer_report=None,
    ) -> tuple[dict[str, Path], dict[str, Path]]:
        return ai_components_renderer.write_ai_pages(
            snapshot,
            self.agents_dir,
            self.prompts_dir,
            self.output_dir,
            self.assets_dir,
            self.log,
            analyzer_report=analyzer_report,
        )

    def write_findings_report_page(
        self,
        analyzer_report,
        object_pages: dict[str, Path],
        apex_pages: dict[str, Path],
        flow_pages: dict[str, Path],
        agent_pages: dict[str, Path] | None = None,
        prompt_pages: dict[str, Path] | None = None,
        omni_pages: dict[str, list[dict[str, object]]] | None = None,
    ) -> Path:
        return findings_report_renderer.write_findings_report_page(
            analyzer_report,
            self.output_dir,
            self.assets_dir,
            self.log,
            object_pages,
            apex_pages,
            flow_pages,
            agent_pages=agent_pages,
            prompt_pages=prompt_pages,
            omni_pages=omni_pages,
        )

    def write_excel_preview_pages(self) -> dict[Path, Path]:
        return excel_preview_renderer.write_excel_preview_pages(
            self.root_output_dir,
            self.assets_dir,
            self.log,
        )

    def write_ai_usage_page(
        self,
        entries: list[AIUsageEntry],
        *,
        tags: list[str] | None = None,
        stats: AIUsageStats | None = None,
    ) -> Path:
        return ai_usage_renderer.write_ai_usage_page(
            entries,
            self.output_dir,
            self.assets_dir,
            self.log,
            tags=tags,
            stats=stats,
        )

    def write_customisation_page(
        self,
        snapshot: MetadataSnapshot,
        stats: DataModelCustomisationStats | None,
    ) -> Path:
        return customisation_renderer.write_customisation_page(
            snapshot,
            stats,
            self.output_dir,
            self.assets_dir,
            self.log,
        )

    def write_adoption_page(
        self,
        snapshot: MetadataSnapshot,
        stats: AdoptionStats | None,
    ) -> Path:
        return adoption_renderer.write_adoption_page(
            snapshot,
            stats,
            self.output_dir,
            self.assets_dir,
            self.log,
        )

    def write_methodology_page(
        self,
        posture_config: list[PostureCapabilityConfig] | None = None,
        data_model_thresholds: tuple[int, int, int] | None = None,
        profiles_thresholds: tuple[int, int, int] | None = None,
    ) -> Path:
        from src.core.models import DEFAULT_DATA_MODEL_THRESHOLDS, DEFAULT_PROFILES_THRESHOLDS

        return methodology_renderer.write_methodology_page(
            self.output_dir,
            self.assets_dir,
            self.log,
            posture_config=posture_config,
            data_model_thresholds=data_model_thresholds or DEFAULT_DATA_MODEL_THRESHOLDS,
            profiles_thresholds=profiles_thresholds or DEFAULT_PROFILES_THRESHOLDS,
        )

    def write_debt_page(
        self,
        snapshot: MetadataSnapshot,
    ) -> Path:
        return debt_renderer.write_debt_page(
            snapshot,
            self.output_dir,
            self.assets_dir,
            self.log,
        )

    def write_innovation_page(
        self,
        snapshot: MetadataSnapshot,
    ) -> Path:
        return innovation_renderer.write_innovation_page(
            snapshot,
            self.output_dir,
            self.assets_dir,
            self.log,
        )

    def write_picklists_page(
        self,
        snapshot: MetadataSnapshot,
    ) -> Path:
        return picklists_renderer.write_picklists_page(
            snapshot,
            self.output_dir,
            self.assets_dir,
            self.log,
        )

    def write_listing_pages(
        self,
        snapshot: MetadataSnapshot,
        object_pages: dict[str, Path],
        apex_pages: dict[str, Path],
        flow_pages: dict[str, Path],
        omni_pages: dict[str, list[dict[str, object]]],
        agent_pages: dict[str, Path],
        prompt_pages: dict[str, Path],
    ) -> dict[str, Path]:
        return listing_renderer.write_listing_pages(
            snapshot,
            object_pages,
            apex_pages,
            flow_pages,
            omni_pages,
            agent_pages,
            prompt_pages,
            self.output_dir,
            self.assets_dir,
            self.log,
        )

    def write_security_pages(
        self,
        snapshot: MetadataSnapshot,
        analyzer_report=None,
    ) -> dict[str, Path]:
        pages = security_renderer.write_security_pages(
            snapshot,
            self.output_dir,
            self.assets_dir,
            self.log,
            analyzer_report=analyzer_report,
        )
        pages["security_matrix"] = security_matrix_renderer.write_security_matrix_page(
            snapshot, self.output_dir, self.assets_dir
        )
        pages["psg_list"] = psg_renderer.write_psg_list_page(
            snapshot, self.output_dir, self.assets_dir
        )
        return pages

    def write_index(
        self,
        snapshot: MetadataSnapshot,
        object_pages: dict[str, Path],
        apex_pages: dict[str, Path],
        flow_pages: dict[str, Path],
        apex_reviews: dict[str, ReviewResult],
        flow_reviews: dict[str, ReviewResult],
        pmd_results: dict[str, list[PmdViolation]],
        omni_pages: dict[str, list[dict[str, object]]] | None = None,
        agent_pages: dict[str, Path] | None = None,
        prompt_pages: dict[str, Path] | None = None,
        listing_pages: dict[str, Path] | None = None,
        security_pages: dict[str, Path] | None = None,
        *,
        analyzer_report=None,
        ai_usage_entries: list[AIUsageEntry] | None = None,
        ai_usage_page: Path | None = None,
        ai_usage_stats: AIUsageStats | None = None,
        data_model_stats: DataModelCustomisationStats | None = None,
        adoption_stats: AdoptionStats | None = None,
        customisation_page: Path | None = None,
        adoption_page: Path | None = None,
        debt_page: Path | None = None,
        innovation_page: Path | None = None,
        picklists_page: Path | None = None,
        findings_report_page: Path | None = None,
        card_visibility: IndexCardVisibility | None = None,
        alias: str = "",
        comparison_page: Path | None = None,
        comparison_regressions: int | None = None,
    ) -> Path:
        return index_renderer.write_index(
            snapshot,
            object_pages,
            apex_pages,
            flow_pages,
            apex_reviews,
            flow_reviews,
            pmd_results,
            self.output_dir,
            self.assets_dir,
            self.log,
            omni_pages=omni_pages,
            agent_pages=agent_pages,
            prompt_pages=prompt_pages,
            listing_pages=listing_pages,
            security_pages=security_pages,
            analyzer_report=analyzer_report,
            ai_usage_entries=ai_usage_entries,
            ai_usage_page=ai_usage_page,
            ai_usage_stats=ai_usage_stats,
            data_model_stats=data_model_stats,
            adoption_stats=adoption_stats,
            customisation_page=customisation_page,
            adoption_page=adoption_page,
            debt_page=debt_page,
            innovation_page=innovation_page,
            picklists_page=picklists_page,
            findings_report_page=findings_report_page,
            card_visibility=card_visibility,
            root_output_dir=self.root_output_dir,
            alias=alias,
            comparison_page=comparison_page,
            comparison_regressions=comparison_regressions,
        )
