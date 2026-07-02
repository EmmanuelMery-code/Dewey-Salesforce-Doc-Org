"""Generic incoming-dependency lookups for objects, fields and any component."""

from __future__ import annotations

from src.core.models import Dependency


def object_dependencies(
    object_name: str,
    all_dependencies: list[Dependency],
) -> list[dict[str, str]]:
    """Compute the dependency rows for an object (Where it's used)."""
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for dep in all_dependencies:
        if dep.target_name == object_name and dep.target_kind == "Object":
            key = (dep.source_name, "Entrant", "Usage objet", dep.source_kind)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "name": dep.source_name,
                "category": dep.source_kind,
                "subtype": dep.source_kind,
                "direction": "Entrant",
                "relation": "Usage objet",
            })

    rows.sort(key=lambda item: (item["category"], item["name"].lower()))
    return rows


def field_dependencies(
    field_full_name: str,
    all_dependencies: list[Dependency],
) -> list[dict[str, str]]:
    """Compute the dependency rows for a field (Where it's used)."""
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for dep in all_dependencies:
        if dep.target_name == field_full_name and dep.target_kind == "Field":
            key = (dep.source_name, "Entrant", "Usage champ", dep.source_kind)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "name": dep.source_name,
                "category": dep.source_kind,
                "subtype": dep.source_kind,
                "direction": "Entrant",
                "relation": "Usage champ",
            })

    rows.sort(key=lambda item: (item["category"], item["name"].lower()))
    return rows


def get_incoming_dependencies(
    target_name: str,
    target_kind: str,
    all_dependencies: list[Dependency],
) -> list[dict[str, str]]:
    """Compute the incoming dependency rows for any component (Where it's used)."""
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for dep in all_dependencies:
        if dep.target_name == target_name and dep.target_kind == target_kind:
            key = (dep.source_name, "Entrant", dep.source_kind)
            if key in seen:
                continue
            seen.add(key)

            relation = "Usage"
            if dep.source_kind == "Apex":
                relation = "Reference code"
            elif dep.source_kind == "Flow":
                relation = "Appel depuis Flow"
            elif dep.source_kind == "Report":
                relation = "Source du rapport"

            rows.append({
                "name": dep.source_name,
                "category": dep.source_kind,
                "subtype": dep.source_kind,
                "direction": "Entrant",
                "relation": relation,
            })

    rows.sort(key=lambda item: (item["category"], item["name"].lower()))
    return rows
