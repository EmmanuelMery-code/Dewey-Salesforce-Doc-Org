"""Printable A4 dashboard renderer for a selected history entry."""

from __future__ import annotations

from pathlib import Path

from src.core.history_service import HistoryEntry
from src.core.utils import html_value
from src.reporting.html.page_shell import href_relative
from src.reporting.html.renderers.history_reports.dashboard_evolution import (
    build_evolution_charts,
)
from src.reporting.html.renderers.history_reports.dashboard_html import (
    build_dashboard_content,
)


def render_dashboard(
    selected: HistoryEntry,
    history: list[HistoryEntry],
    current_path: Path,
    assets_dir: Path,
) -> str:
    """Render a printable A4 dashboard with current status and evolution trend."""

    # Calculations for Status (Selected Generation)
    adoption_pct = selected.adoption_pct
    adaptation_pct = selected.adaptation_pct
    dm_standard_pct = selected.data_model_standard_pct
    dm_custom_pct = selected.data_model_custom_pct
    ai_with_pct = selected.ai_usage_pct
    ai_without_pct = 100.0 - ai_with_pct

    # Findings totals
    f_total = selected.findings_total
    f_crit = selected.findings_critical
    f_maj = selected.findings_major
    f_min = selected.findings_minor
    f_inf = selected.findings_info

    # Max finding for bar scaling
    max_f = max(f_crit, f_maj, f_min, f_inf, 1)

    # Test Coverage
    test_coverage = selected.test_coverage
    test_coverage_pct = test_coverage if test_coverage is not None else 0.0

    # Evolution data: sort history by generation number ascending
    sorted_history = sorted(history, key=lambda e: e.generation_number)

    # Heuristic: if we have more than 5 releases, the tables might make the page too long
    # especially when printing on A4.
    show_evolution_tables = len(sorted_history) <= 5

    evolution = build_evolution_charts(sorted_history, show_evolution_tables)

    html_content = build_dashboard_content(
        selected,
        current_path,
        adoption_pct=adoption_pct,
        adaptation_pct=adaptation_pct,
        dm_standard_pct=dm_standard_pct,
        dm_custom_pct=dm_custom_pct,
        ai_with_pct=ai_with_pct,
        ai_without_pct=ai_without_pct,
        f_total=f_total,
        f_crit=f_crit,
        f_maj=f_maj,
        f_min=f_min,
        f_inf=f_inf,
        max_f=max_f,
        test_coverage_pct=test_coverage_pct,
        evolution=evolution,
    )

    # We use a custom shell for the dashboard to avoid the standard page overhead
    style_href = href_relative(current_path, assets_dir / "style.css")
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Dashboard {html_value(selected.alias)}</title>
    <link rel="stylesheet" href="{style_href}">
    <style>
        @page {{ size: A4; margin: 0; }}
        body {{ margin: 0; padding: 0; background: #f0f2f5; }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""
