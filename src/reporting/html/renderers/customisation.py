"""Render the dedicated ``customisation.html`` page.

Detailed view backing the *Empreinte data model* card on the index. The
page exposes the same custom-vs-standard breakdown as the card, and adds
a per-object table that surfaces *where* customisation accumulates so a
reviewer can quickly spot the heavy hitters (objects with many custom
fields, custom objects with no description, etc.).

When the Data Dictionary screen holds an object selection, a *Ce qui est
utilise* section confronts that footprint with the objects the reviewer
marked as actually used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.core.customization_metrics import (
    DataModelCustomisationStats,
    SelectedUsageStats,
    UsageBucket,
    UsageTable,
)
from src.core.models import MetadataSnapshot
from src.core.utils import html_value, write_text

from src.reporting.html.page_shell import (
    href_relative,
    index_back_link,
    render_page,
)


LogCallback = Callable[[str], None]


def write_customisation_page(
    snapshot: MetadataSnapshot,
    stats: DataModelCustomisationStats | None,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
    usage_stats: SelectedUsageStats | None = None,
) -> Path:
    """Write ``customisation.html`` and return its path.

    The page is always generated so the index card can link to it
    safely; if the snapshot has no objects we still display a clear
    "nothing to show" placeholder. ``usage_stats`` is only provided when
    the Data Dictionary screen holds a selection.
    """

    path = output_dir / "customisation.html"
    write_text(
        path,
        _render_page(snapshot, stats, path, output_dir, assets_dir, usage_stats),
    )
    log(f"Page Empreinte data model generee: {path}")
    return path


def _render_overview_cards(stats: DataModelCustomisationStats | None) -> str:
    if stats is None or stats.total_objects + stats.total_fields == 0:
        return (
            '<div class="cards smallcards">'
            '<div class="card"><span>Empreinte data model</span>'
            '<span class="value">N/A</span></div>'
            "</div>"
        )
    return (
        '<div class="cards smallcards">'
        '<div class="card adopt-card adopt-card--adapt">'
        '<span>Composants custom</span>'
        f'<span class="value">{stats.custom_objects + stats.custom_fields}</span>'
        f'<span class="adopt-percent">{stats.percent_custom_global:.1f} %</span>'
        "</div>"
        '<div class="card adopt-card adopt-card--adopt">'
        '<span>Composants standard</span>'
        f'<span class="value">{stats.standard_objects + stats.standard_fields}</span>'
        f'<span class="adopt-percent">{stats.percent_standard_global:.1f} %</span>'
        "</div>"
        '<div class="card"><span>Objets custom / total</span>'
        f'<span class="value">{stats.custom_objects} / {stats.total_objects}</span>'
        f'<span class="adopt-percent">{stats.percent_custom_objects:.1f} %</span>'
        "</div>"
        '<div class="card"><span>Champs custom / total</span>'
        f'<span class="value">{stats.custom_fields} / {stats.total_fields}</span>'
        f'<span class="adopt-percent">{stats.percent_custom_fields:.1f} %</span>'
        "</div>"
        "</div>"
    )


def _render_usage_row(
    table: UsageTable, bucket: UsageBucket, emphasis: bool = False
) -> str:
    percent = table.percent(bucket)
    ratio = "—" if percent is None else f"{percent:.1f} %"
    cells = [html_value(bucket.label), str(bucket.used), str(bucket.total), ratio]
    if emphasis:
        cells = [f"<strong>{cell}</strong>" for cell in cells]
    return "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"


def _render_usage_table(table: UsageTable) -> str:
    rows = [_render_usage_row(table, bucket) for bucket in table.buckets]
    rows.append(_render_usage_row(table, table.total, emphasis=True))
    return (
        f"<h3>{html_value(table.caption)}</h3>"
        "<table><thead><tr>"
        "<th>Categorie</th>"
        "<th>Utilises</th>"
        "<th>Presents dans le snapshot</th>"
        f"<th>{html_value(table.percent_caption)}</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _render_usage_section(stats: SelectedUsageStats | None) -> str:
    """Render the *Ce qui est utilise* section, or nothing without selection."""

    if stats is None or stats.objects is None or stats.fields is None:
        return ""
    return (
        "<h2>Ce qui est utilise</h2>"
        "<p>Cette section ne regarde que les objets coches dans l'ecran de"
        f" creation du Data Dictionnary : ces {stats.matched_count} objets sont"
        " ceux consideres comme reellement utilises. La colonne <em>Utilises</em>"
        " compte ce qui appartient a ce perimetre, la colonne <em>Presents dans"
        " le snapshot</em> rappelle ce que contient l'org entiere. Les"
        " pourcentages repartissent l'usage : cote objets, ils disent quelle"
        " part des objets utilises est custom plutot que standard ; cote champs,"
        " ils ne portent que sur les objets standard, pour mesurer jusqu'ou"
        " ceux-ci ont ete etendus. Les custom metadata (<code>__mdt</code>)"
        " portent du parametrage plutot que des donnees metier : ils sont"
        " affiches pour information mais exclus des pourcentages et des"
        " totaux.</p>"
        + _render_usage_table(stats.objects)
        + _render_usage_table(stats.fields)
    )


def _render_object_table(snapshot: MetadataSnapshot) -> str:
    if not snapshot.objects:
        return "<p class='empty'>Aucun objet detecte dans le snapshot.</p>"

    rows: list[str] = []
    objects_sorted = sorted(
        snapshot.objects,
        key=lambda obj: (
            not obj.custom,
            -sum(1 for f in obj.fields if f.custom),
            obj.api_name.lower(),
        ),
    )
    for obj in objects_sorted:
        total_fields = len(obj.fields)
        custom_fields = sum(1 for f in obj.fields if f.custom)
        ratio = (custom_fields / total_fields * 100.0) if total_fields else 0.0
        kind = "Custom" if obj.custom else "Standard"
        rows.append(
            "<tr>"
            f"<td>{html_value(obj.api_name)}</td>"
            f"<td>{html_value(obj.label)}</td>"
            f"<td>{kind}</td>"
            f"<td>{total_fields}</td>"
            f"<td>{custom_fields}</td>"
            f"<td>{ratio:.1f} %</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>API Name</th>"
        "<th>Label</th>"
        "<th>Type</th>"
        "<th>Total champs</th>"
        "<th>Champs custom</th>"
        "<th>% custom local</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _render_page(
    snapshot: MetadataSnapshot,
    stats: DataModelCustomisationStats | None,
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    usage_stats: SelectedUsageStats | None = None,
) -> str:
    back_link = index_back_link(current_path, output_dir, "empreinte-data-model")
    methodology_href = href_relative(current_path, output_dir / "methodology.html")
    methodology_link = f'<div class="topnav" style="float: right;"><a href="{methodology_href}">Comprendre le calcul</a></div>'
    back_link = f'<div style="display: flex; justify-content: space-between; align-items: center;">{back_link}{methodology_link}</div>'

    overview = _render_overview_cards(stats)
    usage = _render_usage_section(usage_stats)
    table = _render_object_table(snapshot)

    body = f"""
{back_link}
<h1>Empreinte data model</h1>
<p>Cette page mesure la part du modele de donnees qui releve de la
personnalisation (objets et champs en <code>__c</code>) par rapport au
standard Salesforce present dans le snapshot. Chaque ligne du tableau
detaille la densite custom locale de l'objet : un faible nombre total
de champs combine a 100 % custom local indique une extension legere ;
un objet standard avec beaucoup de champs custom revele au contraire
une adaptation lourde.</p>
{overview}
{usage}
<h2>Detail par objet</h2>
{table}
"""
    return render_page(
        "Empreinte data model",
        body,
        current_path,
        assets_dir,
        include_mermaid=False,
    )
