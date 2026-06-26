"""Renderer for Profile and Permission Set detail and list pages."""

from __future__ import annotations

import html as html_lib
from pathlib import Path
from typing import Callable

from src.analyzer.engine import AnalyzerReport
from src.core.models import MetadataSnapshot, SecurityArtifact
from src.core.utils import html_value, write_text
from src.reporting.html.page_shell import href_relative, index_back_link, render_page

LogCallback = Callable[[str], None]

# Permissions considered high-risk for badges
_HIGH_RISK_PERMS = {"ModifyAllData", "ManageUsers", "ResetPasswords", "ManageProfiles"}
_SENSITIVE_OBJECTS = {
    "Account", "Contact", "Opportunity", "Lead", "Order",
    "Case", "Contract", "User", "Event", "Task",
}

_SEVERITY_COLORS = {
    "Critical": "#ff4444",
    "Major": "#ff8c00",
    "Minor": "#ccbb00",
    "Info": "#0088ff",
}


def _badge(text: str, color: str) -> str:
    return (
        f"<span style='background:{color};color:#fff;padding:1px 7px;"
        f"border-radius:3px;font-size:0.8em;font-weight:bold'>{text}</span>"
    )


def _risk_badge(artifact: SecurityArtifact) -> str:
    """Return a coloured risk badge based on the artifact's permissions."""
    has_mad = any(up.enabled and up.name == "ModifyAllData" for up in artifact.user_permissions)
    has_mu = any(up.enabled and up.name == "ManageUsers" for up in artifact.user_permissions)
    has_mar = any(op.modify_all_records for op in artifact.object_permissions)
    if has_mad:
        return _badge("CRITIQUE", "#ff4444")
    if has_mu or (has_mar and artifact.kind == "profile"):
        return _badge("RISQUE", "#ff8c00")
    if has_mar:
        return _badge("ATTENTION", "#ccbb00")
    return _badge("OK", "#22aa66")


def _bool_cell(value: bool) -> str:
    if value:
        return "<td style='color:#ff4444;text-align:center'>✓</td>"
    return "<td style='color:#aaa;text-align:center'>—</td>"


# ---------------------------------------------------------------------------
# Detail page (individual profile or permission set)
# ---------------------------------------------------------------------------


def render_security_detail_page(
    artifact: SecurityArtifact,
    current_path: Path,
    assets_dir: Path,
    findings: list,
    back_href: str,
) -> str:
    """Render a 4-tab detail HTML page for a profile or permission set."""

    kind_label = "Profil" if artifact.kind == "profile" else "Permission Set"
    custom_label = "Custom" if artifact.is_custom else "Standard"
    badge = _risk_badge(artifact)

    # ── Tab 1 : Object Permissions ──────────────────────────────────────────
    obj_rows = "".join(
        f"<tr><td>{html_value(op.object_name)}</td>"
        + _bool_cell(op.allow_read)
        + _bool_cell(op.allow_create)
        + _bool_cell(op.allow_edit)
        + _bool_cell(op.allow_delete)
        + _bool_cell(op.view_all_records)
        + (
            f"<td style='color:#ff4444;font-weight:bold;text-align:center'>✓ ModAll</td>"
            if op.modify_all_records
            else "<td style='color:#aaa;text-align:center'>—</td>"
        )
        + "</tr>"
        for op in sorted(artifact.object_permissions, key=lambda x: x.object_name)
    ) or "<tr><td colspan='7' class='empty'>Aucun droit objet.</td></tr>"
    obj_tab = (
        "<table><thead><tr>"
        "<th>Objet</th><th>Lire</th><th>Créer</th><th>Modifier</th>"
        "<th>Suppr.</th><th>ViewAll</th><th>ModAll</th>"
        "</tr></thead><tbody>" + obj_rows + "</tbody></table>"
    )

    # ── Tab 2 : Field Permissions ───────────────────────────────────────────
    field_rows = "".join(
        f"<tr><td>{html_value(fp.field_name)}</td>"
        + _bool_cell(fp.readable)
        + _bool_cell(fp.editable)
        + "</tr>"
        for fp in sorted(artifact.field_permissions, key=lambda x: x.field_name)
    ) or "<tr><td colspan='3' class='empty'>Aucun droit champ.</td></tr>"
    field_tab = (
        "<table><thead><tr><th>Champ</th><th>Lecture</th><th>Écriture</th></tr></thead>"
        "<tbody>" + field_rows + "</tbody></table>"
    )

    # ── Tab 3 : User Permissions ────────────────────────────────────────────
    enabled_up = [up for up in artifact.user_permissions if up.enabled]
    up_rows = "".join(
        "<tr><td>"
        + html_value(up.name)
        + ("&nbsp;" + _badge("⚠ Risque élevé", "#ff4444") if up.name in _HIGH_RISK_PERMS else "")
        + "</td></tr>"
        for up in sorted(enabled_up, key=lambda x: x.name)
    ) or "<tr><td class='empty'>Aucune user permission activée.</td></tr>"
    up_tab = (
        f"<p><strong>{len(enabled_up)}</strong> permission(s) système activée(s).</p>"
        "<table><thead><tr><th>Permission</th></tr></thead>"
        "<tbody>" + up_rows + "</tbody></table>"
    )

    # ── Tab 4 : Other Access ────────────────────────────────────────────────
    def _access_section(title: str, items: list, attr: str) -> str:
        enabled = [item for item in items if getattr(item, attr)]
        if not enabled:
            return f"<h4>{title}</h4><p class='empty'>Aucun accès activé.</p>"
        rows = "".join(
            f"<tr><td>{html_value(item.name)}</td></tr>"
            for item in sorted(enabled, key=lambda e: e.name)
        )
        return (
            f"<h4>{title} ({len(enabled)})</h4>"
            "<table><thead><tr><th>Nom</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )

    other_tab = (
        _access_section("Classes Apex", artifact.class_accesses, "enabled")
        + _access_section("Flows", artifact.flow_accesses, "enabled")
        + _access_section("Pages Visualforce", artifact.page_accesses, "enabled")
        + _access_section("Custom Permissions", artifact.custom_permissions, "enabled")
    )

    # ── Findings banner ─────────────────────────────────────────────────────
    findings_html = ""
    if findings:
        banners = []
        for f in findings:
            color = _SEVERITY_COLORS.get(f.rule.severity, "#888")
            banners.append(
                f"<div style='padding:6px 12px;border-left:4px solid {color};"
                f"background:{color}22;margin:4px 0;border-radius:2px'>"
                f"<strong>[{f.rule.severity}]</strong> {html_lib.escape(f.rule.title)}"
                f" — {html_lib.escape(f.message)}</div>"
            )
        findings_html = (
            "<div style='margin-bottom:12px'>"
            f"<h3 style='color:#ff4444'>⚠ {len(findings)} finding(s) détecté(s)</h3>"
            + "".join(banners)
            + "</div>"
        )

    # ── Tab assembly ────────────────────────────────────────────────────────
    tabs_html = _render_tabs([
        (f"Objets ({len(artifact.object_permissions)})", obj_tab),
        (f"Champs ({len(artifact.field_permissions)})", field_tab),
        (f"User Permissions ({len(enabled_up)})", up_tab),
        ("Autres accès", other_tab),
    ])

    body = f"""
<p><a href="{html_lib.escape(back_href)}">&larr; Retour à la liste</a></p>
<h2>{html_lib.escape(kind_label)} : {html_lib.escape(artifact.name)}</h2>
<p>
  {badge}&nbsp;
  <span style='color:#666'>{custom_label}</span>
  {('&nbsp;&mdash;&nbsp;' + html_lib.escape(artifact.label)) if artifact.label else ''}
</p>
{findings_html}
{tabs_html}
"""
    return render_page(artifact.name, body, current_path, assets_dir)


def _render_tabs(tabs: list[tuple[str, str]]) -> str:
    tab_ids = [f"sec-tab-{i}" for i in range(len(tabs))]
    btns = "".join(
        f"<button class='tab-btn' onclick=\"showTab('{tid}')\" id='btn-{tid}'>"
        f"{html_lib.escape(label)}</button>"
        for (label, _), tid in zip(tabs, tab_ids)
    )
    panels = "".join(
        f"<div id='{tid}' class='tab-panel' style='display:none'>{content}</div>"
        for (_, content), tid in zip(tabs, tab_ids)
    )
    first = tab_ids[0] if tab_ids else ""
    return f"""
<div class='tabs'>
  <div class='tab-buttons'>{btns}</div>
  {panels}
</div>
<script>
function showTab(id) {{
  document.querySelectorAll('.tab-panel').forEach(p => p.style.display='none');
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(id).style.display='';
  document.getElementById('btn-' + id).classList.add('active');
}}
showTab('{first}');
</script>
"""


# ---------------------------------------------------------------------------
# List pages
# ---------------------------------------------------------------------------


def _render_security_list_page(
    artifacts: list[SecurityArtifact],
    kind_label: str,
    title: str,
    detail_pages: dict[str, Path],
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    analyzer_report: AnalyzerReport | None,
) -> str:
    rows = []
    for a in sorted(artifacts, key=lambda x: x.name):
        findings = []
        if analyzer_report and a.name in analyzer_report.security:
            findings = analyzer_report.security[a.name]
        severity_badge = ""
        if any(f.rule.severity == "Critical" for f in findings):
            severity_badge = _badge("CRITIQUE", "#ff4444")
        elif any(f.rule.severity == "Major" for f in findings):
            severity_badge = _badge("MAJEUR", "#ff8c00")
        elif findings:
            severity_badge = _badge("FINDINGS", "#ccbb00")

        name_cell = html_value(a.name)
        if a.name in detail_pages:
            rel = href_relative(current_path, detail_pages[a.name])
            name_cell = f"<a href='{html_lib.escape(rel)}'>{html_value(a.name)}</a>"

        rows.append(
            f"<tr>"
            f"<td>{name_cell}</td>"
            f"<td>{'Custom' if a.is_custom else 'Standard'}</td>"
            f"<td>{_risk_badge(a)}</td>"
            f"<td style='text-align:center'>{severity_badge}</td>"
            f"<td style='text-align:center'>{len(a.object_permissions)}</td>"
            f"<td style='text-align:center'>{len(a.field_permissions)}</td>"
            f"<td style='text-align:center'>{len([up for up in a.user_permissions if up.enabled])}</td>"
            f"</tr>"
        )

    table = (
        "<table><thead><tr>"
        f"<th>{kind_label}</th><th>Type</th><th>Risque</th><th>Findings</th>"
        "<th>Droits Objets</th><th>Droits Champs</th><th>User Perms</th>"
        "</tr></thead><tbody>"
        + ("".join(rows) or f"<tr><td colspan='7' class='empty'>Aucun {kind_label.lower()}.</td></tr>")
        + "</tbody></table>"
    )

    body = (
        index_back_link(current_path, output_dir)
        + f"<h2>{html_lib.escape(title)} ({len(artifacts)})</h2>"
        + table
    )
    return render_page(title, body, current_path, assets_dir)


# ---------------------------------------------------------------------------
# Write functions
# ---------------------------------------------------------------------------


def write_security_pages(
    snapshot: MetadataSnapshot,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
    analyzer_report: AnalyzerReport | None = None,
) -> dict[str, Path]:
    """Generate list + detail pages for profiles and permission sets.

    Returns a dict with keys:
      'profiles_list', 'permsets_list',
      and per-artifact keys 'profile:<name>' / 'permset:<name>'.
    """
    pages: dict[str, Path] = {}
    security_dir = output_dir / "security"
    security_dir.mkdir(parents=True, exist_ok=True)

    profiles_dir = security_dir / "profiles"
    profiles_dir.mkdir(exist_ok=True)
    permsets_dir = security_dir / "permsets"
    permsets_dir.mkdir(exist_ok=True)

    # Detail pages — profiles
    profile_detail_pages: dict[str, Path] = {}
    for artifact in snapshot.profiles:
        path = profiles_dir / f"{artifact.name}.html"
        findings = (analyzer_report.security.get(artifact.name, []) if analyzer_report else [])
        back = href_relative(path, output_dir / "security" / "profiles_list.html")
        content = render_security_detail_page(artifact, path, assets_dir, findings, back)
        write_text(path, content)
        profile_detail_pages[artifact.name] = path
        pages[f"profile:{artifact.name}"] = path

    # Detail pages — permission sets
    permset_detail_pages: dict[str, Path] = {}
    for artifact in snapshot.permission_sets:
        path = permsets_dir / f"{artifact.name}.html"
        findings = (analyzer_report.security.get(artifact.name, []) if analyzer_report else [])
        back = href_relative(path, output_dir / "security" / "permsets_list.html")
        content = render_security_detail_page(artifact, path, assets_dir, findings, back)
        write_text(path, content)
        permset_detail_pages[artifact.name] = path
        pages[f"permset:{artifact.name}"] = path

    # List page — profiles
    profiles_list_path = security_dir / "profiles_list.html"
    write_text(
        profiles_list_path,
        _render_security_list_page(
            snapshot.profiles,
            "Profil",
            "Liste des Profils",
            profile_detail_pages,
            profiles_list_path,
            output_dir,
            assets_dir,
            analyzer_report,
        ),
    )
    pages["profiles_list"] = profiles_list_path
    log(f"Pages profils generees : {len(snapshot.profiles)} profil(s).")

    # List page — permission sets
    permsets_list_path = security_dir / "permsets_list.html"
    write_text(
        permsets_list_path,
        _render_security_list_page(
            snapshot.permission_sets,
            "Permission Set",
            "Liste des Permission Sets",
            permset_detail_pages,
            permsets_list_path,
            output_dir,
            assets_dir,
            analyzer_report,
        ),
    )
    pages["permsets_list"] = permsets_list_path
    log(f"Pages permission sets generees : {len(snapshot.permission_sets)} PS.")

    return pages
