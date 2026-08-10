"""Listing pages for the Description tab cards.

Each function generates a simple HTML table page that lists the elements
corresponding to one of the Description-tab metric blocks on index.html.
Pages are only written when there is at least one element to list.

The individual page builders live in sibling ``listing_*`` modules, grouped
by theme; this module re-exports them and exposes :func:`write_listing_pages`,
the single entry point used by ``html_writer.py``.
"""

from __future__ import annotations

from pathlib import Path

from src.core.models import MetadataSnapshot
from src.reporting.html.renderers.listing_tables import LogCallback
from src.reporting.html.renderers.listing_objects_fields import (
    write_fields_list_page,
    write_objects_list_page,
)
from src.reporting.html.renderers.listing_flows_apex_omni import (
    write_apex_list_page,
    write_flows_list_page,
    write_omni_list_page,
)
from src.reporting.html.renderers.listing_agents_prompts_sharing import (
    write_agents_list_page,
    write_prompts_list_page,
    write_sharing_rules_list_page,
)
from src.reporting.html.renderers.listing_components import (
    write_aura_list_page,
    write_duplicate_rules_list_page,
    write_lwc_list_page,
)


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

    result = write_duplicate_rules_list_page(snapshot, output_dir, assets_dir, log)
    if result:
        pages["duplicate_rules"] = result

    result = write_lwc_list_page(snapshot, output_dir, assets_dir, log)
    if result:
        pages["lwc"] = result

    result = write_aura_list_page(snapshot, output_dir, assets_dir, log)
    if result:
        pages["aura"] = result

    return pages
