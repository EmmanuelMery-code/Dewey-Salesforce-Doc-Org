"""Panneaux auxiliaires de la page index HTML."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from src.analyzer.models import Finding
from src.core.models import MetadataSnapshot, PmdViolation, ReviewResult
from src.core.utils import html_value
from src.reporting.html.findings import render_findings_summary
from src.reporting.html.page_shell import href_relative, tabbed_sections


def render_index_omni_panel(
    omni_pages: dict[str, list[dict[str, object]]],
    current_path: Path,
) -> str:
    if not omni_pages:
        return "<p class='empty'>Aucun composant OmniStudio detecte.</p>"

    sections: list[tuple[str, str]] = []
    for subcategory in sorted(omni_pages.keys(), key=lambda value: value.lower()):
        entries = omni_pages[subcategory]
        if not entries:
            rows = "<tr><td colspan='3' class='empty'>Aucun composant dans cette categorie.</td></tr>"
        else:
            rendered_rows: list[str] = []
            for entry in entries:
                name = str(entry.get("name") or "")
                page_path = entry.get("page")
                source = str(entry.get("source") or "")
                file_type = str(entry.get("type") or "")
                if isinstance(page_path, Path):
                    link = f"<a href='{href_relative(current_path, page_path)}'>{html_value(name)}</a>"
                else:
                    link = html_value(name)
                rendered_rows.append(
                    f"<tr><td>{link}</td><td>{html_value(file_type)}</td><td>{html_value(source)}</td></tr>"
                )
            rows = "".join(rendered_rows)

        label = f"{subcategory} ({len(entries)})"
        table = (
            "<table><thead><tr><th>Composant</th><th>Type</th><th>Source</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )
        sections.append((label, table))

    return tabbed_sections("index-omni", sections)


def render_index_analyzer_panel(
    analyzer_report,
    current_path: Path,
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    flow_pages: dict[str, Path],
    agent_pages: dict[str, Path] | None = None,
    prompt_pages: dict[str, Path] | None = None,
) -> str:
    if analyzer_report is None:
        return "<p class='empty'>Analyseur non execute.</p>"

    findings = analyzer_report.all_findings()
    summary = render_findings_summary(findings)
    if not findings:
        return summary + "<p class='empty'>Aucun finding : le projet respecte toutes les regles activees.</p>"

    findings_by_sev: dict[str, list[Finding]] = {
        "Critical": [],
        "Major": [],
        "Minor": [],
        "Info": [],
    }
    for finding in findings:
        if finding.rule.severity in findings_by_sev:
            findings_by_sev[finding.rule.severity].append(finding)

    def _render_severity_table(sev_findings: list[Finding]) -> str:
        if not sev_findings:
            return "<p class='empty'>Aucun finding pour cette severite.</p>"

        comp_findings: dict[tuple[str, str, str], list[Finding]] = {}
        for finding in sev_findings:
            key = (finding.target_kind, finding.target_name, "")
            comp_findings.setdefault(key, []).append(finding)

        rows = []
        for (kind, name, _), flist in sorted(comp_findings.items()):
            href = ""
            if kind == "Objet":
                page = object_pages.get(name)
                href = href_relative(current_path, page) if page else ""
            elif kind == "Apex":
                page = apex_pages.get(name)
                href = href_relative(current_path, page) if page else ""
            elif kind == "Flow":
                page = flow_pages.get(name)
                href = href_relative(current_path, page) if page else ""
            elif kind == "Agent" and agent_pages:
                page = agent_pages.get(name)
                href = href_relative(current_path, page) if page else ""
            elif kind == "Prompt" and prompt_pages:
                page = prompt_pages.get(name)
                href = href_relative(current_path, page) if page else ""

            name_cell = (
                f"<a href='{html_value(href)}'>{html_value(name)}</a>"
                if href
                else html_value(name)
            )
            rules_list = "<ul>" + "".join(
                f"<li>{html_value(f.rule.title)}: {html_value(f.message)}</li>"
                for f in flist
            ) + "</ul>"
            rows.append(
                f"<tr><td>{html_value(kind)}</td><td>{name_cell}</td><td>{rules_list}</td></tr>"
            )

        return f"<table><thead><tr><th>Type</th><th>Composant</th><th>Regles impactees</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"

    sections = [
        ("Critique", _render_severity_table(findings_by_sev["Critical"])),
        ("Majeur", _render_severity_table(findings_by_sev["Major"])),
        ("Mineur", _render_severity_table(findings_by_sev["Minor"])),
        ("Info", _render_severity_table(findings_by_sev["Info"])),
    ]
    note = (
        "<p class='empty'>Analyseur inspire de "
        "<a href='https://docs.pmd-code.org/latest/pmd_rules_apex.html' target='_blank' rel='noopener'>PMD Apex</a>, du "
        "<a href='https://architect.salesforce.com/docs/architect/well-architected/guide/overview.html' target='_blank' rel='noopener'>Salesforce Well-Architected Framework</a>, "
        "des <a href='https://architect.salesforce.com/decision-guides' target='_blank' rel='noopener'>Decision Guides Salesforce</a> et des bonnes pratiques "
        "<a href='https://admin.salesforce.com/' target='_blank' rel='noopener'>Salesforce Admins</a>. "
        "Les regles sont declarees dans <code>src/analyzer/rules.xml</code> et peuvent etre activees / desactivees via l'attribut <code>enabled</code>.</p>"
    )

    return summary + tabbed_sections("index-analyzer", sections) + note


def render_excel_exports(root_dir: Path, current_path: Path) -> str:
    excel_dir = root_dir / "excel"
    html_excel_dir = root_dir / "html" / "excel"

    if not excel_dir.exists():
        return "<p class='empty'>Aucun export Excel detecte.</p>"

    files = sorted(excel_dir.glob("*.xlsx"), key=lambda path: path.name.lower())
    if not files:
        return "<p class='empty'>Aucun export Excel detecte.</p>"

    rows: list[str] = []
    for file_path in files:
        xlsx_href = href_relative(current_path, file_path)
        preview_path = html_excel_dir / f"{file_path.stem}.html"

        if preview_path.exists():
            preview_href = href_relative(current_path, preview_path)
            preview_cell = f"<a href='{preview_href}'>{html_value(file_path.stem)}</a>"
        else:
            preview_cell = f"<span class='empty'>{html_value(file_path.stem)}</span>"
        rows.append(
            f"<tr><td>{preview_cell}</td>"
            f"<td><a href='{xlsx_href}'>{html_value(file_path.name)}</a></td></tr>"
        )
    return (
        "<table><thead><tr><th>Apercu HTML</th><th>Fichier Excel</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_diagram_exports(root_dir: Path, current_path: Path) -> str:
    """Liste les diagrammes ``.drawio`` ecrits dans ``diagrams/``.

    Le contenu d'un ``.drawio`` n'est pas rendu ici : le fichier s'ouvre dans
    draw.io (ou l'extension VS Code), ce que le tableau annonce en listant les
    onglets qu'il contient pour eviter d'avoir a l'ouvrir pour le savoir.
    """

    diagrams_dir = root_dir / "diagrams"
    files = (
        sorted(diagrams_dir.glob("*.drawio"), key=lambda path: path.name.lower())
        if diagrams_dir.exists()
        else []
    )
    if not files:
        return (
            "<p class='empty'>Aucun diagramme genere. Le diagramme du modele de "
            "donnees couvre les objets coches dans l'ecran Data Dictionnary : "
            "sans selection, il n'est pas produit.</p>"
        )

    rows: list[str] = []
    for file_path in files:
        href = href_relative(current_path, file_path)
        tabs = ", ".join(_drawio_tab_names(file_path)) or "-"
        rows.append(
            f"<tr><td><a href='{href}'>{html_value(file_path.name)}</a></td>"
            f"<td>{html_value(tabs)}</td></tr>"
        )
    return (
        "<p>Diagrammes ouvrables dans draw.io. Chaque onglet du fichier est une "
        "vue du modele : vue d'ensemble, domaines d'objets lies, satellites, "
        "puis objets sans relation.</p>"
        "<table><thead><tr><th>Fichier</th><th>Onglets</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _drawio_tab_names(path: Path) -> list[str]:
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError):
        return []
    return [
        diagram.get("name") or "" for diagram in root.iter("diagram")
    ]


def render_index_improvements(
    snapshot: MetadataSnapshot,
    apex_reviews: dict[str, ReviewResult],
    flow_reviews: dict[str, ReviewResult],
    current_path: Path,
    apex_pages: dict[str, Path],
    flow_pages: dict[str, Path],
) -> str:
    improvements_by_type: dict[str, list[str]] = {}

    for artifact in snapshot.apex_artifacts:
        review = apex_reviews.get(artifact.name)
        if review is None:
            continue

        kind = f"Apex/{artifact.kind}"
        improvements_by_type.setdefault(kind, [])
        page = apex_pages.get(artifact.name)
        component = (
            f"<a href='{href_relative(current_path, page)}'>{html_value(artifact.name)}</a>"
            if page
            else html_value(artifact.name)
        )

        for improvement in review.improvements:
            improvements_by_type[kind].append(
                f"<tr><td>{component}</td><td>{html_value(improvement)}</td></tr>"
            )

    for flow in snapshot.flows:
        review = flow_reviews.get(flow.name)
        if review is None:
            continue

        kind = "Flow"
        improvements_by_type.setdefault(kind, [])
        page = flow_pages.get(flow.name)
        component = (
            f"<a href='{href_relative(current_path, page)}'>{html_value(flow.name)}</a>"
            if page
            else html_value(flow.name)
        )

        for improvement in review.improvements:
            improvements_by_type[kind].append(
                f"<tr><td>{component}</td><td>{html_value(improvement)}</td></tr>"
            )

    if not improvements_by_type:
        return "<p class='empty'>Aucune amelioration detectee.</p>"

    sections: list[tuple[str, str]] = []
    for kind in sorted(improvements_by_type.keys()):
        rows = improvements_by_type[kind]
        label = f"{kind} ({len(rows)})"
        table = (
            "<table><thead><tr><th>Composant</th><th>Amelioration</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
        sections.append((label, table))

    return tabbed_sections("index-improvements", sections)


def render_index_pmd_panel(
    snapshot: MetadataSnapshot,
    pmd_results: dict[str, list[PmdViolation]],
    current_path: Path,
    apex_pages: dict[str, Path],
) -> str:
    violations_by_rule: dict[str, list[str]] = {}

    for artifact in snapshot.apex_artifacts:
        violations = pmd_results.get(artifact.name, [])
        if not violations:
            continue

        target = apex_pages.get(artifact.name)
        component = (
            f"<a href='{href_relative(current_path, target)}'>{html_value(artifact.name)}</a>"
            if target
            else html_value(artifact.name)
        )

        for violation in violations:
            violations_by_rule.setdefault(violation.rule, [])
            line_value = violation.begin_line or ""
            violations_by_rule[violation.rule].append(
                f"<tr><td>{component}</td><td>{html_value(violation.priority)}</td><td>{html_value(line_value)}</td><td>{html_value(violation.message)}</td></tr>"
            )

    if not violations_by_rule:
        return "<p class='empty'>Aucune violation PMD detectee.</p>"

    sections: list[tuple[str, str]] = []
    for rule in sorted(violations_by_rule.keys()):
        rows = violations_by_rule[rule]
        label = f"{rule} ({len(rows)})"
        table = (
            "<table><thead><tr><th>Composant</th><th>Priorite</th><th>Ligne</th><th>Message</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
        sections.append((label, table))

    return tabbed_sections("index-pmd", sections)


def render_index_dependencies_panel(
    snapshot: MetadataSnapshot,
    current_path: Path,
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    flow_pages: dict[str, Path],
    agent_pages: dict[str, Path] | None = None,
    prompt_pages: dict[str, Path] | None = None,
) -> str:
    if not snapshot.dependencies:
        return "<p class='empty'>Aucune dependance detectee.</p>"

    def _get_link(name: str, kind: str) -> str:
        href = ""
        if kind == "Objet":
            page = object_pages.get(name)
            if page:
                href = href_relative(current_path, page)
        elif kind == "Apex":
            page = apex_pages.get(name)
            if page:
                href = href_relative(current_path, page)
        elif kind == "Flow":
            page = flow_pages.get(name)
            if page:
                href = href_relative(current_path, page)
        elif kind == "Agent" and agent_pages:
            page = agent_pages.get(name)
            if page:
                href = href_relative(current_path, page)
        elif kind == "Prompt" and prompt_pages:
            page = prompt_pages.get(name)
            if page:
                href = href_relative(current_path, page)

        if href:
            return f"<a href='{html_value(href)}'>{html_value(name)}</a>"
        return html_value(name)

    deps_by_kind: dict[str, list[str]] = {}
    for dep in sorted(
        snapshot.dependencies, key=lambda d: (d.source_kind, d.source_name, d.target_name)
    ):
        kind = dep.source_kind or "Autre"
        deps_by_kind.setdefault(kind, [])
        deps_by_kind[kind].append(
            f"<tr><td>{_get_link(dep.source_name, dep.source_kind)}</td>"
            f"<td>{_get_link(dep.target_name, dep.target_kind)}</td>"
            f"<td>{html_value(dep.target_kind)}</td></tr>"
        )

    sections: list[tuple[str, str]] = []
    for kind in sorted(deps_by_kind.keys()):
        rows = deps_by_kind[kind]
        label = f"{kind} ({len(rows)})"
        table = (
            "<table><thead><tr><th>Source</th><th>Cible</th><th>Type Cible</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
        sections.append((label, table))

    return tabbed_sections("index-dependencies", sections)
