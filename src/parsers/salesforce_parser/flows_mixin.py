"""Parsing of Flow metadata, path analysis and DML/SOQL-in-loop detection."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from src.core.models import FlowConnector, FlowElementInfo, FlowInfo
from src.core.utils import SF_NS, child_text, parse_xml, to_bool
from src.parsers.salesforce_parser.base import _ParserState


# InvocableActionType values that make an actual HTTP request to a system
# outside the org (Metadata API Developer Guide, FlowActionCall.actionType).
# "apex" invocable actions may also perform callouts, but that can only be
# confirmed by cross-referencing the target Apex class (out of scope here).
_API_ACTION_TYPES: frozenset[str] = frozenset({"externalService"})


class _FlowsMixin(_ParserState):
    """Parse the ``flows/`` folder and compute complexity metrics."""

    def _parse_flows(self, folder: Path) -> list[FlowInfo]:
        flows: list[FlowInfo] = []
        if not folder.exists():
            return flows

        interesting_tags = [
            "actionCalls",
            "assignments",
            "collectionProcessors",
            "decisions",
            "formulas",
            "loops",
            "recordCreates",
            "recordDeletes",
            "recordLookups",
            "recordUpdates",
            "screens",
            "subflows",
            "transforms",
            "waits",
        ]

        for flow_file in sorted(folder.glob("*.flow-meta.xml")):
            root = parse_xml(flow_file)
            element_counts = Counter()
            elements: list[FlowElementInfo] = []
            described = 0
            undocumented = 0
            adjacency: dict[str, list[str]] = {}
            structural_types = {"decisions", "loops", "subflows"}
            nodes_by_name: dict[str, str] = {}
            api_action_names: list[str] = []
            called_flow_names: list[str] = []

            for tag in interesting_tags:
                for node in root.findall(f"sf:{tag}", SF_NS):
                    element_counts[tag] += 1
                    description = child_text(node, "description")
                    if description:
                        described += 1
                    else:
                        undocumented += 1

                    name = child_text(node, "name")
                    if name:
                        node_tag = tag
                        if tag == "actionCalls":
                            action_type = child_text(node, "actionType")
                            if action_type in _API_ACTION_TYPES:
                                node_tag = "actionCalls:api"
                                api_action_names.append(name)
                        nodes_by_name[name] = node_tag
                        adjacency.setdefault(name, [])

                    if tag == "subflows":
                        # <subflows> is the "Subflow" element in Flow Builder;
                        # <flowName> holds the API name of the called Flow.
                        # A Flow reachable only through this reference is not
                        # an orphan (see _DependenciesMixin._analyze_dependencies).
                        called_flow_name = child_text(node, "flowName")
                        if called_flow_name:
                            called_flow_names.append(called_flow_name)

                    target = ""
                    element_targets = []
                    element_connectors = []
                    connector = node.find("sf:connector/sf:targetReference", SF_NS)
                    if connector is not None and connector.text:
                        target = connector.text.strip()
                        element_targets.append(target)
                        element_connectors.append(FlowConnector(target=target))
                        if name:
                            adjacency[name].append(target)

                    if tag == "decisions":
                        for rule in node.findall("sf:rules", SF_NS):
                            rule_label = child_text(rule, "label")
                            rule_connector = rule.find("sf:connector", SF_NS)
                            rule_target = (
                                child_text(rule_connector, "targetReference") if rule_connector is not None else ""
                            )
                            if rule_target:
                                element_targets.append(rule_target)
                                element_connectors.append(FlowConnector(target=rule_target, label=rule_label))
                                if name:
                                    adjacency[name].append(rule_target)
                        default_connector = node.find("sf:defaultConnector", SF_NS)
                        default_target = (
                            child_text(default_connector, "targetReference")
                            if default_connector is not None
                            else ""
                        )
                        if default_target:
                            element_targets.append(default_target)
                            element_connectors.append(FlowConnector(target=default_target, label="Default Outcome"))
                            if name:
                                adjacency[name].append(default_target)
                    elif tag == "loops":
                        next_connector = node.find("sf:nextValueConnector", SF_NS)
                        next_target = (
                            child_text(next_connector, "targetReference") if next_connector is not None else ""
                        )
                        if next_target:
                            element_targets.append(next_target)
                            element_connectors.append(FlowConnector(target=next_target, label="Next Item"))
                            if name:
                                adjacency[name].append(next_target)
                        end_connector = node.find("sf:noMoreValuesConnector", SF_NS)
                        end_target = (
                            child_text(end_connector, "targetReference") if end_connector is not None else ""
                        )
                        if end_target:
                            element_targets.append(end_target)
                            element_connectors.append(FlowConnector(target=end_target, label="End Loop"))
                            if name:
                                adjacency[name].append(end_target)

                    fault_connector = node.find("sf:faultConnector", SF_NS)
                    fault_target = (
                        child_text(fault_connector, "targetReference") if fault_connector is not None else ""
                    )
                    if fault_target:
                        element_targets.append(fault_target)
                        element_connectors.append(FlowConnector(target=fault_target, label="Fault"))
                        if name:
                            adjacency[name].append(fault_target)

                    elements.append(
                        FlowElementInfo(
                            element_type=tag,
                            name=name,
                            label=child_text(node, "label"),
                            description=description,
                            connectors=element_connectors,
                            targets=element_targets,
                            target=target,
                        )
                    )

            variables = root.findall("sf:variables", SF_NS)
            variable_total = len(variables)
            variable_input = 0
            variable_output = 0
            for variable in variables:
                if to_bool(child_text(variable, "isInput")):
                    variable_input += 1
                if to_bool(child_text(variable, "isOutput")):
                    variable_output += 1

            start_node = ""
            start = root.find("sf:start", SF_NS)
            if start is not None:
                start_connector = start.find("sf:connector", SF_NS)
                start_node = child_text(start_connector, "targetReference") if start_connector is not None else ""

            max_width = 1
            for decision in root.findall("sf:decisions", SF_NS):
                width = len(decision.findall("sf:rules", SF_NS))
                if decision.find("sf:defaultConnector", SF_NS) is not None:
                    width += 1
                max_width = max(max_width, width)

            min_height = 0
            max_height = 0
            max_depth = 0
            dml_in_loop = False
            soql_in_loop = False
            api_call_in_loop = False
            api_call_in_loop_actions: list[str] = []

            if start_node and start_node in nodes_by_name:
                paths = self._flow_paths(start_node, adjacency)
                if paths:
                    min_height = min(len(path) for path in paths)
                    max_height = max(len(path) for path in paths)
                    for path in paths:
                        depth = sum(
                            1
                            for node_name in path
                            if nodes_by_name.get(node_name) in structural_types
                        )
                        max_depth = max(max_depth, depth)

            # Check for DML/SOQL/API-action in loops
            dml_ops = {"recordCreates", "recordUpdates", "recordDeletes"}
            soql_ops = {"recordLookups"}
            api_ops = {"actionCalls:api"}

            for loop_node in root.findall("sf:loops", SF_NS):
                loop_name = child_text(loop_node, "name")
                next_connector = loop_node.find("sf:nextValueConnector", SF_NS)
                next_target = child_text(next_connector, "targetReference") if next_connector is not None else ""

                if next_target:
                    if self._is_node_reachable(next_target, dml_ops, loop_name, nodes_by_name, adjacency):
                        dml_in_loop = True
                    if self._is_node_reachable(next_target, soql_ops, loop_name, nodes_by_name, adjacency):
                        soql_in_loop = True
                    if api_action_names and self._is_node_reachable(
                        next_target, api_ops, loop_name, nodes_by_name, adjacency,
                        collect_matches=api_call_in_loop_actions,
                    ):
                        api_call_in_loop = True

                if dml_in_loop and soql_in_loop and api_call_in_loop:
                    break

            flow = FlowInfo(
                name=flow_file.stem.replace(".flow-meta", ""),
                label=child_text(root, "label"),
                description=child_text(root, "description"),
                process_type=child_text(root, "processType"),
                status=child_text(root, "status"),
                api_version=child_text(root, "apiVersion"),
                trigger_type=child_text(root.find("sf:start", SF_NS), "triggerType")
                if root.find("sf:start", SF_NS) is not None
                else "",
                start_object=child_text(root.find("sf:start", SF_NS), "object")
                if root.find("sf:start", SF_NS) is not None
                else "",
                start_node=start_node,
                source_path=flow_file,
                element_counts=dict(element_counts),
                described_elements=described,
                undocumented_elements=undocumented,
                total_elements=sum(element_counts.values()),
                variable_total=variable_total,
                variable_input=variable_input,
                variable_output=variable_output,
                max_width=max_width,
                min_height=min_height,
                max_height=max_height,
                max_depth=max_depth,
                elements=elements,
                dml_in_loop=dml_in_loop,
                soql_in_loop=soql_in_loop,
                api_call_in_loop=api_call_in_loop,
                api_call_in_loop_actions=api_call_in_loop_actions,
                called_flow_names=called_flow_names,
            )
            flows.append(flow)

        return flows

    def _flow_paths(self, start_node: str, adjacency: dict[str, list[str]]) -> list[list[str]]:
        paths: list[list[str]] = []
        stack: list[tuple[str, list[str]]] = [(start_node, [start_node])]
        safeguard = 0

        while stack and safeguard < 5000:
            safeguard += 1
            current, path = stack.pop()
            neighbors = adjacency.get(current, [])
            if not neighbors:
                paths.append(path)
                continue

            advanced = False
            for neighbor in neighbors:
                if neighbor and neighbor not in path:
                    stack.append((neighbor, [*path, neighbor]))
                    advanced = True
            if not advanced:
                paths.append(path)

        return paths

    def _is_node_reachable(
        self,
        start_node: str,
        target_types: set[str],
        end_node: str,
        nodes_by_name: dict[str, str],
        adjacency: dict[str, list[str]],
        collect_matches: list[str] | None = None,
    ) -> bool:
        """Depth-first search for a node whose tag is in ``target_types``.

        Traversal stops at ``end_node`` (the loop element itself), which
        marks the boundary of one iteration of the loop body. If
        ``collect_matches`` is provided, every matching node name is
        appended instead of returning on the first hit (used to report
        *which* actions triggered the finding).
        """
        if not start_node or start_node not in nodes_by_name:
            return False

        visited = set()
        stack = [start_node]
        found = False

        while stack:
            current = stack.pop()
            if current == end_node:
                continue
            if current in visited:
                continue
            visited.add(current)

            if nodes_by_name.get(current) in target_types:
                if collect_matches is None:
                    return True
                collect_matches.append(current)
                found = True

            for neighbor in adjacency.get(current, []):
                if neighbor:
                    stack.append(neighbor)

        return found
