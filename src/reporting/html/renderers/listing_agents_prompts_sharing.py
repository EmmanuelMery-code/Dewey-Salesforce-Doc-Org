"""Listing pages for Agentforce Agents, Prompt Builder prompts and Sharing Rules."""

from __future__ import annotations

from pathlib import Path

from src.core.models import MetadataSnapshot
from src.core.utils import html_value
from src.reporting.html.page_shell import href_relative, index_back_link
from src.reporting.html.renderers.listing_tables import LogCallback, _table, _write


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
