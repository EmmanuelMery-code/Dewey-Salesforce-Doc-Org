"""Page de detail des chiffres du sous-onglet "PSet Group Summary".

Les titres des cadrans de la matrice pointent chacun une section de cette
page : le chiffre y est detaille ligne par ligne et explique, de sorte que le
sous-onglet reste lisible sans noyer la matrice de commentaires.
"""

from __future__ import annotations

from pathlib import Path

from src.core.models import MetadataSnapshot
from src.core.psg_access import (
    ALL_FLAGS,
    COVERAGE_REASONS,
    STATUS_HELP,
    GroupAccess,
    build_group_access,
)
from src.core.utils import html_value, safe_slug, write_text
from src.reporting.html.page_shell import index_back_link, render_page
from src.reporting.html.renderers.psg_summary import DETAIL_ANCHORS

SUMMARY_TAB_LABEL = "PSet Group Summary"
SECURITY_TAB_GROUP = "index-security"


def _table(headers: list[str], rows: list[str]) -> str:
    head = "".join(f"<th>{header}</th>" for header in headers)
    body = "".join(rows) or (
        f"<tr><td colspan='{len(headers)}' class='empty'>Aucune ligne.</td></tr>"
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _section(anchor: str, title: str, intro: str, content: str) -> str:
    return f"""
<section id='{anchor}' class='psg-detail-section'>
  <h2>{title}</h2>
  {intro}
  {content}
</section>"""


def _status_cell(status: str) -> str:
    description = next(
        (help_text for value, help_text in STATUS_HELP if value == status), ""
    )
    if not status:
        return "<td><span class='psg-none'>non renseigne</span></td>"
    color = {"Outdated": "#a04000", "Failed": "#c00", "Updating": "#665500"}.get(
        status, "#15803d"
    )
    return (
        f"<td style='color:{color};font-weight:600' title='{html_value(description)}'>"
        f"{html_value(status)}</td>"
    )


def _count_pairs(accesses: list[GroupAccess], attribute: str) -> int:
    return sum(
        1
        for access in accesses
        for entry in access.objects.values()
        if entry.granted(attribute)
    )


def _render_status_section() -> str:
    rows = [
        f"<tr>{_status_cell(value)}<td>{html_value(description)}</td></tr>"
        for value, description in STATUS_HELP
    ]
    intro = (
        "<p>Le statut d'un Permission Set Group decrit l'etat du calcul realise "
        "par la plateforme : un groupe n'accorde aucun droit par lui-meme, "
        "Salesforce agrege les droits de ses permission sets membres et met le "
        "resultat en cache. Le statut dit si ce cache est a jour.</p>"
        "<p><strong>Consequence sur cette documentation</strong> : Dewey recalcule "
        "l'union des droits a partir des metadonnees des permission sets membres. "
        "Pour un groupe <em>Updated</em>, cette union correspond aux droits "
        "reellement appliques. Pour un groupe <em>Outdated</em>, <em>Updating</em> "
        "ou <em>Failed</em>, l'org peut encore appliquer un calcul plus ancien : la "
        "matrice montre alors la cible et non l'etat courant.</p>"
    )
    return _section(
        DETAIL_ANCHORS["status"],
        "Statut d'un Permission Set Group",
        intro,
        _table(["Statut", "Signification"], rows),
    )


def _render_groups_section(accesses: list[GroupAccess]) -> str:
    rows = []
    for access in accesses:
        modify_all = sum(
            1 for entry in access.objects.values() if entry.granted("modify_all_records")
        )
        view_all = sum(
            1 for entry in access.objects.values() if entry.granted("view_all_records")
        )
        unresolved = (
            html_value(", ".join(access.unresolved_permission_sets))
            if access.unresolved_permission_sets
            else "<span class='psg-none'>&mdash;</span>"
        )
        rows.append(
            f"<tr><td>{html_value(access.group.name)}</td>"
            f"<td>{html_value(access.group.label)}</td>"
            f"{_status_cell(access.group.status)}"
            f"<td>{len(access.group.permission_sets)}</td>"
            f"<td>{unresolved}</td>"
            f"<td>{len(access.objects)}</td>"
            f"<td>{modify_all}</td><td>{view_all}</td>"
            f"<td>{html_value(access.group.description)}</td></tr>"
        )
    intro = (
        "<p>Un groupe est compte des lors qu'un fichier "
        "<code>*.permissionsetgroup-meta.xml</code> a ete trouve dans la source "
        "analysee. Un groupe absent du <code>package.xml</code> du retrieve "
        "n'apparait donc pas, meme s'il existe dans l'org.</p>"
    )
    return _section(
        DETAIL_ANCHORS["groups"],
        "Permission Set Groups analyses",
        intro,
        _table(
            [
                "Nom API",
                "Label",
                "Statut",
                "PS membres",
                "PS non analyses",
                "Objets couverts",
                "Objets avec Modify All",
                "Objets avec View All",
                "Description",
            ],
            rows,
        ),
    )


def _render_permission_sets_section(
    snapshot: MetadataSnapshot,
    accesses: list[GroupAccess],
) -> str:
    permission_sets = {item.name: item for item in snapshot.permission_sets}
    groups_by_member: dict[str, list[str]] = {}
    for access in accesses:
        for member in access.group.permission_sets:
            if member:
                groups_by_member.setdefault(member, []).append(access.group.name)

    rows = []
    for member in sorted(groups_by_member, key=str.lower):
        artifact = permission_sets.get(member)
        if artifact is None:
            analysed = (
                "<td style='color:#a04000;font-weight:600' title='Le permission set est "
                "reference par le groupe mais absent de la source analysee : ses droits "
                "ne sont pas comptes dans la matrice.'>Non analyse</td>"
            )
            object_count = "<span class='psg-none'>&mdash;</span>"
        else:
            analysed = "<td style='color:#15803d;font-weight:600'>Analyse</td>"
            object_count = str(len(artifact.object_permissions))
        rows.append(
            f"<tr><td>{html_value(member)}</td>{analysed}"
            f"<td>{len(groups_by_member[member])}</td>"
            f"<td>{html_value(', '.join(sorted(groups_by_member[member], key=str.lower)))}</td>"
            f"<td>{object_count}</td></tr>"
        )
    intro = (
        "<p>Le chiffre du cadran compte les permission sets <em>distincts</em> "
        "references par au moins un groupe : un permission set partage entre trois "
        "groupes ne compte qu'une fois. Les permission sets de l'org qui "
        "n'appartiennent a aucun groupe ne sont pas comptes ici, ils figurent dans "
        "le sous-onglet <em>Permission Sets</em>.</p>"
        "<p>Un permission set <em>non analyse</em> est reference par un groupe mais "
        "absent de la source : son contenu est inconnu, donc les droits qu'il "
        "accorde manquent dans la matrice. C'est le cas typique d'un retrieve dont "
        "le manifest ne liste pas tous les permission sets, ou d'un permission set "
        "issu d'un package installe.</p>"
    )
    return _section(
        DETAIL_ANCHORS["permission_sets"],
        "Permission Sets membres des groupes",
        intro,
        _table(
            ["Permission Set", "Etat", "Nb groupes", "Groupes", "Droits objet"],
            rows,
        ),
    )


def _render_objects_section(
    snapshot: MetadataSnapshot,
    accesses: list[GroupAccess],
) -> str:
    covered: dict[str, list[str]] = {}
    for access in accesses:
        for object_name in access.objects:
            covered.setdefault(object_name, []).append(access.group.name)
    owd = {item.api_name: item.sharing_model for item in snapshot.objects if item.api_name}

    covered_rows = []
    for object_name in sorted(covered, key=str.lower):
        groups = sorted(covered[object_name], key=str.lower)
        parsed = (
            "Oui"
            if object_name in owd
            else "<span title='Objet non present dans le dossier objects/ de la source : "
            "son modele de partage est inconnu.'>Non</span>"
        )
        covered_rows.append(
            f"<tr><td>{html_value(object_name)}</td>"
            f"<td>{html_value(owd.get(object_name) or '—')}</td>"
            f"<td>{parsed}</td>"
            f"<td>{len(groups)}</td>"
            f"<td>{html_value(', '.join(groups))}</td></tr>"
        )

    uncovered_rows = [
        f"<tr><td>{html_value(item.api_name)}</td>"
        f"<td>{html_value(item.sharing_model or '—')}</td>"
        f"<td>{len(item.fields)}</td></tr>"
        for item in sorted(snapshot.objects, key=lambda obj: obj.api_name.lower())
        if item.api_name and item.api_name not in covered
    ]

    reasons = "".join(
        f"<li><strong>{html_value(title)}</strong> &mdash; {html_value(explanation)}</li>"
        for title, explanation in COVERAGE_REASONS
    )
    intro = f"""
<p>La matrice liste <strong>tous</strong> les objets analyses dans la source, plus
les objets references par un permission set membre. Un objet dont toutes les
cellules sont vides est donc bien present : cela signifie qu'aucun groupe analyse
ne lui accorde de droit, ce qui est une information en soi.</p>
<p>Un objet est dit <em>couvert</em> quand au moins un permission set membre d'un
groupe porte un bloc <code>objectPermissions</code> pour lui : c'est ce chiffre
que compte le cadran <em>Objets couverts</em>.</p>
<h3 id='{DETAIL_ANCHORS['coverage']}'>Pourquoi un objet est-il couvert ou non ?</h3>
<ul>{reasons}</ul>
<p>Pour les permission sets absents de la source, voir la section
<a href='#{DETAIL_ANCHORS['permission_sets']}'>Permission Sets membres</a>. Un objet
non retrieve se repere a la colonne <em>Objet analyse</em> a Non ci-dessous.</p>"""

    content = (
        "<h3>Objets couverts par au moins un groupe</h3>"
        + _table(
            ["Objet", "OWD", "Objet analyse", "Nb groupes", "Groupes"],
            covered_rows,
        )
        + "<h3>Objets analyses sans aucun droit via un groupe</h3>"
        + "<p>Ces objets ont ete parses depuis <code>objects/</code> mais aucun "
        "permission set membre d'un groupe ne leur accorde de droit. Ils figurent "
        "dans la matrice avec des cellules vides ; la case <em>Uniquement les objets "
        "couverts</em> permet de les masquer.</p>"
        + _table(["Objet", "OWD", "Nb champs"], uncovered_rows)
    )
    return _section(
        DETAIL_ANCHORS["objects"],
        "Couverture des objets",
        intro,
        content,
    )


def _render_wide_access_section(
    accesses: list[GroupAccess],
    anchor: str,
    title: str,
    attribute: str,
    intro: str,
) -> str:
    rows = []
    for access in accesses:
        for object_name in sorted(access.objects, key=str.lower):
            entry = access.objects[object_name]
            if not entry.granted(attribute):
                continue
            rows.append(
                f"<tr><td>{html_value(access.group.label or access.group.name)}</td>"
                f"{_status_cell(access.group.status)}"
                f"<td>{html_value(object_name)}</td>"
                f"<td>{html_value(', '.join(entry.sources(attribute)))}</td></tr>"
            )
    return _section(
        anchor,
        title,
        intro,
        _table(["Groupe", "Statut", "Objet", "Accorde par"], rows),
    )


def write_psg_details_page(
    snapshot: MetadataSnapshot,
    output_dir: Path,
    assets_dir: Path,
) -> Path:
    """Ecrit la page de detail liee aux cadrans du sous-onglet."""

    path = output_dir / "psg_summary_details.html"
    accesses = build_group_access(snapshot)
    flags = ", ".join(f"{code} ({label})" for code, label, _ in ALL_FLAGS)

    modify_all_intro = f"""
<p>Un couple groupe/objet est compte des qu'un permission set membre accorde
<em>Modify All</em> sur cet objet. C'est le droit le plus large au niveau objet :
il donne lecture, modification et suppression de <strong>tous</strong> les
enregistrements de l'objet, quels que soient le proprietaire, l'OWD et les
regles de partage.</p>
<p>A ne pas confondre avec la permission systeme <em>ModifyAllData</em>, qui
porte sur toute l'org et non sur un objet. Les {_count_pairs(accesses, 'modify_all_records')}
couple(s) ci-dessous meritent une justification metier explicite.</p>"""

    view_all_intro = f"""
<p>Un couple groupe/objet est compte des qu'un permission set membre accorde
<em>View All</em> sur cet objet : lecture de tous les enregistrements de l'objet
en ignorant l'OWD et les regles de partage. C'est souvent legitime (reporting,
support), mais cela contourne le modele de partage, d'où le suivi.</p>
<p><em>View All</em> ne donne aucun droit d'ecriture, et se distingue de
<em>View All Fields</em>, qui leve la securite au niveau des champs. Les droits
affiches dans la matrice sont : {html_value(flags)}.</p>"""

    body = f"""
{index_back_link(path, output_dir, safe_slug(SUMMARY_TAB_LABEL), SECURITY_TAB_GROUP)}
<h1>PSet Group Summary &mdash; detail et explications</h1>
<p>Cette page detaille chacun des chiffres affiches en tete du sous-onglet
<em>PSet Group Summary</em> et explique comment ils sont obtenus.</p>
<div class='section' style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:10px 14px'>
  <strong>Principe de calcul</strong> : un Permission Set Group n'accorde aucun
  droit par lui-meme. Les droits presentes sont l'<strong>union</strong> des
  <code>objectPermissions</code> de ses permission sets membres : un droit
  apparait accorde des qu'un seul membre le porte.
  <ul>
    <li><a href='#{DETAIL_ANCHORS['groups']}'>Permission Set Groups analyses</a></li>
    <li><a href='#{DETAIL_ANCHORS['permission_sets']}'>Permission Sets membres</a></li>
    <li><a href='#{DETAIL_ANCHORS['objects']}'>Couverture des objets</a></li>
    <li><a href='#{DETAIL_ANCHORS['modify_all']}'>Couples avec Modify All</a></li>
    <li><a href='#{DETAIL_ANCHORS['view_all']}'>Couples avec View All</a></li>
    <li><a href='#{DETAIL_ANCHORS['status']}'>Statut d'un Permission Set Group</a></li>
  </ul>
</div>
{_render_groups_section(accesses)}
{_render_permission_sets_section(snapshot, accesses)}
{_render_objects_section(snapshot, accesses)}
{_render_wide_access_section(
    accesses,
    DETAIL_ANCHORS["modify_all"],
    "Couples groupe/objet avec Modify All",
    "modify_all_records",
    modify_all_intro,
)}
{_render_wide_access_section(
    accesses,
    DETAIL_ANCHORS["view_all"],
    "Couples groupe/objet avec View All",
    "view_all_records",
    view_all_intro,
)}
{_render_status_section()}
"""
    write_text(
        path,
        render_page(
            "PSet Group Summary - detail",
            body,
            path,
            assets_dir,
            include_mermaid=False,
        ),
    )
    return path
