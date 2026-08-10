"""Listing pages for custom objects and custom fields (Description tab)."""

from __future__ import annotations

from pathlib import Path

from src.core.models import MetadataSnapshot
from src.core.utils import html_value
from src.reporting.html.page_shell import href_relative, index_back_link
from src.reporting.html.renderers.listing_tables import LogCallback, _table, _write


def write_objects_list_page(
    snapshot: MetadataSnapshot,
    object_pages: dict[str, Path],
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
) -> Path | None:
    """List all custom objects. Returns None when there are none."""
    custom_objects = [o for o in snapshot.objects if o.custom]
    if not custom_objects:
        return None

    path = output_dir / "objects_list.html"
    back = index_back_link(path, output_dir)

    rows = []
    for obj in sorted(custom_objects, key=lambda o: o.api_name.lower()):
        page = object_pages.get(obj.api_name)
        name_cell = (
            f"<a href='{href_relative(path, page)}'>{html_value(obj.api_name)}</a>"
            if page
            else html_value(obj.api_name)
        )
        vr_count = len(obj.validation_rules)
        vr_complexity = sum(vr.complexity_score for vr in obj.validation_rules)
        vr_cell = f"{vr_count} (Σ={vr_complexity})" if vr_count else "0"
        
        rows.append(
            f"<tr>"
            f"<td>{name_cell}</td>"
            f"<td>{html_value(obj.label)}</td>"
            f"<td>{sum(1 for f in obj.fields if f.custom)}</td>"
            f"<td>{len(obj.record_types)}</td>"
            f"<td>{vr_cell}</td>"
            f"<td>{html_value(obj.description)}</td>"
            f"</tr>"
        )

    vr_header = (
        '<span title="Nombre de règles de validation et score de complexité cumulé (Σ). '
        'Le score est calculé selon la longueur de la formule (1pt par 50 car.) '
        'et le nombre d\'opérateurs logiques (IF, AND, OR, CASE, parenthèses).">'
        'VR (Complexité)</span>'
    )
    table = _table(
        ["API Name", "Label", "Champs custom", "Record Types", vr_header, "Description"],
        rows,
    )
    body = f"{back}<h1>Objets custom ({len(custom_objects)})</h1>{table}"
    _write(path, "Objets custom", body, assets_dir)
    log(f"Page liste objets générée : {path}")
    return path


def write_fields_list_page(
    snapshot: MetadataSnapshot,
    object_pages: dict[str, Path],
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
) -> Path | None:
    """List all custom fields grouped by object. Returns None when there are none."""
    objects_with_custom_fields = [
        o for o in snapshot.objects if any(f.custom for f in o.fields)
    ]
    if not objects_with_custom_fields:
        return None

    path = output_dir / "fields_list.html"
    back = index_back_link(path, output_dir)

    sections: list[str] = []
    for obj in sorted(objects_with_custom_fields, key=lambda o: o.api_name.lower()):
        custom_fields = [f for f in obj.fields if f.custom]
        page = object_pages.get(obj.api_name)
        obj_label = (
            f"<a href='{href_relative(path, page)}'>{html_value(obj.api_name)}</a>"
            if page
            else html_value(obj.api_name)
        )
        rows = [
            f"<tr>"
            f"<td>{html_value(f.api_name)}</td>"
            f"<td>{html_value(f.label)}</td>"
            f"<td>{html_value(f.data_type)}</td>"
            f"<td>{'Oui' if f.required else ''}</td>"
            f"<td>{html_value(f.description)}</td>"
            f"</tr>"
            for f in sorted(custom_fields, key=lambda f: f.api_name.lower())
        ]
        table = _table(
            ["API Name", "Label", "Type", "Requis", "Description"],
            rows,
        )
        sections.append(
            f"<h2>{obj_label} <small style='font-weight:normal;color:#64748b;'>"
            f"({len(custom_fields)} champ(s))</small></h2>{table}"
        )

    total = sum(
        sum(1 for f in o.fields if f.custom) for o in snapshot.objects
    )
    body = f"{back}<h1>Champs custom ({total})</h1>{''.join(sections)}"
    _write(path, "Champs custom", body, assets_dir)
    log(f"Page liste champs générée : {path}")
    return path
