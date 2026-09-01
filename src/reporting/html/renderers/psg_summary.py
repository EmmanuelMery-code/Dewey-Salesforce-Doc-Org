"""Synthese des Permission Set Groups : CRUD et Sharing & Visibility par objet.

Rend la matrice objet x groupe du sous-onglet "PSet Group Summary" de l'onglet
"Profiles & PS". Le calcul des droits effectifs vit dans
:mod:`src.core.psg_access`, partage avec la page de detail et le classeur Excel.
"""

from __future__ import annotations

from typing import Collection

from src.core.models import MetadataSnapshot
from src.core.psg_access import (
    ALL_FLAGS,
    CRUD_FLAGS,
    SHARING_FLAGS,
    STATUS_HELP,
    GroupAccess,
    GroupObjectAccess,
    build_group_access,
    covered_object_names,
    listed_object_names,
    sharing_context,
)
from src.core.utils import html_value, safe_slug
from src.reporting.html.page_shell import tab_panel_id

#: Onglets de index.html vises depuis la matrice : les regles de partage d'un
#: objet s'y lisent, filtrees par la recherche globale de la page.
INDEX_TAB_GROUP = "index"
SHARING_RULES_TAB_LABEL = "Sharing Rules"
SHARING_RULES_PANEL_ID = tab_panel_id(INDEX_TAB_GROUP, SHARING_RULES_TAB_LABEL)

# Sections de la page de detail visees par les titres des cadrans.
DETAIL_ANCHORS: dict[str, str] = {
    "groups": "psg-groups",
    "permission_sets": "psg-permission-sets",
    "objects": "psg-objects",
    "modify_all": "psg-modify-all",
    "view_all": "psg-view-all",
    "status": "psg-status",
    "coverage": "psg-coverage",
}


def _flag_cell(access: GroupObjectAccess | None, flags: tuple[tuple[str, str, str], ...]) -> str:
    if access is None:
        return "<td class='psg-cell'><span class='psg-none'>&mdash;</span></td>"
    badges = []
    for code, label, attribute in flags:
        sources = access.sources(attribute)
        if sources:
            title = f"{label} — accorde par : {', '.join(sources)}"
            css = "psg-flag on"
        else:
            title = f"{label} — non accorde"
            css = "psg-flag off"
        badges.append(f"<span class='{css}' title='{html_value(title)}'>{code}</span>")
    return "<td class='psg-cell'>" + "".join(badges) + "</td>"


def _kpi(
    label: str,
    value: object,
    hint: str = "",
    color: str = "",
    href: str = "",
) -> str:
    value_style = f"font-size:1.5em;font-weight:bold{f';color:{color}' if color else ''}"
    hint_html = f"<div style='font-size:.8em;color:#64748b'>{html_value(hint)}</div>" if hint else ""
    title = html_value(label)
    if href:
        title = (
            f"<a href='{href}' title='Voir le detail et les explications'>{title}</a>"
        )
    return (
        "<div style='flex:1;min-width:180px;padding:10px 14px;border:1px solid "
        f"{color + '33' if color else '#e2e8f0'};border-radius:6px'>"
        f"<div style='font-size:.8em;color:#64748b'>{title}</div>"
        f"<div style='{value_style}'>{html_value(value)}</div>"
        f"{hint_html}</div>"
    )


def _detail_href(details_href: str, key: str) -> str:
    if not details_href:
        return ""
    return f"{details_href}#{DETAIL_ANCHORS[key]}"


def _render_kpis(
    accesses: list[GroupAccess],
    covered_names: set[str],
    object_names: list[str],
    details_href: str = "",
) -> str:
    active = sum(1 for item in accesses if (item.group.status or "").lower() == "updated")
    members = {name for item in accesses for name in item.group.permission_sets if name}
    unresolved = {name for item in accesses for name in item.unresolved_permission_sets}
    modify_all = sum(
        1
        for item in accesses
        for entry in item.objects.values()
        if entry.granted("modify_all_records")
    )
    view_all = sum(
        1
        for item in accesses
        for entry in item.objects.values()
        if entry.granted("view_all_records")
    )
    cards = [
        _kpi(
            "Permission Set Groups",
            len(accesses),
            f"{active} au statut Updated",
            href=_detail_href(details_href, "groups"),
        ),
        _kpi(
            "Permission Sets membres",
            len(members),
            f"{len(unresolved)} non analyse(s)",
            href=_detail_href(details_href, "permission_sets"),
        ),
        _kpi(
            "Objets couverts",
            len(covered_names),
            f"sur {len(object_names)} objet(s) listes",
            href=_detail_href(details_href, "objects"),
        ),
        _kpi(
            "Couples groupe/objet avec Modify All",
            modify_all,
            "Droit le plus large : contourne le partage",
            "#ff4444" if modify_all else "#22aa66",
            href=_detail_href(details_href, "modify_all"),
        ),
        _kpi(
            "Couples groupe/objet avec View All",
            view_all,
            "Lecture de tous les enregistrements",
            "#ff8c00" if view_all else "#22aa66",
            href=_detail_href(details_href, "view_all"),
        ),
    ]
    return (
        "<div style='display:flex;gap:16px;flex-wrap:wrap;margin-bottom:14px'>"
        + "".join(cards)
        + "</div>"
    )


def _render_legend(details_href: str = "") -> str:
    crud = " ".join(f"<strong>{code}</strong> = {html_value(label)}" for code, label, _ in CRUD_FLAGS)
    sharing = " ".join(
        f"<strong>{code}</strong> = {html_value(label)}" for code, label, _ in SHARING_FLAGS
    )
    status = " &middot; ".join(
        f"<strong title='{html_value(description)}'>{value}</strong>"
        for value, description in STATUS_HELP
    )
    status_href = _detail_href(details_href, "status")
    status_link = (
        f" <a href='{status_href}'>Detail des statuts</a>" if status_href else ""
    )
    coverage_href = _detail_href(details_href, "coverage")
    coverage_link = (
        f" <a href='{coverage_href}'>Pourquoi un objet est-il couvert ou non ?</a>"
        if coverage_href
        else ""
    )
    return (
        "<div style='margin:10px 0;padding:10px 12px;background:#f8fafc;border:1px solid #e2e8f0;"
        "border-radius:6px;font-size:.85em'>"
        f"<div><em>CRUD</em> : {crud}</div>"
        f"<div><em>Sharing &amp; Visibility</em> : {sharing}</div>"
        f"<div><em>Statut</em> du groupe (etat du calcul des droits agreges par la "
        f"plateforme, survolez chaque valeur) : {status}.{status_link}</div>"
        "<div><span class='psg-flag on'>R</span> droit accorde &middot; "
        "<span class='psg-flag off'>R</span> droit absent. Survolez un droit pour voir le "
        "ou les permission sets qui l'accordent. <em>OWD</em> = Organization-Wide Default "
        "(modele de partage de l'objet). Tous les objets analyses sont listes : une ligne "
        "entierement vide signifie qu'aucun groupe n'accorde de droit sur cet objet."
        f"{coverage_link}</div>"
        "</div>"
    )


def _object_link(object_name: str, object_hrefs: dict[str, str]) -> str:
    """Nom de l'objet, cliquable vers sa page quand elle a ete generee."""

    label = html_value(object_name)
    href = object_hrefs.get(object_name)
    if not href:
        return label
    return f"<a href='{href}' title='Ouvrir la page de l&#39;objet {label}'>{label}</a>"


def _sharing_rules_cell(object_name: str, rule_count: int) -> str:
    """Nombre de regles de partage, cliquable vers l'onglet Sharing Rules.

    Le lien remplit la recherche globale de la page avec le nom de l'objet, de
    sorte que l'onglet n'affiche que les regles de cet objet.
    """

    if not rule_count:
        return "<td class='psg-owd'><span class='psg-none'>&mdash;</span></td>"
    label = html_value(object_name)
    return (
        f"<td class='psg-owd'><a href='#{SHARING_RULES_PANEL_ID}' "
        f"data-psg-sharing-filter='{label}' "
        f"title='Voir les {rule_count} regle(s) de partage de {label} dans "
        f"l&#39;onglet Sharing Rules'>{rule_count}</a></td>"
    )


def _render_matrix(
    accesses: list[GroupAccess],
    object_names: list[str],
    owd: dict[str, str],
    rule_counts: dict[str, int],
    selected_objects: set[str],
    object_hrefs: dict[str, str],
) -> str:
    head_groups = "".join(
        "<th colspan='2' class='psg-group-head' "
        f"title='{html_value(item.group.label or item.group.name)} — "
        f"{len(item.group.permission_sets)} permission set(s)'>"
        f"{html_value(item.group.label or item.group.name)}</th>"
        for item in accesses
    )
    head_subs = "".join(
        "<th class='psg-sub'>CRUD</th><th class='psg-sub'>Sharing &amp; Visibility</th>"
        for _ in accesses
    )

    rows = []
    uncovered_count = 0
    for object_name in object_names:
        entries = [item.objects.get(object_name) for item in accesses]
        covered = any(entry is not None for entry in entries)
        if not covered:
            uncovered_count += 1
        wide = any(
            entry is not None
            and (entry.granted("modify_all_records") or entry.granted("view_all_records"))
            for entry in entries
        )
        cells = "".join(
            _flag_cell(entry, CRUD_FLAGS) + _flag_cell(entry, SHARING_FLAGS)
            for entry in entries
        )
        rows.append(
            f"<tr data-object='{html_value(object_name.lower())}' data-wide='{'1' if wide else '0'}'"
            f" data-covered='{'1' if covered else '0'}'"
            f" data-selected='{'1' if object_name in selected_objects else '0'}'>"
            f"<th scope='row' class='psg-sticky'>{_object_link(object_name, object_hrefs)}</th>"
            f"<td class='psg-owd'>{html_value(owd.get(object_name) or '—')}</td>"
            f"{_sharing_rules_cell(object_name, rule_counts.get(object_name, 0))}"
            f"{cells}</tr>"
        )

    covered_toggle = ""
    if uncovered_count:
        covered_toggle = (
            "<label title='Masque les objets sans aucun droit accorde par un "
            f"groupe : {uncovered_count} objet(s)'>"
            "<input type='checkbox' id='psg-matrix-covered-only'> "
            "Uniquement les objets couverts</label>"
        )

    selected_toggle = ""
    if selected_objects:
        selected_toggle = (
            "<label title='Objets coches dans le Data Dictionnary : "
            f"{len(selected_objects)} objet(s)'>"
            "<input type='checkbox' id='psg-matrix-selected-only'> "
            "Filtrer sur les objets selectionnes</label>"
        )

    return f"""
<div class='psg-toolbar'>
  <input type='search' id='psg-matrix-filter' placeholder='Filtrer par objet...' aria-label='Filtrer par objet'>
  <label><input type='checkbox' id='psg-matrix-wide-only'> Uniquement les objets avec View All / Modify All</label>
  {covered_toggle}
  {selected_toggle}
  <span id='psg-matrix-count' class='psg-count'>{len(object_names)} objet(s)</span>
</div>
<div class='psg-matrix-wrap'>
  <table class='psg-matrix' id='psg-matrix'>
    <thead>
      <tr>
        <th rowspan='2' class='psg-sticky'>Objet</th>
        <th rowspan='2'>OWD</th>
        <th rowspan='2'>Regles de partage</th>
        {head_groups}
      </tr>
      <tr>{head_subs}</tr>
    </thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</div>
<script>
(() => {{
  const table = document.getElementById('psg-matrix');
  const filter = document.getElementById('psg-matrix-filter');
  const wideOnly = document.getElementById('psg-matrix-wide-only');
  const coveredOnly = document.getElementById('psg-matrix-covered-only');
  const selectedOnly = document.getElementById('psg-matrix-selected-only');
  const counter = document.getElementById('psg-matrix-count');
  if (!table || !filter || !wideOnly) return;
  const rows = Array.from(table.tBodies[0].rows);
  const apply = () => {{
    const term = filter.value.trim().toLowerCase();
    let visible = 0;
    rows.forEach((row) => {{
      const matches = (row.dataset.object || '').includes(term)
        && (!wideOnly.checked || row.dataset.wide === '1')
        && (!coveredOnly || !coveredOnly.checked || row.dataset.covered === '1')
        && (!selectedOnly || !selectedOnly.checked || row.dataset.selected === '1');
      row.style.display = matches ? '' : 'none';
      if (matches) visible += 1;
    }});
    if (counter) counter.textContent = visible + ' objet(s)';
  }};
  filter.addEventListener('input', apply);
  wideOnly.addEventListener('change', apply);
  if (coveredOnly) coveredOnly.addEventListener('change', apply);
  if (selectedOnly) selectedOnly.addEventListener('change', apply);
  // Le nombre de regles de partage ouvre l'onglet Sharing Rules en reportant
  // le nom de l'objet dans la recherche globale, qui filtre ses lignes.
  table.querySelectorAll('[data-psg-sharing-filter]').forEach((link) => {{
    link.addEventListener('click', () => {{
      const search = document.getElementById('global-search');
      if (!search) return;
      search.value = link.dataset.psgSharingFilter;
      search.dispatchEvent(new Event('input', {{ bubbles: true }}));
    }});
  }});
}})();
</script>
"""


def _render_group_details(
    accesses: list[GroupAccess],
    owd: dict[str, str],
) -> str:
    blocks = []
    for item in accesses:
        object_names = sorted(item.objects, key=str.lower)
        rows = []
        for object_name in object_names:
            entry = item.objects[object_name]
            flags = "".join(
                (
                    "<td class='psg-check on'>&#10003;</td>"
                    if entry.granted(attribute)
                    else "<td class='psg-check off'>&mdash;</td>"
                )
                for _code, _label, attribute in ALL_FLAGS
            )
            rows.append(
                f"<tr><td>{html_value(object_name)}</td>"
                f"<td>{html_value(owd.get(object_name) or '—')}</td>"
                f"{flags}"
                f"<td>{html_value(', '.join(entry.contributors))}</td></tr>"
            )
        body = "".join(rows) or (
            "<tr><td colspan='10' class='empty'>Aucun droit objet accorde par ce groupe.</td></tr>"
        )
        warning = ""
        if item.unresolved_permission_sets:
            warning = (
                "<p style='color:#a04000'>Permission sets references mais absents de "
                "l'analyse : "
                f"{html_value(', '.join(item.unresolved_permission_sets))}</p>"
            )
        blocks.append(f"""
<details id='psg-detail-{safe_slug(item.group.name)}'>
  <summary><strong>{html_value(item.group.label or item.group.name)}</strong>
    &nbsp;<span style='color:#64748b'>{html_value(item.group.name)} &middot;
    {len(item.group.permission_sets)} permission set(s) &middot;
    {len(object_names)} objet(s) &middot; statut {html_value(item.group.status or 'n/a')}</span>
  </summary>
  <p style='color:#475569'>Permission sets : {html_value(', '.join(item.group.permission_sets) or 'aucun')}</p>
  {warning}
  <table>
    <thead><tr>
      <th>Objet</th><th>OWD</th>
      <th>Create</th><th>Read</th><th>Update</th><th>Delete</th>
      <th>View All</th><th>Modify All</th><th>View All Fields</th>
      <th>Accorde par</th>
    </tr></thead>
    <tbody>{body}</tbody>
  </table>
</details>""")
    return "<h4>Detail par groupe</h4>" + "".join(blocks)


def render_psg_group_summary(
    snapshot: MetadataSnapshot,
    psg_list_href: str = "",
    data_dictionary_objects: Collection[str] | None = None,
    details_href: str = "",
    workbook_href: str = "",
    object_hrefs: dict[str, str] | None = None,
) -> str:
    """Construit le panneau HTML du sous-onglet "PSet Group Summary".

    ``data_dictionary_objects`` porte les objets coches dans l'ecran Data
    Dictionnary : quand cette liste n'est pas vide, la matrice propose une
    case a cocher restreignant l'affichage a ces objets.

    ``details_href`` pointe la page de detail : les titres des cadrans et la
    legende y renvoient, section par section. ``workbook_href`` pointe le
    classeur Excel equivalent, quand il a ete genere. ``object_hrefs`` porte
    la page de chaque objet, cible du nom affiche dans la matrice.
    """

    accesses = build_group_access(snapshot)
    if not accesses:
        return (
            "<p class='empty'>Aucun Permission Set Group analyse : la matrice CRUD / "
            "Sharing &amp; Visibility par groupe n'est pas disponible.</p>"
        )

    owd, rule_counts = sharing_context(snapshot)
    covered_names = covered_object_names(accesses)
    object_names = listed_object_names(snapshot, accesses)
    link = (
        f"<p><a href='{psg_list_href}' target='_blank' rel='noopener'>Ouvrir la liste "
        "des Permission Set Groups dans un nouvel onglet</a></p>"
        if psg_list_href
        else ""
    )
    workbook_link = (
        f"<p><a href='{workbook_href}'>Telecharger le classeur Excel equivalent</a> "
        "(un onglet par tableau de cette page et de sa page de detail).</p>"
        if workbook_href
        else ""
    )
    selected_objects = {str(name) for name in data_dictionary_objects or ()}
    matrix = (
        _render_matrix(
            accesses,
            object_names,
            owd,
            rule_counts,
            selected_objects,
            object_hrefs or {},
        )
        if object_names
        else "<p class='empty'>Aucun objet analyse et aucun droit objet accorde par "
        "les Permission Set Groups analyses.</p>"
    )
    return f"""
<h4>Permission Set Groups &mdash; synthese des droits objet</h4>
<p>Droits effectifs de chaque groupe, calcules comme l'union des object permissions
de ses permission sets membres.</p>
{workbook_link}
{_render_kpis(accesses, covered_names, object_names, details_href)}
{_render_legend(details_href)}
{matrix}
{_render_group_details(accesses, owd)}
{link}
"""
