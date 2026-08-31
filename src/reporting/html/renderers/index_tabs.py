"""Builds the main tabbed section (Objets, Apex, Flows, Analyseur, ...) of index.html."""

from __future__ import annotations

from pathlib import Path

from src.core.models import MetadataSnapshot, PmdViolation, ReviewResult
from src.reporting.html.page_shell import tabbed_sections
from src.reporting.html.renderers.index_panels import (
    render_excel_exports,
    render_index_analyzer_panel,
    render_index_dependencies_panel,
    render_index_improvements,
    render_index_omni_panel,
    render_index_pmd_panel,
)
from src.reporting.html.renderers.omni import OMNI_TAB_LABEL
from src.reporting.html.renderers.index_tables import (
    render_agent_rows,
    render_apex_rows,
    render_flow_panel,
    render_health_panel,
    render_object_rows,
    render_prompt_rows,
    render_security_dashboard_tab,
    render_sharing_rule_rows,
)


def render_index_tabs(
    snapshot: MetadataSnapshot,
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    flow_pages: dict[str, Path],
    apex_reviews: dict[str, ReviewResult],
    flow_reviews: dict[str, ReviewResult],
    pmd_results: dict[str, list[PmdViolation]],
    current_path: Path,
    root_dir: Path,
    omni_pages: dict[str, list[dict[str, object]]],
    agent_pages: dict[str, Path],
    prompt_pages: dict[str, Path],
    security_pages: dict[str, Path] | None,
    analyzer_report,
) -> str:
    """Build the full ``tabbed_sections`` HTML block shown below the summary cards."""
    object_rows = render_object_rows(snapshot, object_pages, current_path)

    security_dashboard_tab = render_security_dashboard_tab(
        snapshot,
        current_path,
        security_pages,
        analyzer_report,
    )

    sharing_rule_rows = render_sharing_rule_rows(snapshot)
    apex_rows = render_apex_rows(snapshot, apex_pages, current_path)
    flow_panel = render_flow_panel(snapshot, flow_pages, current_path)

    excel_links = render_excel_exports(root_dir, current_path)
    omni_panel = render_index_omni_panel(omni_pages, current_path)
    agent_rows = render_agent_rows(snapshot, agent_pages, current_path)
    prompt_rows = render_prompt_rows(snapshot, prompt_pages, current_path)

    analyzer_panel = render_index_analyzer_panel(
        analyzer_report,
        current_path,
        object_pages,
        apex_pages,
        flow_pages,
        agent_pages=agent_pages,
        prompt_pages=prompt_pages,
    )

    dependencies_panel = render_index_dependencies_panel(
        snapshot,
        current_path,
        object_pages,
        apex_pages,
        flow_pages,
        agent_pages=agent_pages,
        prompt_pages=prompt_pages,
    )

    vr_header = (
        '<span title="Nombre de règles de validation et score de complexité cumulé (Σ). '
        'Le score est calculé selon la longueur de la formule (1pt par 50 car.) '
        'et le nombre d\'opérateurs logiques (IF, AND, OR, CASE, parenthèses).">'
        'VR (Complexité)</span>'
    )
    health_panel = render_health_panel(
        snapshot,
        current_path,
        object_pages,
        apex_pages,
        flow_pages,
        agent_pages,
        prompt_pages,
    )

    # ── Improvements & PMD ───────────────────────────────────────────
    improvements_panel = render_index_improvements(
        snapshot,
        apex_reviews,
        flow_reviews,
        current_path,
        apex_pages,
        flow_pages,
    )
    pmd_panel = render_index_pmd_panel(
        snapshot,
        pmd_results,
        current_path,
        apex_pages,
    )

    return tabbed_sections(
        "index",
        [
            (
                "Exports Excel",
                excel_links,
            ),
            (
                "Objets",
                f"<table><thead><tr><th>Objet</th><th>Label</th><th>Nb champs</th><th>Nb relations</th><th>{vr_header}</th><th>Triggers Apex</th><th>Flows</th></tr></thead><tbody>{object_rows}</tbody></table>",
            ),
            (
                "Profiles & PS",
                security_dashboard_tab,
            ),
            (
                "Sharing Rules",
                f"<table><thead><tr><th>Objet</th><th>Nom</th><th>Type</th><th>Label</th><th>Description</th></tr></thead><tbody>{sharing_rule_rows}</tbody></table>",
            ),
            (
                "Apex / Trigger",
                f"<table><thead><tr><th>Nom</th><th>Type</th><th>Lignes</th><th>Methodes</th><th>% Couverture</th></tr></thead><tbody>{apex_rows}</tbody></table>",
            ),
            (
                "Flows",
                flow_panel,
            ),
            (
                OMNI_TAB_LABEL,
                omni_panel,
            ),
            (
                "Prompts",
                f"<table><thead><tr><th>Prompt</th><th>Label</th><th>Description</th></tr></thead><tbody>{prompt_rows}</tbody></table>",
            ),
            (
                "Agents",
                f"<table><thead><tr><th>Agent</th><th>Label</th><th>Description</th></tr></thead><tbody>{agent_rows}</tbody></table>",
            ),
            (
                "Dependances",
                dependencies_panel,
            ),
            (
                "Analyseur",
                analyzer_panel,
            ),
            (
                "Ameliorations",
                improvements_panel,
            ),
            (
                "Qualite PMD",
                pmd_panel,
            ),
            (
                "Comp. Orphelin",
                health_panel,
            ),
        ],
    )
