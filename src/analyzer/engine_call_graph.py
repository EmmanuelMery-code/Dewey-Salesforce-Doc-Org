"""Apex call-graph construction and cycle detection (rule APEX-REL-003), used by
``AnalyzerEngine.analyze_snapshot`` in ``src.analyzer.engine``.
"""
from __future__ import annotations

import re

from src.analyzer.apex_analyzer import _strip_comments_and_strings
from src.analyzer.models import Finding
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import ApexArtifact


IDENTIFIER_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")


def _detect_apex_call_cycles(
    artifacts: list[ApexArtifact], catalog: RuleCatalog
) -> dict[str, list[Finding]]:
    """Detecte les cycles d'appels entre classes Apex (APEX-REL-003).

    La detection construit un graphe d'appels (ClassName -> {ClassName appelee}) base sur
    les identifiants en PascalCase mentionnes dans le code (apres retrait des commentaires
    et chaines litterales) puis applique l'algorithme de Tarjan pour extraire les SCCs.
    Les composantes de taille >= 2, ou les auto-boucles, remontent comme findings.
    """
    rule = catalog.get("APEX-REL-003")
    if not rule or not rule.enabled:
        return {}

    classes = [a for a in artifacts if a.kind == "class"]
    class_names = {a.name for a in classes}
    if len(class_names) < 2:
        return {}

    graph: dict[str, set[str]] = {name: set() for name in class_names}
    for artifact in classes:
        stripped = _strip_comments_and_strings(artifact.body)
        mentioned = {m for m in IDENTIFIER_RE.findall(stripped) if m in class_names}
        mentioned.discard(artifact.name)
        graph[artifact.name] = mentioned

    cycles = _find_cycles(graph)
    if not cycles:
        return {}

    findings_by_class: dict[str, list[Finding]] = {}
    for cycle in cycles:
        cycle_sorted = sorted(cycle)
        cycle_label = " -> ".join(cycle_sorted + [cycle_sorted[0]])
        details = [
            f"Classes participant au cycle : {', '.join(cycle_sorted)}.",
            f"Chaine simplifiee : {cycle_label}.",
        ]
        for cls in cycle_sorted:
            artifact = next((a for a in classes if a.name == cls), None)
            others = [c for c in cycle_sorted if c != cls]
            message = (
                "Classe impliquee dans un cycle d'appels avec "
                + (", ".join(others) if others else "elle-meme")
                + "."
            )
            finding = Finding(
                rule=rule,
                target_kind="ApexClass",
                target_name=cls,
                message=message,
                details=list(details),
                source_path=artifact.source_path if artifact else None,
            )
            findings_by_class.setdefault(cls, []).append(finding)
    return findings_by_class


def _find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Retourne les composantes fortement connexes >= 2 noeuds (ou auto-boucles) via Tarjan."""
    index_counter = [0]
    stack: list[str] = []
    on_stack: dict[str, bool] = {}
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    sccs: list[list[str]] = []

    def strongconnect(node: str) -> None:
        index[node] = index_counter[0]
        lowlink[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack[node] = True

        for neighbour in graph.get(node, set()):
            if neighbour not in graph:
                continue
            if neighbour not in index:
                strongconnect(neighbour)
                lowlink[node] = min(lowlink[node], lowlink[neighbour])
            elif on_stack.get(neighbour):
                lowlink[node] = min(lowlink[node], index[neighbour])

        if lowlink[node] == index[node]:
            component: list[str] = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                component.append(w)
                if w == node:
                    break
            if len(component) >= 2:
                sccs.append(component)
            elif node in graph.get(node, set()):
                sccs.append(component)

    for node in list(graph.keys()):
        if node not in index:
            strongconnect(node)
    return sccs
