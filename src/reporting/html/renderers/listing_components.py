"""Listing pages for LWC, Aura components and Duplicate Rules."""

from __future__ import annotations

from pathlib import Path

from src.core.models import MetadataSnapshot
from src.core.utils import html_value
from src.reporting.html.page_shell import index_back_link
from src.reporting.html.renderers.listing_tables import LogCallback, _table, _write


def write_lwc_list_page(
    snapshot: MetadataSnapshot,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
) -> Path | None:
    if not snapshot.lwc:
        return None

    path = output_dir / "lwc_list.html"
    back = index_back_link(path, output_dir)

    rows = []
    for lwc in sorted(snapshot.lwc, key=lambda x: x.name.lower()):
        rows.append(
            f"<tr>"
            f"<td>{html_value(lwc.name)}</td>"
            f"<td>{html_value(lwc.label)}</td>"
            f"<td>{lwc.line_count_js}</td>"
            f"<td>{lwc.line_count_html}</td>"
            f"<td>{'Oui' if lwc.has_aura_enabled else 'Non'}</td>"
            f"<td>{', '.join(lwc.targets)}</td>"
            f"</tr>"
        )

    table = _table(["Nom", "Label", "Lignes JS", "Lignes HTML", "@AuraEnabled", "Cibles"], rows)
    body = f"{back}<h1>Lightning Web Components ({len(snapshot.lwc)})</h1>{table}"
    _write(path, "LWC", body, assets_dir)
    log(f"Page liste LWC générée : {path}")
    return path


def write_aura_list_page(
    snapshot: MetadataSnapshot,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
) -> Path | None:
    if not snapshot.aura:
        return None

    path = output_dir / "aura_list.html"
    back = index_back_link(path, output_dir)

    rows = []
    for aura in sorted(snapshot.aura, key=lambda x: x.name.lower()):
        rows.append(
            f"<tr>"
            f"<td>{html_value(aura.name)}</td>"
            f"<td>{aura.line_count_cmp}</td>"
            f"<td>{aura.line_count_js}</td>"
            f"<td>{html_value(aura.api_version)}</td>"
            f"</tr>"
        )

    table = _table(["Nom", "Lignes CMP", "Lignes JS", "API Version"], rows)
    body = f"{back}<h1>Composants Aura ({len(snapshot.aura)})</h1>{table}"
    _write(path, "Aura", body, assets_dir)
    log(f"Page liste Aura générée : {path}")
    return path


def write_duplicate_rules_list_page(
    snapshot: MetadataSnapshot,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
) -> Path | None:
    if not snapshot.duplicate_rules:
        return None

    path = output_dir / "duplicate_rules_list.html"
    back = index_back_link(path, output_dir)

    # Group by object
    by_object: dict[str, list[DuplicateRuleInfo]] = {}
    for rule in snapshot.duplicate_rules:
        by_object.setdefault(rule.object_name, []).append(rule)

    sections: list[str] = []
    for obj_name in sorted(by_object.keys(), key=str.lower):
        rules = by_object[obj_name]
        rows = [
            f"<tr>"
            f"<td>{html_value(r.full_name)}</td>"
            f"<td>{html_value(r.action_on_insert)}</td>"
            f"<td>{html_value(r.action_on_update)}</td>"
            f"<td>{'Oui' if r.active else 'Non'}</td>"
            f"</tr>"
            for r in rules
        ]
        table = _table(["Nom", "Action à l'insertion", "Action à la mise à jour", "Actif"], rows)
        sections.append(
            f"<h2>{html_value(obj_name)} <small style='font-weight:normal;color:#64748b;'>"
            f"({len(rules)} règle(s))</small></h2>{table}"
        )

    body = f"{back}<h1>Duplicate Rules ({len(snapshot.duplicate_rules)})</h1>{''.join(sections)}"
    _write(path, "Duplicate Rules", body, assets_dir)
    log(f"Page liste Duplicate Rules générée : {path}")
    return path
