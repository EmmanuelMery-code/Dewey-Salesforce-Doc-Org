"""Flow-centric dependency scanning."""

from __future__ import annotations

import re

from src.core.models import FlowInfo

from src.reporting.html.dependencies.common import _METADATA_RE


def build_flow_reference_index(
    flows: list[FlowInfo],
    flow_bodies: dict[str, str],
) -> dict[str, set[str]]:
    """Return, for each flow, the set of other flow names mentioned in its source XML."""

    references: dict[str, set[str]] = {}
    patterns = {
        flow.name: re.compile(rf"\b{re.escape(flow.name)}\b", re.IGNORECASE)
        for flow in flows
    }
    for source in flows:
        body = flow_bodies.get(source.name, "")
        linked: set[str] = set()
        for target in flows:
            if target.name == source.name:
                continue
            if patterns[target.name].search(body):
                linked.add(target.name)
        references[source.name] = linked
    return references


def flow_dependencies(
    flow: FlowInfo,
    flow_ref_index: dict[str, set[str]],
    body: str,
    object_names: list[str],
    apex_names: list[str],
) -> list[dict[str, str]]:
    """Compute the (sorted, de-duplicated) dependency rows for a single flow."""

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for target_name in sorted(flow_ref_index.get(flow.name, set()), key=str.lower):
        key = (target_name, "Sortant", "Reference flow", "Flow")
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": target_name,
                "category": "Flow",
                "subtype": "Flow",
                "direction": "Sortant",
                "relation": "Reference flow",
            }
        )

    for source_name, targets in flow_ref_index.items():
        if source_name == flow.name or flow.name not in targets:
            continue
        key = (source_name, "Entrant", "Reference flow", "Flow")
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": source_name,
                "category": "Flow",
                "subtype": "Flow",
                "direction": "Entrant",
                "relation": "Reference flow",
            }
        )

    if flow.start_object:
        key = (flow.start_object, "Sortant", "Objet de depart", "Objet")
        if key not in seen:
            seen.add(key)
            rows.append(
                {
                    "name": flow.start_object,
                    "category": "Objet",
                    "subtype": "sObject",
                    "direction": "Sortant",
                    "relation": "Objet de depart",
                }
            )

    for object_name in sorted(object_names, key=str.lower):
        if not re.search(rf"\b{re.escape(object_name)}\b", body):
            continue
        key = (object_name, "Sortant", "Usage objet", "Objet")
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": object_name,
                "category": "Objet",
                "subtype": "sObject",
                "direction": "Sortant",
                "relation": "Usage objet",
            }
        )

    for apex_name in sorted(apex_names, key=str.lower):
        if not re.search(rf"\b{re.escape(apex_name)}\b", body):
            continue
        key = (apex_name, "Sortant", "Reference Apex", "Apex")
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": apex_name,
                "category": "Apex",
                "subtype": "class",
                "direction": "Sortant",
                "relation": "Reference Apex",
            }
        )

    metadata_matches = sorted(set(_METADATA_RE.findall(body)))
    for metadata_name in metadata_matches:
        key = (metadata_name, "Sortant", "Reference metadata", "Metadata")
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": metadata_name,
                "category": "Metadata",
                "subtype": "CustomMetadata",
                "direction": "Sortant",
                "relation": "Reference metadata",
            }
        )

    rows.sort(key=lambda item: (item["category"], item["direction"], item["name"].lower()))
    return rows
