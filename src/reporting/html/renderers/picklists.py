"""Render the picklist fields inventory report page."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.core.models import MetadataSnapshot
from src.core.utils import html_value, write_text
from src.reporting.html.page_shell import index_back_link, render_page

LogCallback = Callable[[str], None]

_PICKLIST_TYPES = ("Picklist", "MultiselectPicklist")


def render_picklists_page(
    snapshot: MetadataSnapshot,
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
) -> str:
    """Render the picklist fields inventory HTML page."""

    back_link = index_back_link(current_path, output_dir, "metriques", "summary-tabs")

    rows: list[str] = []
    for obj in snapshot.objects:
        for item in obj.fields:
            if item.data_type not in _PICKLIST_TYPES:
                continue
            values_str = " | ".join(item.picklist_values) if item.picklist_values else "-"
            rows.append(
                "<tr>"
                f"<td>{html_value(obj.api_name)}</td>"
                f"<td>{html_value(item.api_name)}</td>"
                f"<td>{html_value(item.data_type)}</td>"
                f"<td>{'Oui' if item.picklist_is_global else 'Non'}</td>"
                f"<td>{html_value(item.picklist_global_name or '-')}</td>"
                f"<td style='white-space: pre-wrap;'>{html_value(values_str)}</td>"
                "</tr>"
            )

    table = (
        "<table><thead><tr>"
        "<th>Objet</th><th>Champ</th><th>Type</th>"
        "<th>Picklist Globale ?</th><th>Nom Picklist Globale</th><th>Valeurs</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows) or '<tr><td colspan=\"6\" class=\"empty\">Aucun champ Picklist detecte.</td></tr>'}</tbody></table>"
    )

    body = f"""
{back_link}
<h1>Champs Picklist ({len(rows)})</h1>
<p>Inventaire des champs de type Picklist et Picklist a valeurs multiples, avec resolution des Global Value Sets.</p>
{table}
"""
    return render_page("Champs Picklist", body, current_path, assets_dir)


def write_picklists_page(
    snapshot: MetadataSnapshot,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
) -> Path:
    """Write the picklists.html page to disk."""
    path = output_dir / "picklists.html"
    content = render_picklists_page(snapshot, path, output_dir, assets_dir)
    write_text(path, content)
    log(f"Page champs picklist generee: {path}")
    return path
