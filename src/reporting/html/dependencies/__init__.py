"""Build and render the dependency tables / vis-network graphs.

This package was split from a single ``dependencies.py`` module for
readability. Every public name is re-exported here so existing
``from src.reporting.html.dependencies import X`` imports keep working.
"""

from __future__ import annotations

from src.reporting.html.dependencies.apex import (
    apex_dependencies,
    build_apex_reference_index,
    trigger_object_name,
)
from src.reporting.html.dependencies.components import (
    field_dependencies,
    get_incoming_dependencies,
    object_dependencies,
)
from src.reporting.html.dependencies.flows import (
    build_flow_reference_index,
    flow_dependencies,
)
from src.reporting.html.dependencies.render import (
    dependency_node_color,
    render_apex_dependency_graph,
    render_apex_dependency_rows,
    render_component_dependency_graph,
    render_dependency_rows,
)

__all__ = [
    "apex_dependencies",
    "build_apex_reference_index",
    "build_flow_reference_index",
    "dependency_node_color",
    "field_dependencies",
    "flow_dependencies",
    "get_incoming_dependencies",
    "object_dependencies",
    "render_apex_dependency_graph",
    "render_apex_dependency_rows",
    "render_component_dependency_graph",
    "render_dependency_rows",
    "trigger_object_name",
]
