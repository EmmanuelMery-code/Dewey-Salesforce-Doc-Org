"""Render the permission set groups listing page."""

from __future__ import annotations

from pathlib import Path
from src.core.models import MetadataSnapshot, PermissionSetGroupInfo
from src.core.utils import html_value, safe_slug
from src.reporting.html.page_shell import href_relative, render_page, index_back_link

def write_psg_list_page(
    snapshot: MetadataSnapshot,
    output_dir: Path,
    assets_dir: Path,
) -> Path:
    path = output_dir / "psg_list.html"
    
    rows = []
    for psg in snapshot.permission_set_groups:
        rows.append(f"""
<tr>
    <td>{html_value(psg.name)}</td>
    <td>{html_value(psg.label)}</td>
    <td>{html_value(psg.status)}</td>
    <td>{", ".join(psg.permission_sets)}</td>
    <td>{html_value(psg.description)}</td>
</tr>
""")
        
    table = f"""
<table>
    <thead>
        <tr>
            <th>Nom API</th>
            <th>Label</th>
            <th>Statut</th>
            <th>Permission Sets inclus</th>
            <th>Description</th>
        </tr>
    </thead>
    <tbody>
        {''.join(rows)}
    </tbody>
</table>
"""
    
    body = f"""
{index_back_link(path, output_dir)}
<h1>Permission Set Groups</h1>
<p>Liste des groupes d'ensembles de permissions analyses.</p>
{table}
"""
    from src.core.utils import write_text
    write_text(path, render_page("Permission Set Groups", body, path, assets_dir))
    return path
