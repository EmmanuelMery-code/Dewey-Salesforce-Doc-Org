"""Regles Nebula Logger sur les flows."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import deque

from src.analyzer.models import Finding
from src.analyzer.nebula_config import (
    NebulaConfig,
    language_issues,
    message_matches,
    sensitive_terms,
    tag_allowed,
)
from src.analyzer.nebula_scan import add_finding, line_of
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import FlowInfo
from src.core.utils import SF_NS, child_text


_ADD_ACTIONS = frozenset({
    "FlowLogEntry",
    "FlowRecordLogEntry",
    "FlowCollectionLogEntry",
})
_SAVE_ACTIONS = frozenset({"FlowLogger"})
_ELEMENT_TAGS = (
    "actionCalls",
    "assignments",
    "decisions",
    "loops",
    "recordCreates",
    "recordDeletes",
    "recordLookups",
    "recordUpdates",
    "screens",
    "subflows",
    "waits",
)


def analyze_nebula_flow(
    flow: FlowInfo, catalog: RuleCatalog, config: NebulaConfig
) -> list[Finding]:
    path = flow.source_path
    if path is None or not path.is_file():
        return []
    try:
        xml = path.read_text(encoding="utf-8")
        root = ET.fromstring(xml)
    except (OSError, ET.ParseError):
        return []

    nodes = _read_nodes(root)
    findings: list[Finding] = []
    pattern = config.compiled_format()
    fault_lines = [
        _element_line(xml, node.name)
        for node in nodes.values()
        if node.fault_target and not _fault_path_logs(node.fault_target, nodes)
    ]
    add_finding(
        findings, catalog, "NEBULA-FLOW-001", "Flow", flow.name, path,
        "nebula.flow_fault", fault_lines,
    )

    format_lines: list[int] = []
    sensitive_lines: list[int] = []
    sensitive_words: list[str] = []
    language_lines: list[int] = []
    language_words: list[str] = []
    tag_lines: list[int] = []
    tag_values: list[str] = []
    for node in nodes.values():
        if not node.is_add and not node.messages and not node.tags:
            continue
        line = _element_line(xml, node.name)
        for message in node.messages:
            if node.is_add and not message_matches(message, pattern):
                format_lines.append(line)
            issues = language_issues(message)
            if issues:
                language_lines.append(line)
                language_words.extend(issues)
            terms = sensitive_terms(message)
            if terms:
                sensitive_lines.append(line)
                sensitive_words.extend(terms)
        for value in node.tags:
            if not tag_allowed(value, config.tags):
                tag_lines.append(line)
                tag_values.append(value)

    add_finding(findings, catalog, "NEBULA-FLOW-002", "Flow", flow.name, path, "nebula.format", format_lines)
    add_finding(
        findings, catalog, "NEBULA-FLOW-008", "Flow", flow.name, path, "nebula.sensitive",
        sensitive_lines, sample=", ".join(sorted(set(sensitive_words))[:6]),
    )
    add_finding(
        findings, catalog, "NEBULA-FLOW-009", "Flow", flow.name, path, "nebula.language",
        language_lines, sample=", ".join(sorted(set(language_words))[:6]),
    )
    add_finding(
        findings, catalog, "NEBULA-FLOW-012", "Flow", flow.name, path, "nebula.tag",
        tag_lines, sample=", ".join(tag_values[:6]),
    )
    return findings


class _FlowNode:
    def __init__(self, name: str) -> None:
        self.name = name
        self.targets: list[str] = []
        self.fault_target = ""
        self.is_add = False
        self.is_save = False
        self.messages: list[str] = []
        self.tags: list[str] = []


def _short_action(action_name: str) -> str:
    return action_name.split(".")[-1].split("__")[-1]


def _read_nodes(root: ET.Element) -> dict[str, _FlowNode]:
    nodes: dict[str, _FlowNode] = {}
    for tag in _ELEMENT_TAGS:
        for node in root.findall(f"sf:{tag}", SF_NS):
            name = child_text(node, "name")
            if not name:
                continue
            item = _FlowNode(name)
            action = child_text(node, "actionName")
            label = child_text(node, "label")
            short = _short_action(action)
            item.is_add = short in _ADD_ACTIONS or "add log entry" in label.casefold()
            item.is_save = short in _SAVE_ACTIONS or label.casefold().strip() in {"save log", "save logs"}
            fault = node.find("sf:faultConnector", SF_NS)
            item.fault_target = child_text(fault, "targetReference") if fault is not None else ""
            for target in node.findall(".//sf:targetReference", SF_NS):
                if target.text and target.text.strip() and target.text.strip() != item.fault_target:
                    item.targets.append(target.text.strip())
            if item.fault_target:
                item.targets.append(item.fault_target)
            for param in node.findall("sf:inputParameters", SF_NS):
                param_name = child_text(param, "name").casefold()
                values = [
                    (value.text or "").strip()
                    for value in param.findall(".//sf:stringValue", SF_NS)
                    if value.text and value.text.strip()
                ]
                if param_name == "message":
                    item.messages.extend(values)
                elif param_name in {"tags", "tag"}:
                    item.tags.extend(values)
            nodes[name] = item
    return nodes


def _fault_path_logs(start: str, nodes: dict[str, _FlowNode]) -> bool:
    seen_add = False
    seen_save = False
    queue: deque[str] = deque([start])
    visited: set[str] = set()
    while queue and not (seen_add and seen_save):
        name = queue.popleft()
        if name in visited:
            continue
        visited.add(name)
        node = nodes.get(name)
        if node is None:
            continue
        seen_add = seen_add or node.is_add
        seen_save = seen_save or node.is_save
        for target in node.targets:
            if target not in visited:
                queue.append(target)
    return seen_add and seen_save


def _element_line(xml: str, name: str) -> int:
    token = f">{name}<"
    index = xml.find(token)
    if index < 0:
        return 1
    return line_of(xml, index)
