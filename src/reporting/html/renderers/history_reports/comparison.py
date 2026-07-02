"""Metadata comparison renderer between two history entries."""

from __future__ import annotations

from pathlib import Path

from src.core.history_service import HistoryEntry
from src.core.utils import html_value
from src.reporting.html.page_shell import href_relative, index_back_link, render_page


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

    new_files = {p.relative_to(new_dir): p for p in new_dir.rglob("*") if p.is_file() and ".vs" not in p.parts}
    old_files = {p.relative_to(old_dir): p for p in old_dir.rglob("*") if p.is_file() and ".vs" not in p.parts}

    added = sorted([rel for rel in new_files if rel not in old_files])
    deleted = sorted([rel for rel in old_files if rel not in new_files])
    modified = []
    for rel in new_files:
        if rel in old_files:
            # Simple size/mtime check for "modified" or could do hash, but let's stay simple
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
    type_counts = {} # (type, action) -> count

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

    # Volumetry summary based on actual file diff
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
        /* Column resizing handle */
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
    <h1>Comparaison de métadonnées : {html_value(new.alias)}</h1>
    <p>Comparaison entre la génération #{new.generation_number} ({new.timestamp}) et la génération #{old.generation_number} ({old.timestamp}).</p>
    
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
        <h2>Indicateurs Clés</h2>
        <table>
            <thead>
                <tr><th>Indicateur</th><th>#{old.generation_number}</th><th>#{new.generation_number}</th><th>Différence</th></tr>
            </thead>
            <tbody>
                <tr>
                    <td>Score Global</td>
                    <td>{old.score}</td>
                    <td>{new.score}</td>
                    <td>{new.score - old.score:+d}</td>
                </tr>
                <tr>
                    <td>Couverture de tests</td>
                    <td>{f"{old.test_coverage:.1f}%" if old.test_coverage is not None else "N/A"}</td>
                    <td>{f"{new.test_coverage:.1f}%" if new.test_coverage is not None else "N/A"}</td>
                    <td>
                        {f"{new.test_coverage - old.test_coverage:+.1f}%" if new.test_coverage is not None and old.test_coverage is not None else "N/A"}
                    </td>
                </tr>
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
    // Simple table resizer logic
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
