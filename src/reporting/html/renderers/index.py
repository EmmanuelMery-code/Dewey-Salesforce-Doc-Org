"""Render the main ``index.html`` documentation home page."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from src.analyzer.models import Finding
from src.core.ai_usage import AIUsageEntry, AIUsageStats
from src.core.customization_metrics import (
    AdoptionStats,
    DataModelCustomisationStats,
)
from src.core.index_card_visibility import IndexCardVisibility
from src.core.models import (
    AuraInfo,
    LwcInfo,
    MetadataSnapshot,
    PmdViolation,
    ReviewResult,
)
from src.core.utils import html_value, write_text

from src.reporting.html.assets import SEVERITY_CSS_CLASS, SEVERITY_LABEL
from src.reporting.html.findings import render_findings_summary
from src.reporting.html.page_shell import (
    href_relative,
    render_page,
    tabbed_sections,
)


LogCallback = Callable[[str], None]


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
) -> str:
    if analyzer_report is None:
        return "<p class='empty'>Analyseur non execute.</p>"

    findings = analyzer_report.all_findings()
    summary = render_findings_summary(findings)
    if not findings:
        return summary + "<p class='empty'>Aucun finding : le projet respecte toutes les regles activees.</p>"

    rule_counts = analyzer_report.rule_counts()
    rules_by_id = {rule.id: rule for rule in analyzer_report.rules_used}
    rule_rows = []
    for rule_id, count in sorted(rule_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        rule = rules_by_id.get(rule_id)
        if not rule:
            continue
        sev_css = SEVERITY_CSS_CLASS.get(rule.severity, "sev-info")
        sev_label = SEVERITY_LABEL.get(rule.severity, rule.severity)
        reference = ""
        if rule.reference:
            reference = f"<a href='{html_value(rule.reference)}' target='_blank' rel='noopener'>Reference</a>"
        rule_rows.append(
            f"<tr>"
            f"<td><span class='sev-badge {sev_css}'>{html_value(sev_label)}</span></td>"
            f"<td>{html_value(rule.id)}</td>"
            f"<td>{html_value(rule.title)}</td>"
            f"<td>{html_value(rule.category)} - {html_value(rule.subcategory)}</td>"
            f"<td>{count}</td>"
            f"<td>{reference}</td>"
            f"</tr>"
        )
    rule_table = (
        "<table><thead><tr><th>Severite</th><th>Identifiant</th><th>Regle</th><th>Categorie</th><th>Occurrences</th><th>Reference</th></tr></thead>"
        f"<tbody>{''.join(rule_rows)}</tbody></table>"
    )

    artifact_rows: list[str] = []

    def _artifact_row(kind: str, name: str, findings_list: list[Finding], href: str) -> str:
        if not findings_list:
            return ""
        counts = {"Critical": 0, "Major": 0, "Minor": 0, "Info": 0}
        for finding in findings_list:
            counts[finding.rule.severity] = counts.get(finding.rule.severity, 0) + 1
        sev_cells = "".join(
            f"<td>{counts.get(sev, 0)}</td>"
            for sev in ("Critical", "Major", "Minor", "Info")
        )
        name_cell = (
            f"<a href='{html_value(href)}'>{html_value(name)}</a>" if href else html_value(name)
        )
        return (
            f"<tr><td>{html_value(kind)}</td><td>{name_cell}</td>"
            f"{sev_cells}<td>{len(findings_list)}</td></tr>"
        )

    for name, flist in analyzer_report.objects.items():
        page = object_pages.get(name)
        href = href_relative(current_path, page) if page else ""
        row = _artifact_row("Objet", name, flist, href)
        if row:
            artifact_rows.append(row)

    for name, flist in analyzer_report.apex.items():
        page = apex_pages.get(name)
        href = href_relative(current_path, page) if page else ""
        row = _artifact_row("Apex", name, flist, href)
        if row:
            artifact_rows.append(row)

    for name, flist in analyzer_report.flows.items():
        page = flow_pages.get(name)
        href = href_relative(current_path, page) if page else ""
        row = _artifact_row("Flow", name, flist, href)
        if row:
            artifact_rows.append(row)

    for name, flist in analyzer_report.validation_rules.items():
        row = _artifact_row("Validation Rule", name, flist, "")
        if row:
            artifact_rows.append(row)

    for name, flist in analyzer_report.data_transforms.items():
        row = _artifact_row("Data Transform", name, flist, "")
        if row:
            artifact_rows.append(row)

    for name, flist in analyzer_report.lwc.items():
        row = _artifact_row("LWC", name, flist, "")
        if row:
            artifact_rows.append(row)

    for name, flist in analyzer_report.aura.items():
        row = _artifact_row("Aura", name, flist, "")
        if row:
            artifact_rows.append(row)

    artifact_rows.sort()
    if not artifact_rows:
        artifact_table = "<p class='empty'>Aucun composant impacte.</p>"
    else:
        artifact_table = (
            "<table><thead><tr><th>Type</th><th>Composant</th>"
            "<th>Critique</th><th>Majeur</th><th>Mineur</th><th>Info</th><th>Total</th></tr></thead>"
            f"<tbody>{''.join(artifact_rows)}</tbody></table>"
        )

    note = (
        "<p class='empty'>Analyseur inspire de "
        "<a href='https://docs.pmd-code.org/latest/pmd_rules_apex.html' target='_blank' rel='noopener'>PMD Apex</a>, du "
        "<a href='https://architect.salesforce.com/docs/architect/well-architected/guide/overview.html' target='_blank' rel='noopener'>Salesforce Well-Architected Framework</a>, "
        "des <a href='https://architect.salesforce.com/decision-guides' target='_blank' rel='noopener'>Decision Guides Salesforce</a> et des bonnes pratiques "
        "<a href='https://admin.salesforce.com/' target='_blank' rel='noopener'>Salesforce Admins</a>. "
        "Les regles sont declarees dans <code>src/analyzer/rules.xml</code> et peuvent etre activees / desactivees via l'attribut <code>enabled</code>.</p>"
    )

    sections = [
        ("Synthese par regle", rule_table),
        ("Par composant", artifact_table),
    ]
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
            preview_cell = (
                f"<a href='{preview_href}'>{html_value(file_path.stem)}</a>"
            )
        else:
            preview_cell = (
                f"<span class='empty'>{html_value(file_path.stem)}</span>"
            )
        rows.append(
            f"<tr><td>{preview_cell}</td>"
            f"<td><a href='{xlsx_href}'>{html_value(file_path.name)}</a></td></tr>"
        )
    return (
        "<table><thead><tr><th>Apercu HTML</th><th>Fichier Excel</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_index_improvements(
    snapshot: MetadataSnapshot,
    apex_reviews: dict[str, ReviewResult],
    flow_reviews: dict[str, ReviewResult],
    current_path: Path,
    apex_pages: dict[str, Path],
    flow_pages: dict[str, Path],
) -> str:
    rows: list[str] = []
    for artifact in snapshot.apex_artifacts:
        review = apex_reviews.get(artifact.name)
        if review is None:
            continue
        page = apex_pages.get(artifact.name)
        if page:
            component = f"<a href='{href_relative(current_path, page)}'>{html_value(artifact.name)}</a>"
        else:
            component = html_value(artifact.name)
        for improvement in review.improvements:
            rows.append(
                f"<tr><td>Apex/{html_value(artifact.kind)}</td><td>{component}</td><td>{html_value(improvement)}</td></tr>"
            )

    for flow in snapshot.flows:
        review = flow_reviews.get(flow.name)
        if review is None:
            continue
        page = flow_pages.get(flow.name)
        if page:
            component = f"<a href='{href_relative(current_path, page)}'>{html_value(flow.name)}</a>"
        else:
            component = html_value(flow.name)
        for improvement in review.improvements:
            rows.append(
                f"<tr><td>Flow</td><td>{component}</td><td>{html_value(improvement)}</td></tr>"
            )

    return "".join(rows) or "<tr><td colspan='3' class='empty'>Aucune amelioration detectee.</td></tr>"


def render_index_pmd_rows(
    snapshot: MetadataSnapshot,
    pmd_results: dict[str, list[PmdViolation]],
    current_path: Path,
    apex_pages: dict[str, Path],
) -> str:
    rows: list[str] = []
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
            line_value = violation.begin_line or ""
            rows.append(
                f"<tr><td>{component}</td><td>{html_value(violation.rule)}</td>"
                f"<td>{html_value(violation.priority)}</td><td>{html_value(line_value)}</td>"
                f"<td>{html_value(violation.message)}</td></tr>"
            )
    return "".join(rows) or "<tr><td colspan='5' class='empty'>Aucune violation PMD detectee.</td></tr>"


def render_index_dependencies_panel(snapshot: MetadataSnapshot) -> str:
    if not snapshot.dependencies:
        return "<p class='empty'>Aucune dependance detectee.</p>"

    rows = []
    for dep in sorted(snapshot.dependencies, key=lambda d: (d.source_kind, d.source_name)):
        rows.append(
            f"<tr>"
            f"<td>{html_value(dep.source_name)}</td>"
            f"<td>{html_value(dep.source_kind)}</td>"
            f"<td>{html_value(dep.target_name)}</td>"
            f"<td>{html_value(dep.target_kind)}</td>"
            f"</tr>"
        )

    return (
        "<table><thead><tr><th>Source</th><th>Type Source</th><th>Cible</th><th>Type Cible</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_index(
    snapshot: MetadataSnapshot,
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    flow_pages: dict[str, Path],
    apex_reviews: dict[str, ReviewResult],
    flow_reviews: dict[str, ReviewResult],
    pmd_results: dict[str, list[PmdViolation]],
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    omni_pages: dict[str, list[dict[str, object]]],
    agent_pages: dict[str, Path] = None,
    prompt_pages: dict[str, Path] = None,
    listing_pages: dict[str, Path] = None,
    security_pages: dict[str, Path] | None = None,
    analyzer_report=None,
    ai_usage_entries: list[AIUsageEntry] | None = None,
    ai_usage_page: Path | None = None,
    ai_usage_stats: AIUsageStats | None = None,
    data_model_stats: DataModelCustomisationStats | None = None,
    adoption_stats: AdoptionStats | None = None,
    customisation_page: Path | None = None,
    adoption_page: Path | None = None,
    debt_page: Path | None = None,
    innovation_page: Path | None = None,
    findings_report_page: Path | None = None,
    card_visibility: IndexCardVisibility | None = None,
    root_output_dir: Path | None = None,
    alias: str = "",
) -> str:
    metrics = snapshot.metrics
    visibility = card_visibility or IndexCardVisibility()
    listing = listing_pages or {}

    def _listing_link(key: str, title: str, count: int) -> str:
        """Wrap title in a link to the listing page when count > 0 and page exists."""
        page = listing.get(key)
        if count > 0 and page:
            return f"<a href='{href_relative(current_path, page)}' style='color:inherit;text-decoration:none;'>{title}</a>"
        return title
    
    # Use the provided root_output_dir or fall back to output_dir's parent if it's named 'html'
    root_dir = root_output_dir
    if root_dir is None:
        if output_dir.name == "html":
            root_dir = output_dir.parent
        else:
            root_dir = output_dir

    object_rows = "".join(
        f"<tr><td><a href='{href_relative(current_path, object_pages[item.api_name])}'>{html_value(item.api_name)}</a></td>"
        f"<td>{html_value(item.label)}</td><td>{len(item.fields)}</td><td>{len(item.relationships)}</td>"
        f"<td>{len(item.validation_rules)} (Σ={sum(vr.complexity_score for vr in item.validation_rules)})</td></tr>"
        for item in snapshot.objects
        if item.api_name in object_pages
    ) or "<tr><td colspan='5' class='empty'>Aucun objet analyse.</td></tr>"

    _DANGER_PERMS = {"ModifyAllData", "ManageUsers"}
    _PERM_COLORS = {"ModifyAllData": "#ff4444", "ManageUsers": "#ff8c00"}

    def _profile_risk(item):
        if any(up.enabled and up.name == "ModifyAllData" for up in item.user_permissions):
            return "danger"
        if any(up.enabled and up.name == "ManageUsers" for up in item.user_permissions):
            return "major"
        if any(op.modify_all_records for op in item.object_permissions):
            return "minor"
        return "ok"

    _risk_style = {
        "danger": "background:rgba(255,68,68,.08);color:#c00",
        "major":  "background:rgba(255,140,0,.08);color:#a04000",
        "minor":  "background:rgba(240,220,0,.08);color:#665500",
        "ok":     "",
    }
    _risk_label = {"danger": "⚠ CRITIQUE", "major": "⚠ RISQUE", "minor": "⚠ ATTENTION", "ok": ""}

    def _sec_findings_badge(name, report):
        if report is None or name not in report.security:
            return ""
        fs = report.security[name]
        if any(f.rule.severity == "Critical" for f in fs):
            return " <span style='color:#ff4444;font-weight:bold'>● CRITIQUE</span>"
        if any(f.rule.severity == "Major" for f in fs):
            return " <span style='color:#ff8c00;font-weight:bold'>● MAJEUR</span>"
        if fs:
            return " <span style='color:#ccbb00;font-weight:bold'>●</span>"
        return ""

    def _profile_name_cell(item, pages):
        name = html_value(item.name)
        if item.name in pages:
            name = f"<a href='{href_relative(current_path, pages[item.name])}'>{html_value(item.name)}</a>"
        badge = _sec_findings_badge(item.name, analyzer_report)
        return f"<td>{name}{badge}</td>"

    def _security_artifact_row(item, pages, is_profile=True):
        risk = _profile_risk(item)
        row_style = _risk_style[risk]
        risk_label = _risk_label[risk]
        risk_color = '#ff4444' if risk in ('danger','major','minor') else ''
        
        kind_label = ('Custom' if item.is_custom else 'Standard') if is_profile else 'Permission Set'
        
        return (
            f"<tr style='{row_style}'>"
            + _profile_name_cell(item, pages)
            + f"<td>{kind_label}</td>"
            + f"<td style='color:{risk_color}'>{risk_label}</td>"
            + f"<td>{len(item.object_permissions)}</td>"
            + f"<td>{len(item.field_permissions)}</td></tr>"
        )

    profile_detail_pages = {k.split(":", 1)[1]: v for k, v in (security_pages or {}).items() if k.startswith("profile:")}
    permset_detail_pages = {k.split(":", 1)[1]: v for k, v in (security_pages or {}).items() if k.startswith("permset:")}

    profile_rows = "".join(
        _security_artifact_row(item, profile_detail_pages, is_profile=True)
        for item in snapshot.profiles
    ) or "<tr><td colspan='5' class='empty'>Aucun profil analysé.</td></tr>"

    permset_rows = "".join(
        _security_artifact_row(item, permset_detail_pages, is_profile=False)
        for item in snapshot.permission_sets
    ) or "<tr><td colspan='5' class='empty'>Aucun permission set analysé.</td></tr>"

    # Security dashboard summary
    m = snapshot.metrics
    ratio_pct = m.profiles_ps_ratio_score
    ratio_level = m.profiles_ps_ratio_level
    _ratio_colors = {"Bon": "#22aa66", "Attention": "#ccbb00", "Risque": "#ff8c00", "Critique": "#ff4444"}
    ratio_color = _ratio_colors.get(ratio_level, "#888")
    profiles_list_href = ""
    permsets_list_href = ""
    if security_pages:
        if "profiles_list" in security_pages:
            profiles_list_href = href_relative(current_path, security_pages["profiles_list"])
        if "permsets_list" in security_pages:
            permsets_list_href = href_relative(current_path, security_pages["permsets_list"])

    _profiles_title = (
        f"<a href='{profiles_list_href}'>Profiles</a>"
        if profiles_list_href else "Profiles"
    )
    _permsets_title = (
        f"<a href='{permsets_list_href}'>Permission Sets</a>"
        if permsets_list_href else "Permission Sets"
    )

    security_dashboard = f"""
<div class='section'>
    <div class='topnav'>
        <a href='{href_relative(current_path, security_pages.get("security_matrix")) if security_pages else "#"}'>Voir la matrice de securite (CRUD)</a> | 
        <a href='{href_relative(current_path, security_pages.get("psg_list")) if security_pages else "#"}'>Voir les Permission Set Groups</a>
    </div>
    <div style='display:flex;gap:16px;flex-wrap:wrap;margin-bottom:14px'>
      <div style='flex:1;min-width:200px;padding:10px 14px;border:1px solid #e2e8f0;border-radius:6px'>
        <div style='font-size:.8em;color:#64748b'>Profils custom</div>
        <div style='font-size:1.5em;font-weight:bold'>{m.custom_profiles_count}</div>
        <div style='font-size:.8em;color:#64748b'>sur {m.profiles_count} profils total</div>
      </div>
      <div style='flex:1;min-width:200px;padding:10px 14px;border:1px solid #e2e8f0;border-radius:6px'>
        <div style='font-size:.8em;color:#64748b'>Permission Sets</div>
        <div style='font-size:1.5em;font-weight:bold'>{m.permission_sets_count}</div>
      </div>
      <div style='flex:1;min-width:200px;padding:10px 14px;border:1px solid {ratio_color}33;border-radius:6px'>
        <div style='font-size:.8em;color:#64748b'>Ratio Profils/PS</div>
        <div style='font-size:1.5em;font-weight:bold;color:{ratio_color}'>{ratio_pct}%</div>
        <div style='font-size:.8em;color:{ratio_color};font-weight:bold'>{ratio_level}</div>
      </div>
      <div style='flex:1;min-width:200px;padding:10px 14px;border:1px solid {"#ff444433" if m.dangerous_profiles_count else "#e2e8f0"};border-radius:6px'>
        <div style='font-size:.8em;color:#64748b'>Profils dangereux</div>
        <div style='font-size:1.5em;font-weight:bold;color:{"#ff4444" if m.dangerous_profiles_count else "#22aa66"}'>{m.dangerous_profiles_count}</div>
        <div style='font-size:.8em;color:#64748b'>ModifyAllData / ManageUsers</div>
      </div>
      <div style='flex:1;min-width:200px;padding:10px 14px;border:1px solid {"#ff8c0033" if m.profiles_with_modify_all else "#e2e8f0"};border-radius:6px'>
        <div style='font-size:.8em;color:#64748b'>Profils avec ModifyAllRecords</div>
        <div style='font-size:1.5em;font-weight:bold;color:{"#ff8c00" if m.profiles_with_modify_all else "#22aa66"}'>{m.profiles_with_modify_all}</div>
      </div>
      <div style='flex:1;min-width:200px;padding:10px 14px;border:1px solid {"#ccbb0033" if m.perm_sets_with_modify_all else "#e2e8f0"};border-radius:6px'>
        <div style='font-size:.8em;color:#64748b'>PS avec ModifyAll (objets sensibles)</div>
        <div style='font-size:1.5em;font-weight:bold;color:{"#ccbb00" if m.perm_sets_with_modify_all else "#22aa66"}'>{m.perm_sets_with_modify_all}</div>
      </div>
    </div>
    <table><thead><tr><th>Profil / Permission Set</th><th>Type</th><th>Risque</th><th>Droits objet</th><th>Droits champ</th></tr></thead><tbody>{profile_rows}{permset_rows}</tbody></table>
</div>"""

    TYPE_LABELS_SR = {"criteria": "Critères", "owner": "Propriétaire", "guest": "Utilisateur invité", "territory": "Territoire"}
    sharing_rule_rows = "".join(
        f"<tr><td>{html_value(r.object_name)}</td><td>{html_value(r.full_name)}</td>"
        f"<td>{html_value(TYPE_LABELS_SR.get(r.rule_type, r.rule_type))}</td>"
        f"<td>{html_value(r.label)}</td><td>{html_value(r.description)}</td></tr>"
        for r in snapshot.sharing_rules
    ) or "<tr><td colspan='5' class='empty'>Aucune sharing rule analysée.</td></tr>"

    apex_rows = "".join(
        f"<tr><td><a href='{href_relative(current_path, apex_pages[item.name])}'>{html_value(item.name)}</a></td>"
        f"<td>{html_value(item.kind)}</td><td>{item.line_count}</td><td>{item.method_count}</td>"
        f"<td>{(f'{item.test_coverage:.1f}% ({item.test_coverage_lines_covered}/{item.test_coverage_lines_covered + item.test_coverage_lines_uncovered} lignes)') if item.test_coverage is not None else 'N/A'}</td></tr>"
        for item in snapshot.apex_artifacts
        if item.name in apex_pages
    ) or "<tr><td colspan='5' class='empty'>Aucun artefact Apex analyse.</td></tr>"

    flow_rows = "".join(
        f"<tr><td><a href='{href_relative(current_path, flow_pages[item.name])}'>{html_value(item.name)}</a></td>"
        f"<td>{html_value(item.process_type)}</td><td>{html_value(item.complexity_level)}</td><td>{item.complexity_score}</td><td>{item.total_elements}</td>"
        f"<td>{'⚠' if item.soql_in_loop or item.dml_in_loop else 'OK'}</td>"
        f"<td>{(f'{item.test_coverage:.1f}% ({item.test_coverage_elements_covered}/{item.test_coverage_elements_covered + item.test_coverage_elements_uncovered} blocs)') if item.test_coverage is not None else 'N/A'}</td></tr>"
        for item in snapshot.flows
        if item.name in flow_pages
    ) or "<tr><td colspan='7' class='empty'>Aucun flow analyse.</td></tr>"

    improvements_rows = render_index_improvements(
        snapshot,
        apex_reviews,
        flow_reviews,
        current_path,
        apex_pages,
        flow_pages,
    )
    pmd_rows = render_index_pmd_rows(
        snapshot,
        pmd_results,
        current_path,
        apex_pages,
    )
    excel_links = render_excel_exports(root_dir, current_path)
    omni_panel = render_index_omni_panel(omni_pages, current_path)
    
    agent_rows = "".join(
        f"<tr><td><a href='{href_relative(current_path, agent_pages[item.name])}'>{html_value(item.name)}</a></td>"
        f"<td>{html_value(item.label)}</td><td>{html_value(item.description)}</td></tr>"
        for item in snapshot.agents
        if item.name in agent_pages
    ) or "<tr><td colspan='3' class='empty'>Aucun agent analyse.</td></tr>"

    prompt_rows = "".join(
        f"<tr><td><a href='{href_relative(current_path, prompt_pages[item.name])}'>{html_value(item.name)}</a></td>"
        f"<td>{html_value(item.label)}</td><td>{html_value(item.description)}</td></tr>"
        for item in snapshot.gen_ai_prompts
        if item.name in prompt_pages
    ) or "<tr><td colspan='3' class='empty'>Aucun prompt analyse.</td></tr>"

    analyzer_panel = render_index_analyzer_panel(
        analyzer_report,
        current_path,
        object_pages,
        apex_pages,
        flow_pages,
    )

    dependencies_panel = render_index_dependencies_panel(snapshot)
    
    vr_header = (
        '<span title="Nombre de règles de validation et score de complexité cumulé (Σ). '
        'Le score est calculé selon la longueur de la formule (1pt par 50 car.) '
        'et le nombre d\'opérateurs logiques (IF, AND, OR, CASE, parenthèses).">'
        'VR (Complexité)</span>'
    )
    # ── Org Health ───────────────────────────────────────────────────
    orphan_rows = "".join(
        f"<tr><td>{html_value(o.name)}</td><td>{html_value(o.kind)}</td></tr>"
        for o in snapshot.orphans
    ) or "<tr><td colspan='2' class='empty'>Aucun composant orphelin detecte.</td></tr>"
    
    redundant_flow_rows = "".join(
        f"<tr><td>{html_value(g.object_name)}</td><td>{html_value(g.trigger_type)}</td><td>{', '.join(g.flows)}</td></tr>"
        for g in snapshot.redundant_flows
    ) or "<tr><td colspan='3' class='empty'>Aucune redondance de Flow detectee.</td></tr>"
    
    health_panel = f"""
<h3>Composants Orphelins</h3>
<p>Composants non references dans Apex, Flows ou Rapports.</p>
<table><thead><tr><th>Nom</th><th>Type</th></tr></thead><tbody>{orphan_rows}</tbody></table>
<h3>Redondance des Flows</h3>
<p>Plusieurs Record-Triggered Flows actifs sur le meme objet et evenement.</p>
<table><thead><tr><th>Objet</th><th>Evenement</th><th>Flows</th></tr></thead><tbody>{redundant_flow_rows}</tbody></table>
"""

    tabs = tabbed_sections(
        "index",
        [
            (
                "Exports Excel",
                excel_links,
            ),
            (
                "Sante de l'Org",
                health_panel,
            ),
            (
                "Omni / BRE",
                omni_panel,
            ),
            (
                "Dependances",
                dependencies_panel,
            ),
            (
                "Agents",
                f"<table><thead><tr><th>Agent</th><th>Label</th><th>Description</th></tr></thead><tbody>{agent_rows}</tbody></table>",
            ),
            (
                "Prompts",
                f"<table><thead><tr><th>Prompt</th><th>Label</th><th>Description</th></tr></thead><tbody>{prompt_rows}</tbody></table>",
            ),
            (
                "Objets",
                f"<table><thead><tr><th>Objet</th><th>Label</th><th>Nb champs</th><th>Nb relations</th><th>{vr_header}</th></tr></thead><tbody>{object_rows}</tbody></table>",
            ),
            (
                "Profiles",
                security_dashboard
                + f"<h4>{_profiles_title} ({len(snapshot.profiles)})</h4>"
                + f"<table><thead><tr><th>Profil</th><th>Type</th><th>Risque</th><th>Droits objet</th><th>Droits champ</th></tr></thead><tbody>{profile_rows}</tbody></table>",
            ),
            (
                "Permission Sets",
                f"<h4>{_permsets_title} ({len(snapshot.permission_sets)})</h4>"
                + f"<table><thead><tr><th>Permission Set</th><th>Type</th><th>Risque</th><th>Droits objet</th><th>Droits champ</th></tr></thead><tbody>{permset_rows}</tbody></table>",
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
                f"<table><thead><tr><th>Nom</th><th>Type</th><th>Complexite</th><th>Score</th><th>Elements</th><th>DML/SOQL Boucle</th><th>% Couverture</th></tr></thead><tbody>{flow_rows}</tbody></table>",
            ),
            (
                "Analyseur",
                analyzer_panel,
            ),
            (
                "Ameliorations",
                f"<table><thead><tr><th>Type</th><th>Composant</th><th>Amelioration</th></tr></thead><tbody>{improvements_rows}</tbody></table>",
            ),
            (
                "Qualite PMD",
                f"<table><thead><tr><th>Composant</th><th>Regle</th><th>Priorite</th><th>Ligne</th><th>Message</th></tr></thead><tbody>{pmd_rows}</tbody></table>",
            ),
        ],
    )
    omni_total = (
        metrics.omni_scripts
        + metrics.omni_integration_procedures
        + metrics.omni_ui_cards
        + metrics.omni_data_transforms
        + metrics.bre_decision_matrices
        + metrics.bre_expression_sets
    )
    findings_card = ""
    if analyzer_report is not None and visibility.show_findings:
        findings = analyzer_report.all_findings()
        findings_total = len(findings)
        
        counts = {"Critical": 0, "Major": 0, "Minor": 0, "Info": 0}
        for f in findings:
            counts[f.rule.severity] = counts.get(f.rule.severity, 0) + 1
            
        severity_html = (
            f'<div class="ai-usage-grid" style="margin-top: 10px;">'
            f'  <div class="ai-usage-stat sev-critical" style="background: #fef2f2; border-color: #fca5a5; padding: 4px 8px;">'
            f'    <span style="font-size: 0.7rem; color: #991b1b;">CRITIQUE</span>'
            f'    <span style="font-size: 1.1rem; font-weight: 700; color: #991b1b;">{counts["Critical"]}</span>'
            f'  </div>'
            f'  <div class="ai-usage-stat sev-major" style="background: #fff7ed; border-color: #fdba74; padding: 4px 8px;">'
            f'    <span style="font-size: 0.7rem; color: #9a3412;">MAJEUR</span>'
            f'    <span style="font-size: 1.1rem; font-weight: 700; color: #9a3412;">{counts["Major"]}</span>'
            f'  </div>'
            f'  <div class="ai-usage-stat sev-minor" style="background: #fefce8; border-color: #facc15; padding: 4px 8px;">'
            f'    <span style="font-size: 0.7rem; color: #854d0e;">MINEUR</span>'
            f'    <span style="font-size: 1.1rem; font-weight: 700; color: #854d0e;">{counts["Minor"]}</span>'
            f'  </div>'
            f'  <div class="ai-usage-stat sev-info" style="background: #eff6ff; border-color: #93c5fd; padding: 4px 8px;">'
            f'    <span style="font-size: 0.7rem; color: #1e3a8a;">INFO</span>'
            f'    <span style="font-size: 1.1rem; font-weight: 700; color: #1e3a8a;">{counts["Info"]}</span>'
            f'  </div>'
            f'</div>'
        )

        if findings_report_page is not None:
            href = html_value(href_relative(current_path, findings_report_page))
            title_html = f'<a href="{href}">Findings analyseur</a>'
        else:
            title_html = 'Findings analyseur'

        findings_card = (
            f'  <div class="card" style="min-width: 320px;">'
            f'    <span>{title_html}</span>'
            f'    <span class="value">{findings_total}</span>'
            f'    {severity_html}'
            f'  </div>\n'
        )

    ai_usage_card = (
        _render_ai_usage_card(ai_usage_stats, ai_usage_page, current_path)
        if visibility.show_ai_usage
        else ""
    )
    data_model_card = (
        _render_data_model_card(data_model_stats, customisation_page, current_path)
        if visibility.show_data_model_footprint
        else ""
    )
    adoption_card = (
        _render_adoption_card(adoption_stats, adoption_page, current_path)
        if visibility.show_adopt_adapt_posture
        else ""
    )
    debt_card = (
        _render_debt_card(snapshot, debt_page, current_path)
        if visibility.show_debt
        else ""
    )
    innovation_card = (
        _render_innovation_card(snapshot, innovation_page, current_path)
        if visibility.show_innovation
        else ""
    )
    
    # Calculate Apex and Flow coverage averages
    apex_covered = 0
    apex_to_cover = 0
    for artifact in snapshot.apex_artifacts:
        if not artifact.is_test and artifact.test_coverage is not None:
            apex_covered += artifact.test_coverage_lines_covered
            apex_to_cover += artifact.test_coverage_lines_covered + artifact.test_coverage_lines_uncovered
    apex_coverage_avg = (apex_covered / apex_to_cover * 100) if apex_to_cover > 0 else None
    
    flow_covered = 0
    flow_to_cover = 0
    for flow in snapshot.flows:
        if flow.test_coverage is not None:
            flow_covered += flow.test_coverage_elements_covered
            flow_to_cover += flow.test_coverage_elements_covered + flow.test_coverage_elements_uncovered
    flow_coverage_avg = (flow_covered / flow_to_cover * 100) if flow_to_cover > 0 else None
    
    # Build coverage detail string - show only Apex and Flows, no org average
    apex_str = f"Apex: {apex_coverage_avg:.1f}%" if apex_coverage_avg is not None else "Apex: N/A"
    flow_str = f"Flow: {flow_coverage_avg:.1f}%" if flow_coverage_avg is not None else "Flow: N/A"
    coverage_details = f"{apex_str} | {flow_str}"
    
    test_coverage_card = (
        f'  <div class="card"><span>Couverture de tests</span>'
        f'<span class="value">{coverage_details}</span>'
        f'<small style="color: #64748b; font-weight: normal;">Par type (Apex + Flows)</small></div>\n'
        if visibility.show_test_coverage
        else ""
    )

    customization_level_card = (
        f'  <div class="card"><span>Niveau de customisation</span>'
        f'<span class="value">{html_value(metrics.level)}</span></div>\n'
        if visibility.show_customization_level
        else ""
    )
    score_card = (
        f'  <div class="card"><span>Score</span>'
        f'<span class="value">{metrics.score}</span>'
        f'<div style="display: flex; gap: 8px; margin-top: 4px; font-size: 0.75rem; color: #64748b;">'
        f'<span>No: {metrics.custom_objects * metrics._weight("custom_objects") + metrics.custom_fields * metrics._weight("custom_fields") + metrics.record_types * metrics._weight("record_types") + metrics.validation_rules * metrics._weight("validation_rules") + metrics.layouts * metrics._weight("layouts") + metrics.custom_tabs * metrics._weight("custom_tabs") + metrics.custom_apps * metrics._weight("custom_apps") + metrics.einstein_predictions * metrics._weight("einstein_predictions")}</span>'
        f'<span>Low: {metrics.flows * metrics._weight("flows") + metrics.omni_scripts * metrics._weight("omni_scripts") + metrics.omni_integration_procedures * metrics._weight("omni_integration_procedures") + metrics.omni_ui_cards * metrics._weight("omni_ui_cards") + metrics.omni_data_transforms * metrics._weight("omni_data_transforms") + metrics.bre_decision_matrices * metrics._weight("bre_decision_matrices") + metrics.bre_expression_sets * metrics._weight("bre_expression_sets") + metrics.gen_ai_prompts * metrics._weight("gen_ai_prompts")}</span>'
        f'<span>Pro: {metrics.apex_classes * metrics._weight("apex_classes") + metrics.apex_triggers * metrics._weight("apex_triggers") + metrics.agents * metrics._weight("agents")}</span>'
        f'</div></div>\n'
        if visibility.show_score
        else ""
    )
    adopt_vs_adapt_card = (
        f'  <div class="card"><span>Adopt vs Adapt</span>'
        f'<span class="value">{html_value(metrics.adopt_adapt_level)}</span></div>\n'
        if visibility.show_adopt_vs_adapt
        else ""
    )
    adopt_adapt_score_card = (
        f'  <div class="card"><span>Score Adopt vs Adapt</span>'
        f'<span class="value">{metrics.adopt_adapt_score}</span>'
        f'<div style="display: flex; gap: 8px; margin-top: 4px; font-size: 0.75rem; color: #64748b;">'
        f'<span>No: {metrics.custom_objects * metrics._aa_weight("custom_objects") + metrics.custom_fields * metrics._aa_weight("custom_fields") + metrics.einstein_predictions * metrics._aa_weight("einstein_predictions")}</span>'
        f'<span>Low: {metrics.flows * metrics._aa_weight("flows") + metrics.lwc_count * metrics._aa_weight("lwc") + metrics.flexipage_count * metrics._aa_weight("flexipages") + metrics.omni_scripts * metrics._aa_weight("omni_scripts") + metrics.omni_integration_procedures * metrics._aa_weight("omni_integration_procedures") + metrics.omni_ui_cards * metrics._aa_weight("omni_ui_cards") + metrics.omni_data_transforms * metrics._aa_weight("omni_data_transforms") + metrics.bre_decision_matrices * metrics._aa_weight("bre_decision_matrices") + metrics.bre_expression_sets * metrics._aa_weight("bre_expression_sets") + metrics.gen_ai_prompts * metrics._aa_weight("gen_ai_prompts")}</span>'
        f'<span>Pro: {metrics.apex_classes * metrics._aa_weight("apex_classes") + metrics.agents * metrics._aa_weight("agents")}</span>'
        f'</div></div>\n'
        if visibility.show_adopt_adapt_score
        else ""
    )
    custom_objects_card = (
        f'  <div class="card"><span>{_listing_link("objects", "Objets custom", metrics.custom_objects)} <small style="color: #64748b; font-weight: normal;">(No-code)</small></span>'
        f'<span class="value">{metrics.custom_objects}</span></div>\n'
        if visibility.show_custom_objects
        else ""
    )
    custom_fields_card = (
        f'  <div class="card"><span>{_listing_link("fields", "Champs custom", metrics.custom_fields)} <small style="color: #64748b; font-weight: normal;">(No-code)</small></span>'
        f'<span class="value">{metrics.custom_fields}</span></div>\n'
        if visibility.show_custom_fields
        else ""
    )
    flows_card = (
        f'  <div class="card"><span>{_listing_link("flows", "Flows", metrics.flows)} <small style="color: #64748b; font-weight: normal;">(Low-code)</small></span>'
        f'<span class="value">{metrics.flows}</span></div>\n'
        if visibility.show_flows
        else ""
    )
    apex_classes_triggers_card = (
        f'  <div class="card"><span>{_listing_link("apex", "Classes / Triggers", metrics.apex_classes + metrics.apex_triggers)} <small style="color: #64748b; font-weight: normal;">(Pro-code)</small></span>'
        f'<span class="value">{metrics.apex_classes + metrics.apex_triggers}</span></div>\n'
        if visibility.show_apex_classes_triggers
        else ""
    )
    omni_components_card = (
        f'  <div class="card"><span>{_listing_link("omni", "Composants Omni", omni_total)} <small style="color: #64748b; font-weight: normal;">(Low-code)</small></span>'
        f'<span class="value">{omni_total}</span></div>\n'
        if visibility.show_omni_components
        else ""
    )
    predictions_card = (
        f'  <div class="card"><span>Einstein Predictions <small style="color: #64748b; font-weight: normal;">(No-code)</small></span>'
        f'<span class="value">{metrics.einstein_predictions}</span></div>\n'
        if visibility.show_einstein_predictions
        else ""
    )
    agents_card = (
        f'  <div class="card"><span>{_listing_link("agents", "Agents", metrics.agents)} <small style="color: #64748b; font-weight: normal;">(Pro-code)</small></span>'
        f'<span class="value">{metrics.agents}</span></div>\n'
        if visibility.show_agents
        else ""
    )
    prompts_card = (
        f'  <div class="card"><span>{_listing_link("prompts", "Prompts", metrics.gen_ai_prompts)} <small style="color: #64748b; font-weight: normal;">(Low-code)</small></span>'
        f'<span class="value">{metrics.gen_ai_prompts}</span></div>\n'
        if visibility.show_gen_ai_prompts
        else ""
    )
    lwc_card = (
        f'  <div class="card"><span>{_listing_link("lwc", "Composants LWC", metrics.lwc_count)} <small style="color: #64748b; font-weight: normal;">(Pro-code)</small></span>'
        f'<span class="value">{metrics.lwc_count}</span></div>\n'
        if metrics.lwc_count > 0
        else ""
    )
    aura_card = (
        f'  <div class="card"><span>{_listing_link("aura", "Composants Aura", len(snapshot.aura))} <small style="color: #64748b; font-weight: normal;">(Pro-code)</small></span>'
        f'<span class="value">{len(snapshot.aura)}</span></div>\n'
        if len(snapshot.aura) > 0
        else ""
    )
    duplicate_rules_card = (
        f'  <div class="card"><span>{_listing_link("duplicate_rules", "Duplicate Rules", metrics.duplicate_rules)} <small style="color: #64748b; font-weight: normal;">(No-code)</small></span>'
        f'<span class="value">{metrics.duplicate_rules}</span></div>\n'
        if metrics.duplicate_rules > 0
        else ""
    )
    sharing_rules_card = (
        f'  <div class="card"><span>{_listing_link("sharing_rules", "Sharing Rules", metrics.sharing_rules)} <small style="color: #64748b; font-weight: normal;">(No-code)</small></span>'
        f'<span class="value">{metrics.sharing_rules}</span></div>\n'
        if visibility.show_sharing_rules
        else ""
    )

    # Build the 4 new tabs
    summary_tabs_sections = []
    
    # 1. Description
    desc_content = "".join([
        custom_objects_card, custom_fields_card, flows_card, 
        apex_classes_triggers_card, lwc_card, aura_card, omni_components_card, 
        predictions_card, agents_card, prompts_card, sharing_rules_card, duplicate_rules_card
    ])
    if desc_content.strip():
        summary_tabs_sections.append(("Description", f'<div class="cards">{desc_content}</div>'))

    # 2. Scoring
    scoring_content = "".join([
        customization_level_card, score_card, adopt_vs_adapt_card, adopt_adapt_score_card, test_coverage_card
    ])
    if scoring_content.strip():
        summary_tabs_sections.append(("Scoring", f'<div class="cards">{scoring_content}</div>'))
        
    # 3. Métriques
    metrics_content = "".join([
        findings_card, ai_usage_card, data_model_card, adoption_card, debt_card, innovation_card
    ])
    if metrics_content.strip():
        summary_tabs_sections.append(("Metriques", f'<div class="cards">{metrics_content}</div>'))
        
    # 4. IA
    ia_metier_content = "".join([predictions_card, agents_card, prompts_card])
    ia_admin_content = ai_usage_card
    
    ia_tab_content = ""
    if ia_metier_content.strip():
        ia_tab_content += f'<h3>IA pour le metier</h3><div class="cards">{ia_metier_content}</div>'
    if ia_admin_content.strip():
        ia_tab_content += f'<h3>IA pour les Admin et dev</h3><div class="cards">{ia_admin_content}</div>'
        
    if ia_tab_content:
        summary_tabs_sections.append(("IA", ia_tab_content))

    summary_tabs = tabbed_sections("summary-tabs", summary_tabs_sections) if summary_tabs_sections else ""

    title_suffix = f" : {html_value(alias)}" if alias else ""
    source_rel = href_relative(current_path, snapshot.source_dir)
    output_rel = href_relative(current_path, root_dir)
    body = f"""
<h1>Documentation Salesforce{title_suffix} ({date.today().isoformat()})</h1>
<p>Source analysee: <code>{html_value(source_rel)}</code></p>
<p>Dossier de sortie: <code>{html_value(output_rel)}</code></p>
{summary_tabs}
{tabs}
"""
    return render_page("Index", body, current_path, assets_dir, include_mermaid=False)


def _render_data_model_card(
    stats: DataModelCustomisationStats | None,
    page_path: Path | None,
    current_path: Path,
) -> str:
    """Render the *Empreinte data model* card on the index.

    Lays out custom vs standard objects+fields side by side with their
    percentages. The "custom" figure is hyperlinked to the dedicated
    page when available so a reader can drill down.
    """

    if stats is None or stats.total_objects + stats.total_fields == 0:
        return (
            '  <div class="card adopt-card"><span>Empreinte data model</span>'
            '<span class="value">N/A</span>'
            '<small class="adopt-hint">Mesure non disponible.</small></div>\n'
        )

    custom_count = stats.custom_objects + stats.custom_fields
    standard_count = stats.standard_objects + stats.standard_fields
    custom_pct = stats.percent_custom_global
    standard_pct = stats.percent_standard_global
    total = custom_count + standard_count

    if page_path is not None:
        href = html_value(href_relative(current_path, page_path))
        title_html = f'<a href="{href}">Empreinte data model</a>'
    else:
        title_html = 'Empreinte data model'

    return (
        '  <div class="card adopt-card">\n'
        f'    <span>{title_html}</span>\n'
        '    <div class="adopt-grid">\n'
        '      <div class="adopt-stat adopt-stat--adapt">\n'
        '        <span class="adopt-label">Custom</span>\n'
        f'        <span class="value">{custom_count}</span>\n'
        f'        <span class="adopt-percent">{custom_pct:.1f} %</span>\n'
        f'        <small class="adopt-hint">{stats.custom_objects} objets, {stats.custom_fields} champs</small>\n'
        '      </div>\n'
        '      <div class="adopt-stat adopt-stat--adopt">\n'
        '        <span class="adopt-label">Standard</span>\n'
        f'        <span class="value">{standard_count}</span>\n'
        f'        <span class="adopt-percent">{standard_pct:.1f} %</span>\n'
        f'        <small class="adopt-hint">{stats.standard_objects} objets, {stats.standard_fields} champs</small>\n'
        '      </div>\n'
        '    </div>\n'
        f'    <span class="adopt-hint">Objets+champs analyses : {total}</span>\n'
        '  </div>\n'
    )


def _render_adoption_card(
    stats: AdoptionStats | None,
    page_path: Path | None,
    current_path: Path,
) -> str:
    """Render the *Posture Adopt vs Adapt* card on the index.

    Adopt and Adapt counters are shown side by side with the weighted
    percentage; the "Adapt" total aggregates both Adapt-Low (declarative)
    and Adapt-High (code) so the summary stays compact, while the detail
    page is the place to look at the low/high split.
    """

    if stats is None or stats.total_count == 0:
        return (
            '  <div class="card adopt-card"><span>Posture Adopt vs Adapt</span>'
            '<span class="value">N/A</span>'
            '<small class="adopt-hint">Mesure non disponible.</small></div>\n'
        )

    adopt_count = stats.adopt_count
    adapt_total_count = stats.adapt_count
    adapt_low_count = stats.adapt_low_count
    adapt_high_count = stats.adapt_high_count
    
    adopt_pct = stats.percent_adoption
    adapt_total_pct = stats.percent_adaptation
    
    adopt_weight = stats.adopt_weight
    adapt_total_weight = stats.adapt_weight

    if page_path is not None:
        href = html_value(href_relative(current_path, page_path))
        title_html = f'<a href="{href}">Posture Adopt vs Adapt</a>'
    else:
        title_html = 'Posture Adopt vs Adapt'

    return (
        '  <div class="card adopt-card">\n'
        f'    <span>{title_html}</span>\n'
        '    <div class="adopt-grid">\n'
        '      <div class="adopt-stat adopt-stat--adopt">\n'
        '        <span class="adopt-label">Adopt</span>\n'
        f'        <span class="value">{adopt_count}</span>\n'
        f'        <span class="adopt-percent">{adopt_pct:.1f} %</span>\n'
        f'        <small class="adopt-hint">No-code (poids {adopt_weight})</small>\n'
        '      </div>\n'
        '      <div class="adopt-stat adopt-stat--adapt">\n'
        '        <span class="adopt-label">Adapt</span>\n'
        f'        <span class="value">{adapt_total_count}</span>\n'
        f'        <span class="adopt-percent">{adapt_total_pct:.1f} %</span>\n'
        f'        <small class="adopt-hint">Low: {adapt_low_count}, Pro: {adapt_high_count} (poids {adapt_total_weight})</small>\n'
        '      </div>\n'
        '    </div>\n'
        '    <span class="adopt-hint">'
        f'Capacites : {stats.total_count} / poids total {stats.total_weight}'
        '</span>\n'
        '  </div>\n'
    )


def _render_ai_usage_card(
    stats: AIUsageStats | None,
    page_path: Path | None,
    current_path: Path,
) -> str:
    """Render the "Usage IA" card on the index page.

    The card now exposes two figures side by side: how many customised
    elements (custom objects, custom fields, validation rules, record
    types, flows, Apex classes/triggers) carry one of the configured AI
    tags and how many do not, with the matching percentages. The "with
    tag" value links to ``ai_usage.html`` when available so reviewers can
    drill down into the detailed list.
    """

    if stats is None:
        return (
            '  <div class="card ai-usage-card"><span>Usage IA</span>'
            '<span class="value">N/A</span>'
            '<small class="ai-usage-hint">Mesure non disponible.</small></div>\n'
        )

    total = stats.total
    with_count = stats.with_tag_count
    without_count = stats.without_tag_count
    with_pct = stats.percent_with_tag
    without_pct = stats.percent_without_tag

    if page_path is not None:
        href = html_value(href_relative(current_path, page_path))
        title_html = f'<a href="{href}">Usage IA</a>'
    else:
        title_html = 'Usage IA'

    return (
        '  <div class="card ai-usage-card">\n'
        f'    <span>{title_html}</span>\n'
        '    <div class="ai-usage-grid">\n'
        '      <div class="ai-usage-stat ai-usage-stat--with">\n'
        '        <span class="ai-usage-label">Avec tag</span>\n'
        f'        <span class="value">{with_count}</span>\n'
        f'        <span class="ai-usage-percent">{with_pct:.1f} %</span>\n'
        '      </div>\n'
        '      <div class="ai-usage-stat ai-usage-stat--without">\n'
        '        <span class="ai-usage-label">Sans tag</span>\n'
        f'        <span class="value">{without_count}</span>\n'
        f'        <span class="ai-usage-percent">{without_pct:.1f} %</span>\n'
        '      </div>\n'
        '    </div>\n'
        f'    <span class="ai-usage-hint">Total customs : {total}</span>\n'
        '  </div>\n'
    )


def _render_debt_card(
    snapshot: MetadataSnapshot,
    page_path: Path | None,
    current_path: Path,
) -> str:
    """Render the "Dette technique & Entorse et PR" card on the index page."""
    
    debt_count = len(snapshot.technical_debt)
    deviation_count = len(snapshot.deviations)

    if page_path is not None:
        href = html_value(href_relative(current_path, page_path))
        title_html = f'<a href="{href}">Dette technique & Entorse et PR</a>'
        debt_link = f'<a href="{href}" style="color: inherit; text-decoration: none;">{debt_count}</a>'
        deviation_link = f'<a href="{href}" style="color: inherit; text-decoration: none;">{deviation_count}</a>'
    else:
        title_html = 'Dette technique & Entorse et PR'
        debt_link = str(debt_count)
        deviation_link = str(deviation_count)

    return (
        '  <div class="card adopt-card">\n'
        f'    <span>{title_html}</span>\n'
        '    <div class="adopt-grid">\n'
        '      <div class="adopt-stat adopt-stat--adapt">\n'
        '        <span class="adopt-label">Dette technique</span>\n'
        f'        <span class="value">{debt_link}</span>\n'
        '      </div>\n'
        '      <div class="adopt-stat adopt-stat--adapt" style="border-left: 1px solid #e2e8f0;">\n'
        '        <span class="adopt-label">Entorses et PR</span>\n'
        f'        <span class="value">{deviation_link}</span>\n'
        '      </div>\n'
        '    </div>\n'
        '  </div>\n'
    )


def _render_innovation_card(
    snapshot: MetadataSnapshot,
    page_path: Path | None,
    current_path: Path,
) -> str:
    """Render the "POC et Innovation" card on the index page."""
    
    total_count = len(snapshot.innovations)
    not_started_count = len([item for item in snapshot.innovations if item.not_started])
    started_count = total_count - not_started_count

    if page_path is not None:
        href = html_value(href_relative(current_path, page_path))
        title_html = f'<a href="{href}">POC et Innovation</a>'
        started_link = f'<a href="{href}" style="color: inherit; text-decoration: none;">{started_count}</a>'
        not_started_link = f'<a href="{href}" style="color: inherit; text-decoration: none;">{not_started_count}</a>'
        total_link = f'<a href="{href}" style="color: inherit; text-decoration: none;">{total_count}</a>'
    else:
        title_html = 'POC et Innovation'
        started_link = str(started_count)
        not_started_link = str(not_started_count)
        total_link = str(total_count)

    return (
        '  <div class="card adopt-card">\n'
        f'    <span>{title_html}</span>\n'
        '    <div class="adopt-grid">\n'
        '      <div class="adopt-stat adopt-stat--adapt">\n'
        '        <span class="adopt-label">En cours ou Terminés</span>\n'
        f'        <span class="value">{started_link}</span>\n'
        '      </div>\n'
        '      <div class="adopt-stat adopt-stat--adapt" style="border-left: 1px solid #e2e8f0;">\n'
        '        <span class="adopt-label">Non Commencé</span>\n'
        f'        <span class="value">{not_started_link}</span>\n'
        '      </div>\n'
        '      <div class="adopt-stat adopt-stat--adapt" style="border-left: 1px solid #e2e8f0;">\n'
        '        <span class="adopt-label">Total</span>\n'
        f'        <span class="value">{total_link}</span>\n'
        '      </div>\n'
        '    </div>\n'
        '  </div>\n'
    )


def write_index(
    snapshot: MetadataSnapshot,
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    flow_pages: dict[str, Path],
    apex_reviews: dict[str, ReviewResult],
    flow_reviews: dict[str, ReviewResult],
    pmd_results: dict[str, list[PmdViolation]],
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
    omni_pages: dict[str, list[dict[str, object]]] | None = None,
    agent_pages: dict[str, Path] | None = None,
    prompt_pages: dict[str, Path] | None = None,
    listing_pages: dict[str, Path] | None = None,
    security_pages: dict[str, Path] | None = None,
    *,
    analyzer_report=None,
    ai_usage_entries: list[AIUsageEntry] | None = None,
    ai_usage_page: Path | None = None,
    ai_usage_stats: AIUsageStats | None = None,
    data_model_stats: DataModelCustomisationStats | None = None,
    adoption_stats: AdoptionStats | None = None,
    customisation_page: Path | None = None,
    adoption_page: Path | None = None,
    debt_page: Path | None = None,
    innovation_page: Path | None = None,
    findings_report_page: Path | None = None,
    card_visibility: IndexCardVisibility | None = None,
    root_output_dir: Path | None = None,
    alias: str = "",
) -> Path:
    path = output_dir / "index.html"
    write_text(
        path,
        render_index(
            snapshot,
            object_pages,
            apex_pages,
            flow_pages,
            apex_reviews,
            flow_reviews,
            pmd_results,
            path,
            output_dir,
            assets_dir,
            omni_pages or {},
            agent_pages or {},
            prompt_pages or {},
            listing_pages or {},
            security_pages or {},
            analyzer_report,
            ai_usage_entries=ai_usage_entries,
            ai_usage_page=ai_usage_page,
            ai_usage_stats=ai_usage_stats,
            data_model_stats=data_model_stats,
            adoption_stats=adoption_stats,
            customisation_page=customisation_page,
            adoption_page=adoption_page,
            findings_report_page=findings_report_page,
            debt_page=debt_page,
            innovation_page=innovation_page,
            card_visibility=card_visibility,
            root_output_dir=root_output_dir,
            alias=alias,
        ),
    )
    log(f"Index genere: {path}")
    return path
