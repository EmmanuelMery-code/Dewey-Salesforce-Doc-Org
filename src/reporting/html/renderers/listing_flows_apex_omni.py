"""Listing pages for Flows, Apex classes/triggers and OmniStudio components."""

from __future__ import annotations

from pathlib import Path

from src.core.models import MetadataSnapshot
from src.core.utils import html_value
from src.reporting.html.page_shell import href_relative, index_back_link
from src.reporting.html.renderers.listing_tables import LogCallback, _table, _write


def write_flows_list_page(
    snapshot: MetadataSnapshot,
    flow_pages: dict[str, Path],
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
) -> Path | None:
    if not snapshot.flows:
        return None

    path = output_dir / "flows_list.html"
    back = index_back_link(path, output_dir)

    rows = []
    for flow in sorted(snapshot.flows, key=lambda f: (f.name or "").lower()):
        page = flow_pages.get(flow.name)
        name_cell = (
            f"<a href='{href_relative(path, page)}'>{html_value(flow.name)}</a>"
            if page
            else html_value(flow.name)
        )
        rows.append(
            f"<tr>"
            f"<td>{name_cell}</td>"
            f"<td>{html_value(flow.label)}</td>"
            f"<td>{html_value(flow.process_type)}</td>"
            f"<td>{html_value(flow.status)}</td>"
            f"<td>{html_value(flow.start_object)}</td>"
            f"<td>{html_value(flow.description)}</td>"
            f"</tr>"
        )

    table = _table(
        ["Nom", "Label", "Type", "Statut", "Objet", "Description"],
        rows,
    )
    body = f"{back}<h1>Flows ({len(snapshot.flows)})</h1>{table}"
    _write(path, "Flows", body, assets_dir)
    log(f"Page liste flows générée : {path}")
    return path


def write_apex_list_page(
    snapshot: MetadataSnapshot,
    apex_pages: dict[str, Path],
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
) -> Path | None:
    apex = snapshot.apex_artifacts
    if not apex:
        return None

    path = output_dir / "apex_list.html"
    back = index_back_link(path, output_dir)

    classes = sorted(
        [a for a in apex if a.kind == "class"],
        key=lambda a: a.name.lower(),
    )
    triggers = sorted(
        [a for a in apex if a.kind == "trigger"],
        key=lambda a: a.name.lower(),
    )
    # Split classes into test classes and "business" classes (neither a
    # trigger nor a test class) so each population can be counted separately.
    test_classes = [a for a in classes if getattr(a, "is_test", False)]
    business_classes = [a for a in classes if not getattr(a, "is_test", False)]

    def _rows(artifacts):
        result = []
        for art in artifacts:
            page = apex_pages.get(art.name)
            name_cell = (
                f"<a href='{href_relative(path, page)}'>{html_value(art.name)}</a>"
                if page
                else html_value(art.name)
            )
            result.append(
                f"<tr>"
                f"<td>{name_cell}</td>"
                f"<td>{art.line_count}</td>"
                f"<td>{art.method_count}</td>"
                f"<td>{html_value(art.api_version)}</td>"
                f"<td>{html_value(art.status)}</td>"
                f"</tr>"
            )
        return result

    headers = ["Nom", "Lignes", "Méthodes", "API Version", "Statut"]

    def _summary_card(count: int, label: str) -> str:
        return (
            "<div style='flex:1;min-width:160px;padding:12px 16px;border:1px solid #d0d7de;"
            "border-radius:8px;background:#f6f8fa;text-align:center'>"
            f"<div style='font-size:1.8em;font-weight:700'>{count}</div>"
            f"<div style='color:#57606a'>{label}</div>"
            "</div>"
        )

    summary = (
        "<div style='display:flex;gap:12px;flex-wrap:wrap;margin:12px 0 20px 0'>"
        + _summary_card(len(triggers), "Triggers")
        + _summary_card(len(test_classes), "Classes de test")
        + _summary_card(len(business_classes), "Classes hors test / hors trigger")
        + "</div>"
    )

    parts: list[str] = [summary]
    if business_classes:
        parts.append(
            f"<h2>Classes hors test / hors trigger ({len(business_classes)})</h2>"
            f"{_table(headers, _rows(business_classes))}"
        )
    if test_classes:
        parts.append(
            f"<h2>Classes de test ({len(test_classes)})</h2>"
            f"{_table(headers, _rows(test_classes))}"
        )
    if triggers:
        parts.append(
            f"<h2>Triggers Apex ({len(triggers)})</h2>"
            f"{_table(headers, _rows(triggers))}"
        )

    body = f"{back}<h1>Classes &amp; Triggers Apex ({len(apex)})</h1>{''.join(parts)}"
    _write(path, "Classes / Triggers Apex", body, assets_dir)
    log(f"Page liste Apex générée : {path}")
    return path


def write_omni_list_page(
    snapshot: MetadataSnapshot,
    omni_pages: dict[str, list[dict[str, object]]],
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
) -> Path | None:
    if not omni_pages:
        return None

    path = output_dir / "omni_list.html"
    back = index_back_link(path, output_dir)

    sections: list[str] = []
    for category in sorted(omni_pages.keys(), key=str.lower):
        entries = omni_pages[category]
        rows = []
        for entry in entries:
            page_path = entry.get("page")
            name = str(entry.get("name", ""))
            name_cell = (
                f"<a href='{href_relative(path, page_path)}'>{html_value(name)}</a>"
                if isinstance(page_path, Path)
                else html_value(name)
            )
            rows.append(
                f"<tr>"
                f"<td>{name_cell}</td>"
                f"<td>{html_value(str(entry.get('type', '')))}</td>"
                f"<td>{html_value(str(entry.get('source', '')))}</td>"
                f"</tr>"
            )
        table = _table(["Nom", "Type", "Source"], rows)
        sections.append(
            f"<h2>{html_value(category)} ({len(entries)})</h2>{table}"
        )

    total = sum(len(v) for v in omni_pages.values())
    body = f"{back}<h1>Composants OmniStudio ({total})</h1>{''.join(sections)}"
    _write(path, "Composants OmniStudio", body, assets_dir)
    log(f"Page liste OmniStudio générée : {path}")
    return path
