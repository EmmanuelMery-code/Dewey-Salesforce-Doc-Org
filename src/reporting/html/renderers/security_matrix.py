"""Render the security comparison matrix."""

from __future__ import annotations

from pathlib import Path
from src.core.models import MetadataSnapshot, SecurityArtifact
from src.core.utils import html_value, safe_slug
from src.reporting.html.page_shell import href_relative, render_page, index_back_link

def write_security_matrix_page(
    snapshot: MetadataSnapshot,
    output_dir: Path,
    assets_dir: Path,
) -> Path:
    path = output_dir / "security_matrix.html"
    
    # We'll compare the first 5 profiles/permsets by default, or let user choose (future)
    # For now, let's list all objects and their CRUD for all profiles/permsets in a big table
    
    objects = sorted({obj.api_name for obj in snapshot.objects})
    artifacts = sorted(snapshot.profiles + snapshot.permission_sets, key=lambda x: x.name.lower())
    
    headers = ["Objet"] + [art.name for art in artifacts]
    
    rows = []
    for obj_name in objects:
        row = [f"<td>{html_value(obj_name)}</td>"]
        for art in artifacts:
            perm = next((p for p in art.object_permissions if p.object_name == obj_name), None)
            if perm:
                crud = ""
                if perm.allow_read: crud += "R"
                if perm.allow_create: crud += "C"
                if perm.allow_edit: crud += "U"
                if perm.allow_delete: crud += "D"
                if perm.view_all_records: crud += "V"
                if perm.modify_all_records: crud += "M"
                row.append(f"<td title='{art.name} on {obj_name}'>{crud}</td>")
            else:
                row.append("<td class='empty'>-</td>")
        rows.append(f"<tr>{''.join(row)}</tr>")
        
    table = f"<table><thead><tr>{''.join(f'<th>{h}</th>' for h in headers)}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    
    body = f"""
{index_back_link(path, output_dir)}
<h1>Matrice de securite (CRUD)</h1>
<p>Cette matrice compare les permissions d'acces aux objets pour tous les profils et permission sets analyses.</p>

<div class='section' style='margin-bottom: 20px; padding: 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;'>
    <h3 style='margin-top: 0;'>Legende des permissions :</h3>
    <ul style='list-style: none; padding: 0; display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 0;'>
        <li><strong>R</strong> : Read (Lecture)</li>
        <li><strong>C</strong> : Create (Creation)</li>
        <li><strong>U</strong> : Update (Modification)</li>
        <li><strong>D</strong> : Delete (Suppression)</li>
        <li><strong>V</strong> : View All (Voir tout)</li>
        <li><strong>M</strong> : Modify All (Modifier tout)</li>
    </ul>
</div>

<div style='overflow:auto; max-height: 80vh;'>
{table}
</div>
"""
    from src.core.utils import write_text
    write_text(path, render_page("Matrice de securite", body, path, assets_dir))
    return path
