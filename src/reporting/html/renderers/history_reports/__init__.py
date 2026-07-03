"""Renderer for history-based reports (dashboards and comparisons).

This package was split from a single ``history_reports.py`` module for
readability. Public names are re-exported so existing
``from src.reporting.html.renderers.history_reports import X`` imports
keep working.
"""

from __future__ import annotations

from pathlib import Path

from src.core.history_service import HistoryEntry
from src.core.utils import write_text
from src.reporting.html.assets import write_assets

from src.reporting.html.renderers.history_reports.comparison import (
    comparison_regression_count,
    render_comparison,
)
from src.reporting.html.renderers.history_reports.dashboard import render_dashboard


def write_history_report(
    entry: HistoryEntry,
    report_type: str,
    content: str,
    filename: str,
) -> Path:
    """Write a history report to the output directory of the entry."""
    app_root = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
    output_dir = Path(entry.output_dir)
    if not output_dir.is_absolute():
        output_dir = app_root / output_dir

    output_dir = output_dir / "html"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Ensure assets are present
    write_assets(output_dir / "assets")

    path = output_dir / filename
    write_text(path, content)
    return path


__all__ = [
    "comparison_regression_count",
    "render_comparison",
    "render_dashboard",
    "write_history_report",
]
