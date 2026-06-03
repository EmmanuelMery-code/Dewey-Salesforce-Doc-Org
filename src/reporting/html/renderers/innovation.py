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
    
    back_link = index_back_link(current_path, output_dir)
    
    rows = []
    for item in snapshot.innovations:
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
    
    table = (
        "<table><thead><tr>"
        "<th>Libelle</th>"
        "<th>Theme</th>"
        "<th>Date debut</th>"
        "<th>Date fin</th>"
        "<th>Date presentation</th>"
        "<th>Description</th>"
        "<th>Conclusion</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows) or '<tr><td colspan=\"7\" class=\"empty\">Aucun POC ou innovation repertorie.</td></tr>'}</tbody></table>"
    )

    body = f"""
{back_link}
<h1>POC et Innovations ({len(snapshot.innovations)})</h1>

<div class="section">
    {table}
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
