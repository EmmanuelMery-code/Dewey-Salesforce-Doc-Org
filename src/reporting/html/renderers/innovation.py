"""Render the POC and innovations report page."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.core.models import MetadataSnapshot
from src.core.utils import html_value, write_text
from src.reporting.html.page_shell import index_back_link, render_page

LogCallback = Callable[[str], None]


def render_innovation_page(
    snapshot: MetadataSnapshot,
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
) -> str:
    """Render the POC and innovations HTML page."""
    
    back_link = index_back_link(current_path, output_dir, "metriques", "summary-tabs")
    
    started_items = [item for item in snapshot.innovations if not item.not_started]
    not_started_items = [item for item in snapshot.innovations if item.not_started]

    def _render_table(items: list[InnovationItem], empty_msg: str) -> str:
        rows = []
        for item in items:
            rows.append(
                f"<tr>"
                f"<td>{html_value(item.label)}</td>"
                f"<td>{html_value(item.theme)}</td>"
                f"<td>{html_value(item.date_start)}</td>"
                f"<td>{html_value(item.date_end)}</td>"
                f"<td>{html_value(item.date_presentation)}</td>"
                f"<td style='white-space: pre-wrap;'>{html_value(item.description)}</td>"
                f"<td style='white-space: pre-wrap;'>{html_value(item.conclusion)}</td>"
                f"</tr>"
            )
        
        return (
            "<table><thead><tr>"
            "<th>Libelle</th>"
            "<th>Theme</th>"
            "<th>Date debut</th>"
            "<th>Date fin</th>"
            "<th>Date presentation</th>"
            "<th>Description</th>"
            "<th>Conclusion</th>"
            "</tr></thead>"
            f"<tbody>{''.join(rows) or f'<tr><td colspan=\"7\" class=\"empty\">{empty_msg}</td></tr>'}</tbody></table>"
        )

    table_started = _render_table(started_items, "Aucun POC ou innovation en cours ou termine.")
    table_not_started = _render_table(not_started_items, "Aucun POC ou innovation non commence.")

    body = f"""
{back_link}
<h1>POC et Innovations ({len(snapshot.innovations)})</h1>

<div class="section">
    <h2>En cours ou Terminés ({len(started_items)})</h2>
    {table_started}
</div>

<div class="section">
    <h2>Non Commencés ({len(not_started_items)})</h2>
    {table_not_started}
</div>
"""
    return render_page("POC et Innovations", body, current_path, assets_dir)


def write_innovation_page(
    snapshot: MetadataSnapshot,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
) -> Path:
    """Write the innovations.html page to disk."""
    path = output_dir / "innovations.html"
    content = render_innovation_page(snapshot, path, output_dir, assets_dir)
    write_text(path, content)
    log(f"Page POC et innovations generee: {path}")
    return path
