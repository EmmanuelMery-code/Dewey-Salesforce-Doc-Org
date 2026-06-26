"""Render the technical debt and deviations report page."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.core.models import MetadataSnapshot
from src.core.utils import html_value, write_text
from src.reporting.html.page_shell import index_back_link, render_page, tabbed_sections

LogCallback = Callable[[str], None]


def render_debt_page(
    snapshot: MetadataSnapshot,
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
) -> str:
    """Render the technical debt and deviations HTML page."""
    
    back_link = index_back_link(current_path, output_dir, "metriques", "summary-tabs")
    
    # Technical Debt Table
    tech_rows = []
    for item in snapshot.technical_debt:
        tech_rows.append(
            f"<tr>"
            f"<td>{html_value(item.label)}</td>"
            f"<td>{html_value(item.date_creation)}</td>"
            f"<td>{html_value(item.date_resolution)}</td>"
            f"<td style='white-space: pre-wrap;'>{html_value(item.accepted_solution)}</td>"
            f"<td style='white-space: pre-wrap;'>{html_value(item.target_solution)}</td>"
            f"</tr>"
        )
    
    tech_table = (
        "<table><thead><tr><th>Libelle</th><th>Date creation</th><th>Date resolution</th><th>Solution acceptee</th><th>Solution Cible</th></tr></thead>"
        f"<tbody>{''.join(tech_rows) or '<tr><td colspan=\"5\" class=\"empty\">Aucun element de dette technique.</td></tr>'}</tbody></table>"
    )

    # Deviations Table
    dev_rows = []
    for item in snapshot.deviations:
        dev_rows.append(
            f"<tr>"
            f"<td>{html_value(item.label)}</td>"
            f"<td>{html_value(item.date_creation)}</td>"
            f"<td style='white-space: pre-wrap;'>{html_value(item.explanation)}</td>"
            f"</tr>"
        )
    
    dev_table = (
        "<table><thead><tr><th>Libelle</th><th>Date creation</th><th>Explication</th></tr></thead>"
        f"<tbody>{''.join(dev_rows) or '<tr><td colspan=\"3\" class=\"empty\">Aucune entorse et point remarquable.</td></tr>'}</tbody></table>"
    )

    tabs = tabbed_sections("debt-tabs", [
        (f"Dette technique ({len(snapshot.technical_debt)})", tech_table),
        (f"Entorses et PR ({len(snapshot.deviations)})", dev_table)
    ])

    body = f"""
{back_link}
<h1>Dette technique & Entorses et PR</h1>
{tabs}
"""
    return render_page("Dette technique & Entorses et PR", body, current_path, assets_dir)


def write_debt_page(
    snapshot: MetadataSnapshot,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
) -> Path:
    """Write the debt.html page to disk."""
    path = output_dir / "debt.html"
    content = render_debt_page(snapshot, path, output_dir, assets_dir)
    write_text(path, content)
    log(f"Page dette technique generee: {path}")
    return path
