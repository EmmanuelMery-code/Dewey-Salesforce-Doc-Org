"""Diagramme du modele de donnees au format draw.io (``.drawio``).

Un fichier ``.drawio`` non compresse est du XML mxGraph : il suffit de
l'ecrire, sans dependance. Chaque onglet du fichier est un ``<diagram>``, ce
qui permet de repartir le modele en vues lisibles plutot qu'en une planche
unique : vue d'ensemble, un onglet par domaine, puis les objets sans relation.

Le decoupage lui-meme vit dans :mod:`src.core.data_model_graph`, partage avec
les tests, de sorte que ce module ne s'occupe que du rendu et du placement.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Sequence

from src.core.data_model_graph import (
    DOMAIN,
    SATELLITE,
    UNRELATED,
    DataModelCluster,
    DataModelLink,
    plan_data_model_tabs,
)
from src.core.models import ObjectInfo
from src.core.utils import safe_slug

LogCallback = Callable[[str], None]

# --- Styles mxGraph ---------------------------------------------------------

ZONE_STYLE = (
    "rounded=1;arcSize=6;whiteSpace=wrap;html=1;fillColor={fill};dashed=1;"
    "dashPattern=4 4;strokeColor={stroke};verticalAlign=top;align=left;"
    "spacingLeft=8;spacingTop=6;fontStyle=1;fontSize=13;"
)
NODE_STYLE = (
    "rounded=1;arcSize=10;whiteSpace=wrap;html=1;fillColor={fill};"
    "strokeColor={stroke};fontColor=#FFFFFF;fontStyle=1;align=center;"
    "verticalAlign=middle;shadow=1;strokeWidth={width};fontSize=12;"
)
EDGE_STYLE = (
    "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;"
    "html=1;strokeColor={stroke};strokeWidth={width};dashed={dashed};"
    "fontSize=9;fontColor=#6B6B6B;startArrow=ERmany;startFill=0;"
    "endArrow=ERone;endFill=0;"
)
TITLE_STYLE = "text;html=1;strokeColor=none;fillColor=none;fontSize=22;fontStyle=1;"
SUBTITLE_STYLE = (
    "text;html=1;strokeColor=none;fillColor=none;fontSize=12;fontColor=#5A6470;"
    "align=left;verticalAlign=top;"
)

#: Remplissage et bordure d'une boite selon la nature de l'objet.
STANDARD_COLORS = ("#1F3864", "#0D1B33")
CUSTOM_COLORS = ("#B5651D", "#7A4514")
#: Bordure doree des hubs, qui signale un objet duplique sur plusieurs onglets.
HUB_STROKE = "#E8A33D"

#: Palette des cadres de zone, parcourue dans l'ordre puis rebouclee.
ZONE_COLORS = (
    ("#dae8fc", "#6c8ebf"),
    ("#ffe6cc", "#d79b00"),
    ("#d5e8d4", "#82b366"),
    ("#fff2cc", "#d6b656"),
    ("#f8cecc", "#b85450"),
    ("#d0cee2", "#56517e"),
    ("#bac8d3", "#23445d"),
)
#: Les objets partages sont toujours encadres de la meme couleur neutre.
SHARED_ZONE_COLORS = ("#f5f5f5", "#666666")
SHARED_ZONE_LABEL = "Objets partages"

# --- Geometrie --------------------------------------------------------------

NODE_WIDTH = 300
NODE_HEIGHT = 60
NODE_GAP = 18
ZONE_PADDING_X = 25
ZONE_HEADER = 34
ZONE_PADDING_BOTTOM = 22
ZONE_GAP = 44
CANVAS_LEFT = 40
CANVAS_TOP = 130
#: Au-dela, une zone se replie sur plusieurs colonnes plutot que de s'etirer
#: sur une hauteur que personne ne peut parcourir.
MAX_ROWS_PER_COLUMN = 14


def _node_value(obj: ObjectInfo, is_hub: bool) -> str:
    """Libelle HTML d'une boite : nom API, puis nature et role en petit."""

    nature = "Custom" if obj.custom else "Standard SF"
    if is_hub:
        nature = f"{nature} - partage"
    return (
        f"<b>{obj.api_name}</b><br>"
        f'<i style="font-size:10px;opacity:0.85">{nature}</i>'
    )


def _zone_colors(index: int, label: str) -> tuple[str, str]:
    if label == SHARED_ZONE_LABEL:
        return SHARED_ZONE_COLORS
    return ZONE_COLORS[index % len(ZONE_COLORS)]


def _cell(root: ET.Element, cell_id: str, **attributes: str) -> ET.Element:
    return ET.SubElement(root, "mxCell", id=cell_id, parent="1", **attributes)


def _geometry(cell: ET.Element, x: int, y: int, width: int, height: int) -> None:
    ET.SubElement(
        cell,
        "mxGeometry",
        x=str(x),
        y=str(y),
        width=str(width),
        height=str(height),
        **{"as": "geometry"},
    )


def _column_count(size: int) -> int:
    return max(1, -(-size // MAX_ROWS_PER_COLUMN))


def _zone_size(size: int) -> tuple[int, int]:
    """Largeur et hauteur d'un cadre de zone contenant ``size`` boites."""

    columns = _column_count(size)
    rows = -(-size // columns)
    width = ZONE_PADDING_X * 2 + columns * NODE_WIDTH + (columns - 1) * NODE_GAP
    height = ZONE_HEADER + rows * NODE_HEIGHT + (rows - 1) * NODE_GAP + ZONE_PADDING_BOTTOM
    return width, height


class DrawioDiagramWriter:
    """Ecrit les diagrammes ``.drawio`` deduits du snapshot analyse."""

    def __init__(self, log_callback: LogCallback | None = None) -> None:
        self.log: LogCallback = log_callback or (lambda message: None)

    def write_data_model_diagram(
        self,
        objects: Sequence[ObjectInfo],
        output_path: str | Path,
    ) -> Path | None:
        """Ecrit le diagramme du modele de donnees des objets fournis.

        Renvoie ``None`` quand le perimetre est vide : mieux vaut ne pas
        laisser un fichier trompeur qu'un diagramme sans aucune boite.
        """

        output = Path(output_path)
        clusters = plan_data_model_tabs(objects)
        if not clusters:
            self.log(
                "Diagramme du modele de donnees : aucun objet a representer, "
                "generation ignoree."
            )
            return None

        by_name = {obj.api_name: obj for obj in objects if obj.api_name}
        mxfile = ET.Element("mxfile", host="Dewey")
        for index, cluster in enumerate(clusters):
            mxfile.append(self._render_tab(index, cluster, by_name))

        tree = ET.ElementTree(mxfile)
        ET.indent(tree, space="  ")
        output.parent.mkdir(parents=True, exist_ok=True)
        tree.write(output, encoding="utf-8", xml_declaration=True)

        tabs = ", ".join(cluster.label for cluster in clusters)
        self.log(
            f"Diagramme du modele de donnees genere ({len(clusters)} onglet(s) : "
            f"{tabs}): {output}"
        )
        return output

    def _render_tab(
        self,
        index: int,
        cluster: DataModelCluster,
        by_name: dict[str, ObjectInfo],
    ) -> ET.Element:
        slug = safe_slug(cluster.label)
        diagram = ET.Element("diagram", name=cluster.label, id=f"dewey-{index}-{slug}")
        model = ET.SubElement(
            diagram,
            "mxGraphModel",
            dx="1600",
            dy="1000",
            grid="1",
            gridSize="10",
            guides="1",
            tooltips="1",
            connect="1",
            arrows="1",
            fold="1",
            page="1",
            pageScale="1",
            pageWidth="1900",
            pageHeight="1500",
            math="0",
            shadow="0",
        )
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", id="0")
        ET.SubElement(root, "mxCell", id="1", parent="0")

        self._render_header(root, slug, cluster)
        positions = self._render_zones(root, slug, cluster, by_name)
        if cluster.kind != UNRELATED:
            self._render_links(root, slug, cluster.links, positions)
        return diagram

    def _render_header(self, root: ET.Element, slug: str, cluster: DataModelCluster) -> None:
        title = _cell(root, f"{slug}-title", style=TITLE_STYLE, value=cluster.label, vertex="1")
        _geometry(title, CANVAS_LEFT, 30, 900, 34)

        counts = f"{len(cluster.object_names)} objet(s)"
        if cluster.kind != UNRELATED:
            counts += f", {len(cluster.links)} relation(s)"
        hint = {
            UNRELATED: "Objets selectionnes qui ne portent aucune relation vers un "
            "autre objet du perimetre.",
            DOMAIN: "Objets lies entre eux. Les objets partages sont references "
            "par plusieurs domaines et reapparaissent sur leurs onglets.",
            SATELLITE: "Objets accroches a un seul objet partage : trop isoles pour "
            "meriter leur propre domaine, ils sont regroupes ici.",
        }.get(cluster.kind, "Tous les objets selectionnes portant au moins une relation.")
        legend = (
            "Boite bleue = objet standard, orange = custom, bordure doree = objet "
            "partage. Trait plein = Master-Detail, pointille = Lookup, le libelle "
            "portant le champ qui porte la relation."
        )
        subtitle = _cell(
            root,
            f"{slug}-subtitle",
            style=SUBTITLE_STYLE,
            value=f"{counts}. {hint}<br>{legend}",
            vertex="1",
        )
        _geometry(subtitle, CANVAS_LEFT, 68, 1200, 50)

    def _render_zones(
        self,
        root: ET.Element,
        slug: str,
        cluster: DataModelCluster,
        by_name: dict[str, ObjectInfo],
    ) -> dict[str, str]:
        """Dessine un cadre par Squad, puis ses boites. Renvoie l'id des boites."""

        positions: dict[str, str] = {}
        x = CANVAS_LEFT
        for zone_index, (label, names) in enumerate(cluster.zones):
            if not names:
                continue
            fill, stroke = _zone_colors(zone_index, label)
            width, height = _zone_size(len(names))
            frame = _cell(
                root,
                f"{slug}-zone-{zone_index}",
                style=ZONE_STYLE.format(fill=fill, stroke=stroke),
                value=f"{label} ({len(names)})",
                vertex="1",
            )
            _geometry(frame, x, CANVAS_TOP, width, height)

            columns = _column_count(len(names))
            rows = -(-len(names) // columns)
            for position, name in enumerate(names):
                column, row = divmod(position, rows)
                obj = by_name.get(name)
                if obj is None:
                    continue
                is_hub = name in cluster.hub_names
                fill_color, stroke_color = CUSTOM_COLORS if obj.custom else STANDARD_COLORS
                node_id = f"{slug}-{safe_slug(name)}"
                box = _cell(
                    root,
                    node_id,
                    style=NODE_STYLE.format(
                        fill=fill_color,
                        stroke=HUB_STROKE if is_hub else stroke_color,
                        width="3" if is_hub else "1",
                    ),
                    value=_node_value(obj, is_hub),
                    vertex="1",
                )
                _geometry(
                    box,
                    x + ZONE_PADDING_X + column * (NODE_WIDTH + NODE_GAP),
                    CANVAS_TOP + ZONE_HEADER + row * (NODE_HEIGHT + NODE_GAP),
                    NODE_WIDTH,
                    NODE_HEIGHT,
                )
                positions[name] = node_id

            x += width + ZONE_GAP
        return positions

    def _render_links(
        self,
        root: ET.Element,
        slug: str,
        links: Sequence[DataModelLink],
        positions: dict[str, str],
    ) -> None:
        for index, link in enumerate(links):
            source = positions.get(link.source)
            target = positions.get(link.target)
            if source is None or target is None:
                continue
            style = EDGE_STYLE.format(
                stroke="#B85450" if link.is_master_detail else "#8C8C8C",
                width="2.5" if link.is_master_detail else "1.5",
                dashed="0" if link.is_master_detail else "1",
            )
            edge = _cell(
                root,
                f"{slug}-e{index}",
                style=style,
                value=link.field_name,
                edge="1",
                source=source,
                target=target,
            )
            ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})
