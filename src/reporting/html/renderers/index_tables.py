"""Tables principales de la page index HTML."""

from __future__ import annotations

import re
from pathlib import Path

from src.core.models import MetadataSnapshot
from src.core.utils import html_value
from src.reporting.html.page_shell import href_relative, tabbed_sections


def render_object_rows(
    snapshot: MetadataSnapshot,
    object_pages: dict[str, Path],
    current_path: Path,
) -> str:
    trigger_re = re.compile(r"(?is)\btrigger\s+\w+\s+on\s+([A-Za-z0-9_]+)")
    trigger_counts: dict[str, int] = {}
    for artifact in snapshot.apex_artifacts:
        if (artifact.kind or "").lower() == "trigger":
            match = trigger_re.search(artifact.body or "")
            if match:
                obj_name = match.group(1)
                trigger_counts[obj_name] = trigger_counts.get(obj_name, 0) + 1

    active_flow_counts: dict[str, int] = {}
    inactive_flow_counts: dict[str, int] = {}
    for flow in snapshot.flows:
        if flow.start_object:
            if (flow.status or "").strip().lower() == "active":
                active_flow_counts[flow.start_object] = (
                    active_flow_counts.get(flow.start_object, 0) + 1
                )
            else:
                inactive_flow_counts[flow.start_object] = (
                    inactive_flow_counts.get(flow.start_object, 0) + 1
                )

    def flag_cell(count: int) -> str:
        if count > 0:
            return f"<td style='text-align:center;color:#16a34a;font-weight:600'>&#10003; {count}</td>"
        return "<td style='text-align:center;color:#cbd5e1'>&mdash;</td>"

    def flow_flags_cell(active_count: int, inactive_count: int) -> str:
        if active_count == 0 and inactive_count == 0:
            return "<td style='text-align:center;color:#cbd5e1'>&mdash;</td>"
        parts = []
        if active_count > 0:
            parts.append(
                f"<span style='color:#16a34a;font-weight:600'>Actifs: {active_count}</span>"
            )
        if inactive_count > 0:
            parts.append(
                f"<span style='color:#dc2626;font-weight:600'>Inactifs: {inactive_count}</span>"
            )
        return "<td style='text-align:center'>" + "<br/>".join(parts) + "</td>"

    return "".join(
        f"<tr><td><a href='{href_relative(current_path, object_pages[item.api_name])}'>{html_value(item.api_name)}</a></td>"
        f"<td>{html_value(item.label)}</td><td>{len(item.fields)}</td><td>{len(item.relationships)}</td>"
        f"<td>{len(item.validation_rules)} (Σ={sum(vr.complexity_score for vr in item.validation_rules)})</td>"
        f"{flag_cell(trigger_counts.get(item.api_name, 0))}"
        f"{flow_flags_cell(active_flow_counts.get(item.api_name, 0), inactive_flow_counts.get(item.api_name, 0))}</tr>"
        for item in snapshot.objects
        if item.api_name in object_pages
    ) or "<tr><td colspan='7' class='empty'>Aucun objet analyse.</td></tr>"


def render_security_dashboard_tab(
    snapshot: MetadataSnapshot,
    current_path: Path,
    security_pages: dict[str, Path] | None,
    analyzer_report,
) -> str:
    risk_style = {
        "danger": "background:rgba(255,68,68,.08);color:#c00",
        "major": "background:rgba(255,140,0,.08);color:#a04000",
        "minor": "background:rgba(240,220,0,.08);color:#665500",
        "ok": "",
    }
    risk_label = {
        "danger": "⚠ CRITIQUE",
        "major": "⚠ RISQUE",
        "minor": "⚠ ATTENTION",
        "ok": "",
    }

    def profile_risk(item):
        if any(up.enabled and up.name == "ModifyAllData" for up in item.user_permissions):
            return "danger"
        if any(up.enabled and up.name == "ManageUsers" for up in item.user_permissions):
            return "major"
        if any(op.modify_all_records for op in item.object_permissions):
            return "minor"
        return "ok"

    def sec_findings_badge(name: str) -> str:
        if analyzer_report is None or name not in analyzer_report.security:
            return ""
        findings = analyzer_report.security[name]
        if any(f.rule.severity == "Critical" for f in findings):
            return " <span style='color:#ff4444;font-weight:bold'>● CRITIQUE</span>"
        if any(f.rule.severity == "Major" for f in findings):
            return " <span style='color:#ff8c00;font-weight:bold'>● MAJEUR</span>"
        if findings:
            return " <span style='color:#ccbb00;font-weight:bold'>●</span>"
        return ""

    def profile_name_cell(item, pages: dict[str, Path]) -> str:
        name = html_value(item.name)
        if item.name in pages:
            name = f"<a href='{href_relative(current_path, pages[item.name])}'>{name}</a>"
        return f"<td>{name}{sec_findings_badge(item.name)}</td>"

    def security_artifact_row(item, pages: dict[str, Path], is_profile: bool = True) -> str:
        risk = profile_risk(item)
        risk_color = "#ff4444" if risk in ("danger", "major", "minor") else ""
        kind_label = ("Custom" if item.is_custom else "Standard") if is_profile else "Permission Set"
        return (
            f"<tr style='{risk_style[risk]}'>"
            + profile_name_cell(item, pages)
            + f"<td>{kind_label}</td>"
            + f"<td style='color:{risk_color}'>{risk_label[risk]}</td>"
            + f"<td>{len(item.object_permissions)}</td>"
            + f"<td>{len(item.field_permissions)}</td></tr>"
        )

    profile_pages = {
        k.split(":", 1)[1]: v
        for k, v in (security_pages or {}).items()
        if k.startswith("profile:")
    }
    permset_pages = {
        k.split(":", 1)[1]: v
        for k, v in (security_pages or {}).items()
        if k.startswith("permset:")
    }
    profile_rows = "".join(
        security_artifact_row(item, profile_pages, is_profile=True)
        for item in snapshot.profiles
    ) or "<tr><td colspan='5' class='empty'>Aucun profil analysé.</td></tr>"
    permset_rows = "".join(
        security_artifact_row(item, permset_pages, is_profile=False)
        for item in snapshot.permission_sets
    ) or "<tr><td colspan='5' class='empty'>Aucun permission set analysé.</td></tr>"

    metrics = snapshot.metrics
    ratio_colors = {"Bon": "#22aa66", "Attention": "#ccbb00", "Risque": "#ff8c00", "Critique": "#ff4444"}
    ratio_color = ratio_colors.get(metrics.profiles_ps_ratio_level, "#888")
    profiles_href = href_relative(current_path, security_pages["profiles_list"]) if security_pages and "profiles_list" in security_pages else ""
    permsets_href = href_relative(current_path, security_pages["permsets_list"]) if security_pages and "permsets_list" in security_pages else ""
    profiles_title = f"<a href='{profiles_href}'>Profiles</a>" if profiles_href else "Profiles"
    permsets_title = f"<a href='{permsets_href}'>Permission Sets</a>" if permsets_href else "Permission Sets"

    summary = f"""
<div class='section'>
    <div style='display:flex;gap:16px;flex-wrap:wrap;margin-bottom:14px'>
      <div style='flex:1;min-width:200px;padding:10px 14px;border:1px solid #e2e8f0;border-radius:6px'>
        <div style='font-size:.8em;color:#64748b'>Profils custom</div>
        <div style='font-size:1.5em;font-weight:bold'>{metrics.custom_profiles_count}</div>
        <div style='font-size:.8em;color:#64748b'>sur {metrics.profiles_count} profils total</div>
      </div>
      <div style='flex:1;min-width:200px;padding:10px 14px;border:1px solid #e2e8f0;border-radius:6px'>
        <div style='font-size:.8em;color:#64748b'>Permission Sets</div>
        <div style='font-size:1.5em;font-weight:bold'>{metrics.permission_sets_count}</div>
      </div>
      <div style='flex:1;min-width:200px;padding:10px 14px;border:1px solid {ratio_color}33;border-radius:6px'>
        <div style='font-size:.8em;color:#64748b'>Ratio Profils/PS</div>
        <div style='font-size:1.5em;font-weight:bold;color:{ratio_color}'>{metrics.profiles_ps_ratio_score}%</div>
        <div style='font-size:.8em;color:{ratio_color};font-weight:bold'>{metrics.profiles_ps_ratio_level}</div>
      </div>
      <div style='flex:1;min-width:200px;padding:10px 14px;border:1px solid {"#ff444433" if metrics.dangerous_profiles_count else "#e2e8f0"};border-radius:6px'>
        <div style='font-size:.8em;color:#64748b'>Profils dangereux</div>
        <div style='font-size:1.5em;font-weight:bold;color:{"#ff4444" if metrics.dangerous_profiles_count else "#22aa66"}'>{metrics.dangerous_profiles_count}</div>
        <div style='font-size:.8em;color:#64748b'>ModifyAllData / ManageUsers</div>
      </div>
      <div style='flex:1;min-width:200px;padding:10px 14px;border:1px solid {"#ff8c0033" if metrics.profiles_with_modify_all else "#e2e8f0"};border-radius:6px'>
        <div style='font-size:.8em;color:#64748b'>Profils avec ModifyAllRecords</div>
        <div style='font-size:1.5em;font-weight:bold;color:{"#ff8c00" if metrics.profiles_with_modify_all else "#22aa66"}'>{metrics.profiles_with_modify_all}</div>
      </div>
      <div style='flex:1;min-width:200px;padding:10px 14px;border:1px solid {"#ccbb0033" if metrics.perm_sets_with_modify_all else "#e2e8f0"};border-radius:6px'>
        <div style='font-size:.8em;color:#64748b'>PS avec ModifyAll (objets sensibles)</div>
        <div style='font-size:1.5em;font-weight:bold;color:{"#ccbb00" if metrics.perm_sets_with_modify_all else "#22aa66"}'>{metrics.perm_sets_with_modify_all}</div>
      </div>
    </div>
    <table><thead><tr><th>Profil / Permission Set</th><th>Type</th><th>Risque</th><th>Droits objet</th><th>Droits champ</th></tr></thead><tbody>{profile_rows}{permset_rows}</tbody></table>
</div>"""

    return tabbed_sections("index-security", [
        ("Synthese", summary),
        ("Profiles", f"<h4>{profiles_title} ({len(snapshot.profiles)})</h4><table><thead><tr><th>Profil</th><th>Type</th><th>Risque</th><th>Droits objet</th><th>Droits champ</th></tr></thead><tbody>{profile_rows}</tbody></table>"),
        ("Permission Sets", f"<h4>{permsets_title} ({len(snapshot.permission_sets)})</h4><table><thead><tr><th>Permission Set</th><th>Type</th><th>Risque</th><th>Droits objet</th><th>Droits champ</th></tr></thead><tbody>{permset_rows}</tbody></table>"),
        ("CRUD", f"<p><a href='{href_relative(current_path, security_pages.get('security_matrix')) if security_pages else '#'}' target='_blank' rel='noopener'>Ouvrir la matrice de securite (CRUD) dans un nouvel onglet</a></p>"),
        ("PS Group", f"<p><a href='{href_relative(current_path, security_pages.get('psg_list')) if security_pages else '#'}' target='_blank' rel='noopener'>Ouvrir les Permission Set Groups dans un nouvel onglet</a></p>"),
    ])


def render_apex_rows(
    snapshot: MetadataSnapshot,
    apex_pages: dict[str, Path],
    current_path: Path,
) -> str:
    return "".join(
        f"<tr><td><a href='{href_relative(current_path, apex_pages[item.name])}'>{html_value(item.name)}</a></td>"
        f"<td>{html_value(item.kind)}</td><td>{item.line_count}</td><td>{item.method_count}</td>"
        f"<td>{(f'{item.test_coverage:.1f}% ({item.test_coverage_lines_covered}/{item.test_coverage_lines_covered + item.test_coverage_lines_uncovered} lignes)') if item.test_coverage is not None else 'N/A'}</td></tr>"
        for item in snapshot.apex_artifacts
        if item.name in apex_pages
    ) or "<tr><td colspan='5' class='empty'>Aucun artefact Apex analyse.</td></tr>"


def render_flow_panel(
    snapshot: MetadataSnapshot,
    flow_pages: dict[str, Path],
    current_path: Path,
) -> str:
    def flow_status_cell(status: str) -> str:
        normalized = (status or "").strip().lower()
        if normalized == "active":
            return "<td style='color:#16a34a;font-weight:600'>Actif</td>"
        if normalized:
            return f"<td style='color:#dc2626;font-weight:600'>Inactif ({html_value(status)})</td>"
        return "<td style='color:#94a3b8'>Inconnu</td>"

    def elements_coverage_cell(item) -> str:
        elements = item.elements or []
        total = len(elements)
        if item.test_coverage is None or total == 0:
            return "<td>N/A</td>"
        covered = sum(1 for e in elements if e.covered_by)
        pct = (covered / total * 100) if total > 0 else 0.0
        return f"<td>{pct:.1f}% ({covered}/{total})</td>"

    flow_rows = "".join(
        f"<tr><td><a href='{href_relative(current_path, flow_pages[item.name])}'>{html_value(item.name)}</a></td>"
        f"<td>{html_value(item.process_type)}</td>{flow_status_cell(item.status)}"
        f"<td>{html_value(item.complexity_level)}</td><td>{item.complexity_score}</td><td>{item.total_elements}</td>"
        f"<td>{'⚠' if item.soql_in_loop or item.dml_in_loop else 'OK'}</td>"
        f"<td>{(f'{item.test_coverage:.1f}% ({item.test_coverage_elements_covered}/{item.test_coverage_elements_covered + item.test_coverage_elements_uncovered} blocs API)') if item.test_coverage is not None else 'N/A'}</td>"
        f"{elements_coverage_cell(item)}</tr>"
        for item in snapshot.flows
        if item.name in flow_pages
    ) or "<tr><td colspan='9' class='empty'>Aucun flow analyse.</td></tr>"
    redundant_flow_rows = "".join(
        f"<tr><td>{html_value(group.object_name)}</td><td>{html_value(group.trigger_type)}</td><td>{', '.join(group.flows)}</td></tr>"
        for group in snapshot.redundant_flows
    ) or "<tr><td colspan='3' class='empty'>Aucune redondance de Flow detectee.</td></tr>"

    coverage_header_tooltip = (
        "% de blocs testes calcule par l'API Tooling Salesforce (FlowTestCoverage). "
        "Un 'bloc' est plus granulaire qu'un element du flow : chaque branche de decision, "
        "chaque sortie de boucle ou chemin de fault est compte separement. "
        "C'est pourquoi le nombre de blocs est generalement superieur au nombre d'elements nommes du flow."
    )
    elements_coverage_header_tooltip = (
        "% d'elements du flow (au sens de l'onglet Elements de la page du flow) testes par au moins "
        "une classe Apex, c'est-a-dire marques 'Oui' dans la colonne Teste par. "
        "Calcul : nombre d'elements 'Oui' / nombre total d'elements du flow."
    )
    flow_list_table = f"<table><thead><tr><th>Nom</th><th>Type</th><th>Statut</th><th>Complexite</th><th>Score</th><th>Elements</th><th>DML/SOQL Boucle</th><th title=\"{coverage_header_tooltip}\">% Couverture</th><th title=\"{elements_coverage_header_tooltip}\">% elements couverts</th></tr></thead><tbody>{flow_rows}</tbody></table>"
    flow_redundancy_table = f"<table><thead><tr><th>Objet</th><th>Evenement</th><th>Flows</th></tr></thead><tbody>{redundant_flow_rows}</tbody></table>"
    return tabbed_sections("index-flows", [
        ("Liste", flow_list_table),
        ("Redondance", flow_redundancy_table),
    ])


def render_sharing_rule_rows(snapshot: MetadataSnapshot) -> str:
    type_labels = {
        "criteria": "Critères",
        "owner": "Propriétaire",
        "guest": "Utilisateur invité",
        "territory": "Territoire",
    }
    return "".join(
        f"<tr><td>{html_value(rule.object_name)}</td><td>{html_value(rule.full_name)}</td>"
        f"<td>{html_value(type_labels.get(rule.rule_type, rule.rule_type))}</td>"
        f"<td>{html_value(rule.label)}</td><td>{html_value(rule.description)}</td></tr>"
        for rule in snapshot.sharing_rules
    ) or "<tr><td colspan='5' class='empty'>Aucune sharing rule analysée.</td></tr>"


def render_agent_rows(
    snapshot: MetadataSnapshot,
    agent_pages: dict[str, Path],
    current_path: Path,
) -> str:
    return "".join(
        f"<tr><td><a href='{href_relative(current_path, agent_pages[item.name])}'>{html_value(item.name)}</a></td>"
        f"<td>{html_value(item.label)}</td><td>{html_value(item.description)}</td></tr>"
        for item in snapshot.agents
        if item.name in agent_pages
    ) or "<tr><td colspan='3' class='empty'>Aucun agent analyse.</td></tr>"


def render_prompt_rows(
    snapshot: MetadataSnapshot,
    prompt_pages: dict[str, Path],
    current_path: Path,
) -> str:
    return "".join(
        f"<tr><td><a href='{href_relative(current_path, prompt_pages[item.name])}'>{html_value(item.name)}</a></td>"
        f"<td>{html_value(item.label)}</td><td>{html_value(item.description)}</td></tr>"
        for item in snapshot.gen_ai_prompts
        if item.name in prompt_pages
    ) or "<tr><td colspan='3' class='empty'>Aucun prompt analyse.</td></tr>"


def render_health_panel(
    snapshot: MetadataSnapshot,
    current_path: Path,
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    flow_pages: dict[str, Path],
    agent_pages: dict[str, Path],
    prompt_pages: dict[str, Path],
) -> str:
    if not snapshot.orphans:
        return "<p class='empty'>Aucun composant orphelin detecte.</p>"

    orphans_by_kind: dict[str, list[str]] = {}
    for orphan in snapshot.orphans:
        kind = orphan.kind or "Autre"
        href = ""
        if kind == "Objet":
            page = object_pages.get(orphan.name)
            href = href_relative(current_path, page) if page else ""
        elif kind == "Apex":
            page = apex_pages.get(orphan.name)
            href = href_relative(current_path, page) if page else ""
        elif kind == "Flow":
            page = flow_pages.get(orphan.name)
            href = href_relative(current_path, page) if page else ""
        elif kind == "Agent":
            page = agent_pages.get(orphan.name)
            href = href_relative(current_path, page) if page else ""
        elif kind == "Prompt":
            page = prompt_pages.get(orphan.name)
            href = href_relative(current_path, page) if page else ""
        name_cell = (
            f"<a href='{html_value(href)}'>{html_value(orphan.name)}</a>"
            if href
            else html_value(orphan.name)
        )
        orphans_by_kind.setdefault(kind, []).append(f"<tr><td>{name_cell}</td></tr>")

    sections: list[tuple[str, str]] = []
    for kind in sorted(orphans_by_kind.keys()):
        rows = orphans_by_kind[kind]
        table = f"<table><thead><tr><th>Nom</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
        sections.append((f"{kind} ({len(rows)})", table))
    return tabbed_sections("index-orphans", sections)
