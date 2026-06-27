"""Algorithme de construction du graphe One Page."""

from __future__ import annotations

import html
from dataclasses import dataclass, field

from src.core.models import Dependency
from src.reporting.html import one_page_state as state


_KIND_TO_CATEGORY = {
    "class": "Apex",
    "trigger": "Apex",
    "apex": "Apex",
    "object": "Objet",
    "objet": "Objet",
    "field": "Field",
    "champ": "Field",
    "flow": "Flow",
    "lwc": "LWC",
    "aura": "Aura",
    "report": "Report",
    "metadata": "Metadata",
}

_CATEGORY_PRIORITY = {
    "Objet": 5,
    "Flow": 5,
    "Field": 4,
    "LWC": 4,
    "Aura": 4,
    "Report": 4,
    "Metadata": 3,
    "Apex": 2,
    "": 0,
}

_CATEGORY_COLORS = {
    "Apex": {"background": "#dbeafe", "border": "#3b82f6"},
    "Objet": {"background": "#dcfce7", "border": "#22c55e"},
    "Flow": {"background": "#ffedd5", "border": "#f97316"},
    "Field": {"background": "#fef9c3", "border": "#ca8a04"},
    "LWC": {"background": "#cffafe", "border": "#06b6d4"},
    "Aura": {"background": "#e0e7ff", "border": "#6366f1"},
    "Report": {"background": "#fae8ff", "border": "#c026d3"},
    "Metadata": {"background": "#f3e8ff", "border": "#a855f7"},
}

_CENTER_COLOR = {"background": "#bfdbfe", "border": "#1d4ed8"}

_RELATION_LABEL = {
    "Object": "utilise objet",
    "Objet": "utilise objet",
    "Field": "utilise champ",
    "Apex": "reference",
    "Flow": "appelle flow",
}


def _category_for_kind(kind: str) -> str:
    return _KIND_TO_CATEGORY.get((kind or "").strip().lower(), "Apex")


def _better_category(existing: str, candidate: str) -> str:
    if _CATEGORY_PRIORITY.get(candidate, 1) > _CATEGORY_PRIORITY.get(existing, 1):
        return candidate
    return existing


@dataclass(slots=True)
class _Graph:
    categories: dict[str, str] = field(default_factory=dict)
    neighbors: dict[str, set[str]] = field(default_factory=dict)
    edges: dict[tuple[str, str], str] = field(default_factory=dict)
    in_degree: dict[str, int] = field(default_factory=dict)


def _build_graph(all_dependencies: list[Dependency]) -> _Graph:
    graph = _Graph()
    incoming_sources: dict[str, set[str]] = {}

    for dep in all_dependencies:
        source = dep.source_name
        target = dep.target_name
        if not source or not target or source == target:
            continue

        src_cat = _category_for_kind(dep.source_kind)
        tgt_cat = _category_for_kind(dep.target_kind)
        graph.categories[source] = _better_category(
            graph.categories.get(source, ""), src_cat
        )
        graph.categories[target] = _better_category(
            graph.categories.get(target, ""), tgt_cat
        )

        graph.neighbors.setdefault(source, set()).add(target)
        graph.neighbors.setdefault(target, set()).add(source)

        label = _RELATION_LABEL.get(dep.target_kind, "lien")
        graph.edges.setdefault((source, target), label)
        incoming_sources.setdefault(target, set()).add(source)

    graph.in_degree = {name: len(sources) for name, sources in incoming_sources.items()}
    return graph


def build_one_page_graph(
    center_name: str,
    center_category: str,
    all_dependencies: list[Dependency],
    *,
    max_depth: int | None = None,
    hub_threshold: int | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Retourne ``(nodes, edges)`` prets pour vis-network apres elagage."""

    max_depth = state.ONE_PAGE_MAX_DEPTH if max_depth is None else max_depth
    hub_threshold = (
        state.ONE_PAGE_HUB_THRESHOLD if hub_threshold is None else hub_threshold
    )

    graph = _build_graph(all_dependencies)
    if center_name not in graph.neighbors:
        return [], []

    hubs = {
        name
        for name, degree in graph.in_degree.items()
        if degree >= hub_threshold and name != center_name
    }

    depth: dict[str, int] = {center_name: 0}
    is_hub_terminal: set[str] = set()
    queue: list[tuple[str, int]] = [(center_name, 0)]
    while queue:
        node, node_depth = queue.pop(0)
        if node_depth >= max_depth:
            continue
        for neighbor in sorted(graph.neighbors.get(node, set())):
            if neighbor in depth:
                continue
            new_depth = node_depth + 1
            if neighbor in hubs:
                if new_depth == 1:
                    depth[neighbor] = new_depth
                    is_hub_terminal.add(neighbor)
                continue
            depth[neighbor] = new_depth
            queue.append((neighbor, new_depth))

    kept = set(depth)
    sub_edges: dict[tuple[str, str], str] = {
        (s, t): label
        for (s, t), label in graph.edges.items()
        if s in kept and t in kept
    }

    undirected_degree: dict[str, int] = {name: 0 for name in kept}
    seen_pairs: set[frozenset[str]] = set()
    for s, t in sub_edges:
        pair = frozenset((s, t))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        undirected_degree[s] = undirected_degree.get(s, 0) + 1
        undirected_degree[t] = undirected_degree.get(t, 0) + 1

    removable = {
        name
        for name in kept
        if name != center_name
        and depth.get(name, 0) >= 2
        and name not in is_hub_terminal
        and undirected_degree.get(name, 0) <= 1
    }
    if removable:
        kept -= removable
        sub_edges = {
            (s, t): label
            for (s, t), label in sub_edges.items()
            if s in kept and t in kept
        }

    nodes: list[dict[str, object]] = []
    for name in sorted(kept, key=lambda n: (depth.get(n, 0), n.lower())):
        node_depth = depth.get(name, 0)
        if name == center_name:
            category = center_category
            color = _CENTER_COLOR
            border_width = 3
        else:
            category = graph.categories.get(name, "Apex")
            color = _CATEGORY_COLORS.get(category, _CATEGORY_COLORS["Apex"])
            border_width = 2 if node_depth == 1 else 1

        is_test = name in state.TEST_NODE_NAMES
        is_inactive_flow = category == "Flow" and name in state.INACTIVE_FLOW_NAMES
        suffix = " (hub)" if name in is_hub_terminal else ""
        if is_test:
            suffix += " (test)"
        if is_inactive_flow:
            suffix += " (inactif)"
        description = state.NODE_DESCRIPTIONS.get(name, "")
        title = f"{category} - rang {node_depth}{suffix}: {name}"
        if description:
            title += (
                "<br><br><strong>Description</strong><br>"
                f"{html.escape(description)}"
            )
        nodes.append(
            {
                "id": name,
                "label": name,
                "title": title,
                "color": color,
                "shape": "box",
                "depth": node_depth,
                "category": category,
                "isHub": name in is_hub_terminal,
                "isTest": is_test,
                "isInactiveFlow": is_inactive_flow,
                "borderWidth": border_width,
            }
        )

    edges: list[dict[str, object]] = []
    for (source, target), label in sorted(sub_edges.items()):
        edges.append(
            {
                "from": source,
                "to": target,
                "label": label,
                "arrows": "to",
                "depth": max(depth.get(source, 0), depth.get(target, 0)),
            }
        )

    return nodes, edges
