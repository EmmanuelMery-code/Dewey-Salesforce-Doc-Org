"""Render the main ``index.html`` documentation home page."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from src.core.ai_usage import AIUsageEntry, AIUsageStats
from src.core.customization_metrics import (
    AdoptionStats,
    DataModelCustomisationStats,
)
from src.core.index_card_visibility import IndexCardVisibility
from src.core.models import (
    MetadataSnapshot,
    PmdViolation,
    ReviewResult,
)
from src.core.utils import html_value, write_text

from src.reporting.html.page_shell import (
    href_relative,
    render_page,
)
from src.reporting.html.renderers.index_summary_cards import render_index_summary_tabs
from src.reporting.html.renderers.index_tabs import render_index_tabs


LogCallback = Callable[[str], None]


def render_index(
    snapshot: MetadataSnapshot,
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    flow_pages: dict[str, Path],
    apex_reviews: dict[str, ReviewResult],
    flow_reviews: dict[str, ReviewResult],
    pmd_results: dict[str, list[PmdViolation]],
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    omni_pages: dict[str, list[dict[str, object]]],
    agent_pages: dict[str, Path] = None,
    prompt_pages: dict[str, Path] = None,
    listing_pages: dict[str, Path] = None,
    security_pages: dict[str, Path] | None = None,
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
    root_output_dir: Path | None = None,
    alias: str = "",
    comparison_page: Path | None = None,
    comparison_regressions: int | None = None,
) -> str:
    visibility = card_visibility or IndexCardVisibility()
    listing = listing_pages or {}

    # Use the provided root_output_dir or fall back to output_dir's parent if it's named 'html'
    root_dir = root_output_dir
    if root_dir is None:
        if output_dir.name == "html":
            root_dir = output_dir.parent
        else:
            root_dir = output_dir

    tabs = render_index_tabs(
        snapshot,
        object_pages,
        apex_pages,
        flow_pages,
        apex_reviews,
        flow_reviews,
        pmd_results,
        current_path,
        root_dir,
        omni_pages,
        agent_pages,
        prompt_pages,
        security_pages,
        analyzer_report,
    )

    summary_tabs = render_index_summary_tabs(
        snapshot,
        current_path,
        listing,
        visibility,
        analyzer_report,
        findings_report_page,
        ai_usage_stats,
        ai_usage_page,
        data_model_stats,
        customisation_page,
        adoption_stats,
        adoption_page,
        debt_page,
        innovation_page,
        picklists_page,
    )

    comparison_banner = ""
    if comparison_page is not None:
        cmp_rel = href_relative(current_path, comparison_page)
        if comparison_regressions and comparison_regressions > 0:
            border, bg, fg = "#d1242f", "#ffebe9", "#d1242f"
            status_txt = f"\u26a0 {comparison_regressions} régression(s) détectée(s)"
        else:
            border, bg, fg = "#1a7f37", "#dafbe1", "#1a7f37"
            status_txt = "\u2713 Aucune régression détectée"
        comparison_banner = (
            f'<div style="border-left:6px solid {border}; background:{bg}; '
            f'padding:12px 16px; border-radius:6px; margin:12px 0; display:flex; '
            f'align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap;">'
            f'<span><b>Comparaison avec une génération précédente</b> — '
            f'<span style="color:{fg}; font-weight:600;">{status_txt}</span></span>'
            f'<a href="{cmp_rel}" style="color:{fg}; font-weight:600; text-decoration:none;">'
            f'Voir la comparaison détaillée \u2192</a>'
            f'</div>\n'
        )

    title_suffix = f" : {html_value(alias)}" if alias else ""
    source_rel = href_relative(current_path, snapshot.source_dir)
    output_rel = href_relative(current_path, root_dir)
    body = f"""
<h1>Documentation Salesforce{title_suffix} ({date.today().isoformat()})</h1>
<p>Source analysee: <code>{html_value(source_rel)}</code></p>
<p>Dossier de sortie: <code>{html_value(output_rel)}</code></p>
{comparison_banner}
{summary_tabs}
{tabs}
"""
    return render_page("Index", body, current_path, assets_dir, include_mermaid=False)


def write_index(
    snapshot: MetadataSnapshot,
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    flow_pages: dict[str, Path],
    apex_reviews: dict[str, ReviewResult],
    flow_reviews: dict[str, ReviewResult],
    pmd_results: dict[str, list[PmdViolation]],
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
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
    root_output_dir: Path | None = None,
    alias: str = "",
    comparison_page: Path | None = None,
    comparison_regressions: int | None = None,
) -> Path:
    path = output_dir / "index.html"
    write_text(
        path,
        render_index(
            snapshot,
            object_pages,
            apex_pages,
            flow_pages,
            apex_reviews,
            flow_reviews,
            pmd_results,
            path,
            output_dir,
            assets_dir,
            omni_pages or {},
            agent_pages or {},
            prompt_pages or {},
            listing_pages or {},
            security_pages or {},
            analyzer_report,
            ai_usage_entries=ai_usage_entries,
            ai_usage_page=ai_usage_page,
            ai_usage_stats=ai_usage_stats,
            data_model_stats=data_model_stats,
            adoption_stats=adoption_stats,
            customisation_page=customisation_page,
            adoption_page=adoption_page,
            findings_report_page=findings_report_page,
            debt_page=debt_page,
            innovation_page=innovation_page,
            picklists_page=picklists_page,
            card_visibility=card_visibility,
            root_output_dir=root_output_dir,
            alias=alias,
            comparison_page=comparison_page,
            comparison_regressions=comparison_regressions,
        ),
    )
    log(f"Index genere: {path}")
    return path
