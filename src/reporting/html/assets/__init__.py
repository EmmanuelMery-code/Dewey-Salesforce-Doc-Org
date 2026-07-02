"""Static assets used by the HTML documentation site.

This package was split from a single ``assets.py`` module for readability.
It holds the CSS, the Mermaid runtime ``<script>`` block embedded in every
page header, and the JavaScript that drives tab activation. Every public
name is re-exported here so existing imports keep working unchanged.
"""

from __future__ import annotations

from pathlib import Path

from src.core.utils import write_text
from src.reporting.html.assets.scripts import (
    MERMAID_RUNTIME_SCRIPT,
    SEARCH_SCRIPT,
    TABS_SCRIPT,
)
from src.reporting.html.assets.styles import DASHBOARD_CSS, MAIN_CSS


SEVERITY_CSS_CLASS: dict[str, str] = {
    "Critical": "sev-critical",
    "Major": "sev-major",
    "Minor": "sev-minor",
    "Info": "sev-info",
}

SEVERITY_LABEL: dict[str, str] = {
    "Critical": "Critique",
    "Major": "Majeur",
    "Minor": "Mineur",
    "Info": "Info",
}


def write_assets(assets_dir: Path) -> None:
    """Write the static stylesheets to ``assets_dir``."""

    write_text(assets_dir / "style.css", MAIN_CSS)
    write_text(assets_dir / "dashboard.css", DASHBOARD_CSS)


__all__ = [
    "DASHBOARD_CSS",
    "MAIN_CSS",
    "MERMAID_RUNTIME_SCRIPT",
    "SEARCH_SCRIPT",
    "SEVERITY_CSS_CLASS",
    "SEVERITY_LABEL",
    "TABS_SCRIPT",
    "write_assets",
]
