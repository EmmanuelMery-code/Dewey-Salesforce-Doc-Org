"""Listing pages for the Description tab cards.

Each function generates a simple HTML table page that lists the elements
corresponding to one of the Description-tab metric blocks on index.html.
Pages are only written when there is at least one element to list.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.core.models import MetadataSnapshot
from src.core.utils import html_value, write_text
from src.reporting.html.page_shell import (
    href_relative,
    index_back_link,
    render_page,
)


LogCallback = Callable[[str], None]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _table(headers: list[str], rows: list[str], empty_msg: str = "Aucun élément.") -> str:
    ths = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join(rows) or f"<tr><td colspan='{len(headers)}' class='empty'>{empty_msg}</td></tr>"
    return f"<table><thead><tr>{ths}</tr></thead><tbody>{body}</tbody></table>"


def _write(path: Path, title: str, body: str, assets_dir: Path) -> None:
    write_text(path, render_page(title, body, path, assets_dir, include_mermaid=False))


# ---------------------------------------------------------------------------
# Custom objects
# ---------------------------------------------------------------------------


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
        rows.append(
            f"<tr>"
            f"<td>{name_cell}</td>"
            f"<td>{html_value(obj.label)}</td>"
            f"<td>{sum(1 for f in obj.fields if f.custom)}</td>"
            f"<td>{len(obj.record_types)}</td>"
            f"<td>{len(obj.validation_rules)}</td>"
            f"<td>{html_value(obj.description)}</td>"
            f"</tr>"
        )

    table = _table(
        ["API Name", "Label", "Champs custom", "Record Types", "Règles de validation", "Description"],
        rows,
    )
    body = f"{back}<h1>Objets custom ({len(custom_objects)})</h1>{table}"
    _write(path, "Objets custom", body, assets_dir)
    log(f"Page liste objets générée : {path}")
    return path


# ---------------------------------------------------------------------------
# Custom fields
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Flows
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Apex classes & triggers
# ---------------------------------------------------------------------------


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
    parts: list[str] = []
    if classes:
        parts.append(
            f"<h2>Classes Apex ({len(classes)})</h2>"
            f"{_table(headers, _rows(classes))}"
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


# ---------------------------------------------------------------------------
# OmniStudio components
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


def write_agents_list_page(
    snapshot: MetadataSnapshot,
    agent_pages: dict[str, Path],
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
) -> Path | None:
    if not snapshot.agents:
        return None

    path = output_dir / "agents_list.html"
    back = index_back_link(path, output_dir)

    rows = []
    for agent in sorted(snapshot.agents, key=lambda a: a.name.lower()):
        page = agent_pages.get(agent.name)
        name_cell = (
            f"<a href='{href_relative(path, page)}'>{html_value(agent.name)}</a>"
            if page
            else html_value(agent.name)
        )
        rows.append(
            f"<tr>"
            f"<td>{name_cell}</td>"
            f"<td>{html_value(agent.label)}</td>"
            f"<td>{html_value(agent.description)}</td>"
            f"</tr>"
        )

    table = _table(["Nom", "Label", "Description"], rows)
    body = f"{back}<h1>Agents Agentforce ({len(snapshot.agents)})</h1>{table}"
    _write(path, "Agents Agentforce", body, assets_dir)
    log(f"Page liste Agents générée : {path}")
    return path


# ---------------------------------------------------------------------------
# Gen AI Prompts
# ---------------------------------------------------------------------------


def write_prompts_list_page(
    snapshot: MetadataSnapshot,
    prompt_pages: dict[str, Path],
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
) -> Path | None:
    if not snapshot.gen_ai_prompts:
        return None

    path = output_dir / "prompts_list.html"
    back = index_back_link(path, output_dir)

    rows = []
    for prompt in sorted(snapshot.gen_ai_prompts, key=lambda p: p.name.lower()):
        page = prompt_pages.get(prompt.name)
        name_cell = (
            f"<a href='{href_relative(path, page)}'>{html_value(prompt.name)}</a>"
            if page
            else html_value(prompt.name)
        )
        rows.append(
            f"<tr>"
            f"<td>{name_cell}</td>"
            f"<td>{html_value(prompt.label)}</td>"
            f"<td>{html_value(prompt.description)}</td>"
            f"</tr>"
        )

    table = _table(["Nom", "Label", "Description"], rows)
    body = f"{back}<h1>Prompts — Prompt Builder ({len(snapshot.gen_ai_prompts)})</h1>{table}"
    _write(path, "Prompts", body, assets_dir)
    log(f"Page liste Prompts générée : {path}")
    return path


# ---------------------------------------------------------------------------
# Sharing Rules
# ---------------------------------------------------------------------------


def write_sharing_rules_list_page(
    snapshot: MetadataSnapshot,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
) -> Path | None:
    if not snapshot.sharing_rules:
        return None

    path = output_dir / "sharing_rules_list.html"
    back = index_back_link(path, output_dir)

    # Group by object
    by_object: dict[str, list] = {}
    for rule in snapshot.sharing_rules:
        by_object.setdefault(rule.object_name, []).append(rule)

    TYPE_LABELS = {
        "criteria": "Critères",
        "owner": "Propriétaire",
        "guest": "Utilisateur invité",
        "territory": "Territoire",
    }

    sections: list[str] = []
    for obj_name in sorted(by_object.keys(), key=str.lower):
        rules = by_object[obj_name]
        rows = [
            f"<tr>"
            f"<td>{html_value(r.full_name)}</td>"
            f"<td>{html_value(TYPE_LABELS.get(r.rule_type, r.rule_type))}</td>"
            f"<td>{html_value(r.label)}</td>"
            f"<td>{html_value(r.description)}</td>"
            f"</tr>"
            for r in rules
        ]
        table = _table(["Nom", "Type", "Label", "Description"], rows)
        sections.append(
            f"<h2>{html_value(obj_name)} <small style='font-weight:normal;color:#64748b;'>"
            f"({len(rules)} règle(s))</small></h2>{table}"
        )

    body = f"{back}<h1>Sharing Rules ({len(snapshot.sharing_rules)})</h1>{''.join(sections)}"
    _write(path, "Sharing Rules", body, assets_dir)
    log(f"Page liste Sharing Rules générée : {path}")
    return path


# ---------------------------------------------------------------------------
# Entry point — write all listing pages at once
# ---------------------------------------------------------------------------


def write_listing_pages(
    snapshot: MetadataSnapshot,
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    flow_pages: dict[str, Path],
    omni_pages: dict[str, list[dict[str, object]]],
    agent_pages: dict[str, Path],
    prompt_pages: dict[str, Path],
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
) -> dict[str, Path]:
    """Generate all listing pages and return a mapping key → Path.

    Keys: ``objects``, ``fields``, ``flows``, ``apex``, ``omni``,
    ``agents``, ``prompts``.  Only pages with at least one element are
    written; absent keys mean the count was zero.
    """
    pages: dict[str, Path] = {}

    result = write_objects_list_page(snapshot, object_pages, output_dir, assets_dir, log)
    if result:
        pages["objects"] = result

    result = write_fields_list_page(snapshot, object_pages, output_dir, assets_dir, log)
    if result:
        pages["fields"] = result

    result = write_flows_list_page(snapshot, flow_pages, output_dir, assets_dir, log)
    if result:
        pages["flows"] = result

    result = write_apex_list_page(snapshot, apex_pages, output_dir, assets_dir, log)
    if result:
        pages["apex"] = result

    result = write_omni_list_page(snapshot, omni_pages, output_dir, assets_dir, log)
    if result:
        pages["omni"] = result

    result = write_agents_list_page(snapshot, agent_pages, output_dir, assets_dir, log)
    if result:
        pages["agents"] = result

    result = write_prompts_list_page(snapshot, prompt_pages, output_dir, assets_dir, log)
    if result:
        pages["prompts"] = result

    result = write_sharing_rules_list_page(snapshot, output_dir, assets_dir, log)
    if result:
        pages["sharing_rules"] = result

    return pages
