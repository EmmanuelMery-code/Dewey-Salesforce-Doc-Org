"""Metadata comparison renderer between two history entries.

Beyond the raw file-level diff (added / modified / deleted), this renderer
also performs a *regression analysis*: it compares the key quality metrics of
the two generations (test coverage, findings, test ratio) and flags every
degradation, so the reader can immediately tell whether the newer generation
improved or regressed compared to the older one.
"""

from __future__ import annotations

from pathlib import Path

from src.core.history_service import HistoryEntry
from src.core.utils import html_value
from src.reporting.html.page_shell import href_relative, index_back_link, render_page


# ── Verdict styling ──────────────────────────────────────────────────────────
_VERDICT_STYLE = {
    "improvement": ("Amélioration", "#dafbe1", "#1a7f37"),
    "regression": ("Régression", "#ffebe9", "#d1242f"),
    "stable": ("Stable", "#eaeef2", "#57606a"),
    "neutral": ("—", "#eaeef2", "#57606a"),
}

# Severity rank used to sort regressions (highest first) and colour badges.
_SEVERITY_RANK = {"Critique": 3, "Majeur": 2, "Mineur": 1, "": 0}
_SEVERITY_COLOR = {
    "Critique": "#d1242f",
    "Majeur": "#bc4c00",
    "Mineur": "#9a6700",
    "": "#57606a",
}


def _classify(old_v, new_v, direction):
    """Return (delta, status) for a metric given its 'good' direction."""
    if old_v is None or new_v is None:
        return None, "neutral"
    delta = new_v - old_v
    if direction == "up_good":
        status = "improvement" if delta > 0 else ("regression" if delta < 0 else "stable")
    elif direction == "down_good":
        status = "improvement" if delta < 0 else ("regression" if delta > 0 else "stable")
    else:
        status = "neutral"
    return delta, status


def _fmt(v, is_pct: bool) -> str:
    if v is None:
        return "N/A"
    return f"{v:.1f}%" if is_pct else f"{int(v)}"


def _delta_cell(delta, status: str, is_pct: bool) -> str:
    if delta is None:
        return "<td style='text-align:center;'>N/A</td>"
    color = _VERDICT_STYLE[status][2] if status != "neutral" else "#57606a"
    arrow = "\u25b2" if delta > 0 else ("\u25bc" if delta < 0 else "=")
    sign = f"{delta:+.1f}%" if is_pct else f"{delta:+d}"
    return f"<td style='text-align:center; color:{color}; font-weight:600;'>{arrow} {sign}</td>"


def _verdict_badge(status: str) -> str:
    label, bg, fg = _VERDICT_STYLE[status]
    return (
        f"<span style='display:inline-block; padding:2px 8px; border-radius:10px; "
        f"font-size:12px; font-weight:600; background:{bg}; color:{fg};'>{label}</span>"
    )


def _quality_specs(old: HistoryEntry, new: HistoryEntry):
    """Metrics whose degradation is a genuine regression.

    Each spec: (label, old_value, new_value, direction, is_pct, severity).
    """
    def ratio(e: HistoryEntry):
        if e.apex_business_classes:
            return e.apex_test_classes / e.apex_business_classes * 100
        return None

    return [
        ("Couverture de tests globale", old.test_coverage, new.test_coverage, "up_good", True, "Majeur"),
        ("Couverture Apex", old.test_coverage_apex, new.test_coverage_apex, "up_good", True, "Majeur"),
        ("Couverture Flows", old.test_coverage_flows, new.test_coverage_flows, "up_good", True, "Mineur"),
        ("Ratio classes de test / métier", ratio(old), ratio(new), "up_good", True, "Mineur"),
        ("Findings critiques", old.findings_critical, new.findings_critical, "down_good", False, "Critique"),
        ("Findings majeurs", old.findings_major, new.findings_major, "down_good", False, "Majeur"),
        ("Findings mineurs", old.findings_minor, new.findings_minor, "down_good", False, "Mineur"),
        ("Findings total", old.findings_total, new.findings_total, "down_good", False, "Mineur"),
    ]


def _complexity_specs(old: HistoryEntry, new: HistoryEntry):
    """Informational metrics tracking customization / complexity growth."""
    return [
        ("Score de personnalisation", old.score, new.score, False),
        ("Score Adopt/Adapt", old.adopt_adapt_score, new.adopt_adapt_score, False),
        ("% Adaptation (pro-code)", old.adaptation_pct, new.adaptation_pct, True),
        ("% Adoption (standard)", old.adoption_pct, new.adoption_pct, True),
        ("Objets custom", old.custom_objects, new.custom_objects, False),
        ("Champs custom", old.custom_fields, new.custom_fields, False),
        ("Flows", old.flows, new.flows, False),
        ("Classes Apex (métier)", old.apex_business_classes, new.apex_business_classes, False),
        ("Classes de test", old.apex_test_classes, new.apex_test_classes, False),
        ("Triggers Apex", old.apex_triggers, new.apex_triggers, False),
        ("Composants LWC", old.lwc_count, new.lwc_count, False),
        ("Composants OmniStudio", old.omni_components, new.omni_components, False),
    ]


def _build_quality_section(old: HistoryEntry, new: HistoryEntry):
    """Return (html, regressions, improvements) for the quality analysis."""
    rows = ""
    regressions: list[tuple[str, str, str]] = []  # (label, severity, detail)
    improvements: list[str] = []

    for label, old_v, new_v, direction, is_pct, severity in _quality_specs(old, new):
        delta, status = _classify(old_v, new_v, direction)
        sev = severity if status == "regression" else ""
        if status == "regression":
            detail = f"{_fmt(old_v, is_pct)} \u2192 {_fmt(new_v, is_pct)}"
            regressions.append((label, severity, detail))
        elif status == "improvement":
            improvements.append(label)

        sev_cell = (
            f"<span style='color:{_SEVERITY_COLOR[sev]}; font-weight:600;'>{sev}</span>"
            if sev else ""
        )
        rows += f"""
            <tr>
                <td>{label}</td>
                <td style="text-align:center;">{_fmt(old_v, is_pct)}</td>
                <td style="text-align:center;">{_fmt(new_v, is_pct)}</td>
                {_delta_cell(delta, status, is_pct)}
                <td style="text-align:center;">{_verdict_badge(status)}</td>
                <td style="text-align:center;">{sev_cell}</td>
            </tr>
        """

    html = f"""
    <div class="section">
        <h2>Analyse qualité (régressions & améliorations)</h2>
        <table>
            <thead>
                <tr>
                    <th>Indicateur</th>
                    <th>#{old.generation_number}</th>
                    <th>#{new.generation_number}</th>
                    <th>Écart</th>
                    <th>Verdict</th>
                    <th>Sévérité</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
    </div>
    """
    return html, regressions, improvements


def comparison_regression_count(old: HistoryEntry, new: HistoryEntry) -> int:
    """Return the number of quality regressions between two generations.

    Used by callers (e.g. the index page) that want the regression count
    without rendering the whole comparison page.
    """
    _html, regressions, _improvements = _build_quality_section(old, new)
    return len(regressions)


def _build_complexity_section(old: HistoryEntry, new: HistoryEntry) -> str:
    rows = ""
    for label, old_v, new_v, is_pct in _complexity_specs(old, new):
        delta, _ = _classify(old_v, new_v, "neutral")
        rows += f"""
            <tr>
                <td>{label}</td>
                <td style="text-align:center;">{_fmt(old_v, is_pct)}</td>
                <td style="text-align:center;">{_fmt(new_v, is_pct)}</td>
                {_delta_cell(delta, "neutral", is_pct)}
            </tr>
        """
    return f"""
    <div class="section">
        <h2>Évolution de la personnalisation & complexité</h2>
        <p><small><i>Indicateurs de suivi : une hausse traduit une org plus personnalisée / complexe.</i></small></p>
        <table>
            <thead>
                <tr>
                    <th>Indicateur</th>
                    <th>#{old.generation_number}</th>
                    <th>#{new.generation_number}</th>
                    <th>Écart</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
    </div>
    """


def _build_banner(regressions, improvements) -> str:
    if regressions:
        by_sev: dict[str, int] = {}
        for _label, sev, _detail in regressions:
            by_sev[sev] = by_sev.get(sev, 0) + 1
        parts = ", ".join(
            f"{by_sev[s]} {s.lower()}{'s' if by_sev[s] > 1 else ''}"
            for s in ("Critique", "Majeur", "Mineur")
            if by_sev.get(s)
        )
        items = "".join(
            f"<li><b>{html_value(label)}</b> "
            f"<span style='color:{_SEVERITY_COLOR[sev]};'>({sev})</span> : {html_value(detail)}</li>"
            for label, sev, detail in sorted(
                regressions, key=lambda r: _SEVERITY_RANK[r[1]], reverse=True
            )
        )
        return f"""
        <div style="border-left:6px solid #d1242f; background:#ffebe9; padding:14px 18px;
                    border-radius:6px; margin:18px 0;">
            <div style="font-size:18px; font-weight:700; color:#d1242f;">
                \u26a0 {len(regressions)} régression(s) détectée(s){f' — {parts}' if parts else ''}
            </div>
            <ul style="margin:10px 0 0 0;">{items}</ul>
        </div>
        """
    extra = (
        f" — {len(improvements)} amélioration(s) constatée(s)" if improvements else ""
    )
    return f"""
    <div style="border-left:6px solid #1a7f37; background:#dafbe1; padding:14px 18px;
                border-radius:6px; margin:18px 0;">
        <div style="font-size:18px; font-weight:700; color:#1a7f37;">
            \u2713 Aucune régression détectée{extra}
        </div>
    </div>
    """


def render_comparison(
    new: HistoryEntry,
    old: HistoryEntry,
    current_path: Path,
    assets_dir: Path,
) -> str:
    """Render a metadata comparison between two generations."""
    app_root = Path(__file__).resolve().parent.parent.parent.parent.parent.parent

    # 1. Scan directories to find added, modified, deleted files
    new_dir = Path(new.source_dir)
    if not new_dir.is_absolute():
        new_dir = (app_root / new_dir).resolve()

    old_dir = Path(old.source_dir)
    if not old_dir.is_absolute():
        old_dir = (app_root / old_dir).resolve()

    scan_ok = new_dir.exists() and old_dir.exists()
    if scan_ok:
        new_files = {p.relative_to(new_dir): p for p in new_dir.rglob("*") if p.is_file() and ".vs" not in p.parts}
        old_files = {p.relative_to(old_dir): p for p in old_dir.rglob("*") if p.is_file() and ".vs" not in p.parts}
    else:
        new_files, old_files = {}, {}

    added = sorted([rel for rel in new_files if rel not in old_files])
    deleted = sorted([rel for rel in old_files if rel not in new_files])
    modified = []
    for rel in new_files:
        if rel in old_files:
            if new_files[rel].stat().st_size != old_files[rel].stat().st_size or \
               new_files[rel].stat().st_mtime != old_files[rel].stat().st_mtime:
                modified.append(rel)
    modified.sort()

    def _get_metadata_type(rel_path: Path) -> str:
        parts = rel_path.parts
        if "objects" in parts: return "Object/Field"
        if "classes" in parts: return "Apex Class"
        if "triggers" in parts: return "Apex Trigger"
        if "flows" in parts: return "Flow"
        if "profiles" in parts: return "Profile"
        if "permissionsets" in parts: return "Permission Set"
        if "lwc" in parts: return "LWC"
        if "aura" in parts: return "Aura"
        if "flexipages" in parts: return "Lightning Page"
        if "omniIntegrationProcedures" in parts: return "Omni IP"
        if "omniScripts" in parts: return "OmniScript"
        if "omniUiCard" in parts: return "Omni FlexCard"
        if "omniDataTransforms" in parts: return "Omni Data Transform"
        return "Autre"

    diff_rows = ""
    type_counts = {}  # (type, action) -> count

    for rel in added:
        mtype = _get_metadata_type(rel)
        type_counts[(mtype, "Ajouté")] = type_counts.get((mtype, "Ajouté"), 0) + 1
        diff_rows += f"<tr><td>{html_value(str(rel))}</td><td>{mtype}</td><td><span style='color: green; font-weight: bold;'>Ajouté</span></td></tr>\n"

    for rel in modified:
        mtype = _get_metadata_type(rel)
        type_counts[(mtype, "Modifié")] = type_counts.get((mtype, "Modifié"), 0) + 1
        diff_rows += f"<tr><td>{html_value(str(rel))}</td><td>{mtype}</td><td><span style='color: orange; font-weight: bold;'>Modifié</span></td></tr>\n"

    for rel in deleted:
        mtype = _get_metadata_type(rel)
        type_counts[(mtype, "Supprimé")] = type_counts.get((mtype, "Supprimé"), 0) + 1
        diff_rows += f"<tr><td>{html_value(str(rel))}</td><td>{mtype}</td><td><span style='color: red; font-weight: bold;'>Supprimé</span></td></tr>\n"

    # Summary by type
    all_types = sorted(list(set(t for t, a in type_counts.keys())))
    type_summary_rows = ""
    for t in all_types:
        a_count = type_counts.get((t, "Ajouté"), 0)
        m_count = type_counts.get((t, "Modifié"), 0)
        d_count = type_counts.get((t, "Supprimé"), 0)
        total_t = a_count - d_count
        type_summary_rows += f"""
            <tr>
                <td>{t}</td>
                <td><span style="color: green;">+{a_count}</span></td>
                <td><span style="color: orange;">{m_count}</span></td>
                <td><span style="color: red;">-{d_count}</span></td>
                <td>{total_t:+d}</td>
            </tr>
        """

    # Regression analysis (metric-based, independent from the file scan)
    quality_html, regressions, improvements = _build_quality_section(old, new)
    complexity_html = _build_complexity_section(old, new)
    banner = _build_banner(regressions, improvements)

    scan_warning = "" if scan_ok else (
        "<div style='border-left:6px solid #bc4c00; background:#fff4e5; padding:10px 14px; "
        "border-radius:6px; margin:12px 0;'><b>Note :</b> l'un des répertoires sources est "
        "introuvable, le diff de fichiers n'a pas pu être calculé. L'analyse des indicateurs "
        "reste valide.</div>"
    )

    body = f"""
    <style>
        .resizable-table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
        }}
        .resizable-table th {{
            position: relative;
            padding: 10px;
            border: 1px solid #ddd;
            background: #f9f9f9;
        }}
        .resizable-table td {{
            padding: 8px;
            border: 1px solid #ddd;
            word-break: break-all;
        }}
        .resizer {{
            position: absolute;
            top: 0;
            right: 0;
            width: 5px;
            cursor: col-resize;
            user-select: none;
            height: 100%;
        }}
        .resizer:hover {{
            background: #aaa;
        }}
    </style>

    {index_back_link(current_path, current_path.parent)}
    <h1>Comparaison de générations : {html_value(new.alias)}</h1>
    <p>Comparaison entre la génération #{new.generation_number} ({new.timestamp}) et la génération #{old.generation_number} ({old.timestamp}).</p>

    {banner}
    {scan_warning}

    {quality_html}

    {complexity_html}

    <div class="section">
        <h2>Résumé des changements par type</h2>
        <table>
            <thead>
                <tr><th>Type de métadonnée</th><th>Ajouts</th><th>Modifs</th><th>Suppr.</th><th>Diff nette</th></tr>
            </thead>
            <tbody>
                {type_summary_rows if type_summary_rows else '<tr><td colspan="5" class="empty">Aucun changement.</td></tr>'}
            </tbody>
        </table>
    </div>

    <div class="section">
        <h2>Résumé global (fichiers)</h2>
        <table>
            <thead>
                <tr><th>Indicateur</th><th>#{old.generation_number}</th><th>#{new.generation_number}</th><th>Ajouts</th><th>Modifs</th><th>Suppr.</th><th>Total Diff</th></tr>
            </thead>
            <tbody>
                <tr>
                    <td>Total Fichiers</td>
                    <td>{len(old_files)}</td>
                    <td>{len(new_files)}</td>
                    <td><span style="color: green;">+{len(added)}</span></td>
                    <td><span style="color: orange;">{len(modified)}</span></td>
                    <td><span style="color: red;">-{len(deleted)}</span></td>
                    <td>{len(added) - len(deleted):+d}</td>
                </tr>
            </tbody>
        </table>
    </div>

    <div class="section">
        <h2>Détail des fichiers modifiés</h2>
        <p><small><i>Astuce : Vous pouvez redimensionner les colonnes en glissant les bordures des en-têtes.</i></small></p>
        <div style="max-height: 600px; overflow-y: auto; border: 1px solid #ddd; border-radius: 4px;">
            <table id="diffTable" class="resizable-table">
                <thead>
                    <tr>
                        <th style="width: 70%;">Chemin du fichier<div class="resizer"></div></th>
                        <th style="width: 15%;">Type<div class="resizer"></div></th>
                        <th style="width: 15%;">Action<div class="resizer"></div></th>
                    </tr>
                </thead>
                <tbody>
                    {diff_rows if diff_rows else '<tr><td colspan="3" class="empty">Aucun changement détecté.</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>

    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        const table = document.getElementById('diffTable');
        const cols = table.querySelectorAll('th');

        cols.forEach(col => {{
            const resizer = col.querySelector('.resizer');
            if (!resizer) return;

            let x = 0;
            let w = 0;

            const mouseDownHandler = function(e) {{
                x = e.clientX;
                const styles = window.getComputedStyle(col);
                w = parseInt(styles.width, 10);

                document.addEventListener('mousemove', mouseMoveHandler);
                document.addEventListener('mouseup', mouseUpHandler);
                resizer.classList.add('resizing');
            }};

            const mouseMoveHandler = function(e) {{
                const dx = e.clientX - x;
                col.style.width = `${{w + dx}}px`;
            }};

            const mouseUpHandler = function() {{
                document.removeEventListener('mousemove', mouseMoveHandler);
                document.removeEventListener('mouseup', mouseUpHandler);
                resizer.classList.remove('resizing');
            }};

            resizer.addEventListener('mousedown', mouseDownHandler);
        }});
    }});
    </script>

    <div class="section">
        <h2>Répertoires sources</h2>
        <dl>
            <dt>Source #{old.generation_number}:</dt><dd><code>{html_value(href_relative(current_path, (app_root / Path(old.source_dir)).resolve()))}</code></dd>
            <dt>Source #{new.generation_number}:</dt><dd><code>{html_value(href_relative(current_path, (app_root / Path(new.source_dir)).resolve()))}</code></dd>
        </dl>
    </div>
    """
    return render_page(f"Comparaison {new.alias}", body, current_path, assets_dir, include_mermaid=False)
