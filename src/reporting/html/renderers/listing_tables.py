"""Shared helpers for the Description-tab listing pages.

Provides the small table-rendering and page-writing helpers used by every
``listing_*`` module, plus the common ``LogCallback`` type alias.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.core.utils import write_text
from src.reporting.html.page_shell import render_page


LogCallback = Callable[[str], None]


def _table(headers: list[str], rows: list[str], empty_msg: str = "Aucun élément.") -> str:
    ths = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join(rows) or f"<tr><td colspan='{len(headers)}' class='empty'>{empty_msg}</td></tr>"
    return f"<table><thead><tr>{ths}</tr></thead><tbody>{body}</tbody></table>"


def _write(path: Path, title: str, body: str, assets_dir: Path) -> None:
    write_text(path, render_page(title, body, path, assets_dir, include_mermaid=False))
