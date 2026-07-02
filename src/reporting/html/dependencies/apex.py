"""Apex-centric dependency scanning."""

from __future__ import annotations

import re

from src.core.models import ApexArtifact

from src.reporting.html.dependencies.common import _METADATA_RE


def build_apex_reference_index(
    artifacts: list[ApexArtifact],
) -> dict[str, set[str]]:
    """Return, for each Apex artifact, the set of other artifacts mentioned in its body."""

    references: dict[str, set[str]] = {}
    patterns = {
        artifact.name: re.compile(rf"\b{re.escape(artifact.name)}\b", re.IGNORECASE)
        for artifact in artifacts
    }
    for source in artifacts:
        linked: set[str] = set()
        for target in artifacts:
            if target.name == source.name:
                continue
            if patterns[target.name].search(source.body):
                linked.add(target.name)
        references[source.name] = linked
    return references


def trigger_object_name(artifact: ApexArtifact) -> str:
    """Extract the sObject name a trigger fires on, or ``""`` for non-triggers."""

    if artifact.kind != "trigger":
        return ""
    match = re.search(
        r"(?im)^\s*trigger\s+\w+\s+on\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        artifact.body,
    )
    return match.group(1) if match else ""


def apex_dependencies(
    artifact: ApexArtifact,
    artifacts: list[ApexArtifact],
    reference_index: dict[str, set[str]],
    trigger_objects: dict[str, str],
    object_names: list[str],
    flow_names: list[str],
) -> list[dict[str, str]]:
    """Compute the (sorted, de-duplicated) dependency rows for a single Apex artifact."""

    rows: list[dict[str, str]] = []
    by_name = {item.name: item for item in artifacts}
    seen: set[tuple[str, str, str, str]] = set()

    for target_name in sorted(reference_index.get(artifact.name, set()), key=str.lower):
        target = by_name.get(target_name)
        if target is None:
            continue
        key = (target_name, "Sortant", "Reference code", "Apex")
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": target_name,
                "category": "Apex",
                "subtype": target.kind,
                "direction": "Sortant",
                "relation": "Reference code",
            }
        )

    for source_name, targets in reference_index.items():
        if source_name == artifact.name or artifact.name not in targets:
            continue
        source = by_name.get(source_name)
        if source is None:
            continue
        key = (source_name, "Entrant", "Reference code", "Apex")
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": source_name,
                "category": "Apex",
                "subtype": source.kind,
                "direction": "Entrant",
                "relation": "Reference code",
            }
        )

    if artifact.kind == "trigger":
        current_object = trigger_objects.get(artifact.name, "")
        if current_object:
            for target in artifacts:
                if target.name == artifact.name or target.kind != "trigger":
                    continue
                if trigger_objects.get(target.name) != current_object:
                    continue
                key = (target.name, "Sortant", f"Meme objet trigger ({current_object})", "Apex")
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "name": target.name,
                        "category": "Apex",
                        "subtype": target.kind,
                        "direction": "Sortant",
                        "relation": f"Meme objet trigger ({current_object})",
                    }
                )

    for object_name in sorted(object_names, key=str.lower):
        if not re.search(rf"\b{re.escape(object_name)}\b", artifact.body):
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

    for flow_name in sorted(flow_names, key=str.lower):
        if not re.search(rf"\b{re.escape(flow_name)}\b", artifact.body):
            continue
        key = (flow_name, "Sortant", "Reference flow", "Flow")
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": flow_name,
                "category": "Flow",
                "subtype": "Flow",
                "direction": "Sortant",
                "relation": "Reference flow",
            }
        )

    metadata_matches = sorted(set(_METADATA_RE.findall(artifact.body)))
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
