"""Diagramme du modele de donnees au format draw.io (``.drawio``).

Le rendu suit les consignes ERD du comite DA, de facon algorithmique :
page 16:9, grille de 10 px, une couleur par sens, boite a en-tete (nom API)
et corps limite aux champs utiles, liens orthogonaux avec cardinalite,
legende compacte des seules couleurs utilisees. Pas de titre dans le
schema : il vit dans le slide.

Le decoupage en onglets vit dans :mod:`src.core.data_model_graph`.
"""

from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Sequence

from src.core.data_model_graph import (
    OVERVIEW,
    UNRELATED,
    DataModelCluster,
    DataModelLink,
    exclude_virtual,
    plan_data_model_tabs,
)
from src.core.models import ObjectInfo
from src.core.utils import safe_slug

LogCallback = Callable[[str], None]

#: Page 16:9 demandee pour l'export PNG du comite.
PAGE_WIDTH = 1280
PAGE_HEIGHT = 720
GRID = 10

#: Au-dela, la zone est scindee : la consigne limite une zone a 10 elements.
MAX_OBJECTS_PER_ZONE = 10
#: Id, FK, puis champs custom d'un objet standard. Pas tous les champs.
MAX_BODY_LINES = 6

MARGIN = 20
NODE_WIDTH = 240
NODE_GAP = 20
ZONE_GAP = 30
LABEL_HEIGHT = 20
HEADER_HEIGHT = 30
LINE_HEIGHT = 20
BODY_PADDING = 10
LEGEND_SWATCH = 20
LEGEND_GAP = 16

_DIRECT_MARKERS = ("lookup", "master", "hierarchy")

#: (cle, libelle, bordure, fond, en-tete). Le texte d'en-tete est blanc.
_PALETTE = {
    "standard": ("Standard Salesforce", "#6C8EBF", "#DAE8FC", "#3A6FC4"),
    "custom": ("Custom", "#82B366", "#D5E8D4", "#5E8F45"),
    "context": ("Contexte", "#666666", "#F5F5F5", "#8C8C8C"),
}
_LEGEND_ORDER = ("standard", "custom", "context")

_BOX_STYLE = (
    "rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;spacing=0;"
    "fontFamily=Arial;fontSize=12;strokeWidth=1;fillColor={fill};"
    "strokeColor={stroke};dashed={dashed};"
)
_EDGE_STYLE = (
    "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;"
    "html=1;fontFamily=Arial;fontSize=12;fontColor=#1A1A1A;endArrow=open;"
    "endFill=0;startArrow=none;strokeColor=#666666;strokeWidth=1;"
    "dashed={dashed};"
)
_EDGE_LABEL_STYLE = (
    "edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];"
    "fontFamily=Arial;fontSize=12;fontColor=#1A1A1A;"
)
_CAPTION_STYLE = (
    "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;"
    "fontFamily=Arial;fontSize=12;fontColor=#1A1A1A;fontStyle=1;"
)
_LEGEND_TEXT_STYLE = (
    "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;"
    "fontFamily=Arial;fontSize=12;fontColor=#1A1A1A;"
)


def _is_custom_object(obj: ObjectInfo) -> bool:
    return obj.custom or obj.api_name.endswith("__c")


def _is_direct(link: DataModelLink) -> bool:
    kind = (link.relationship_type or "").lower()
    return any(marker in kind for marker in _DIRECT_MARKERS)


def _target_cardinality(link: DataModelLink, by_name: dict[str, ObjectInfo]) -> str:
    """Cardinalite cote objet reference : 1 si le lien est obligatoire, sinon 0..1."""

    if link.is_master_detail:
        return "1"
    source = by_name.get(link.source)
    field = next(
        (
            field_info
            for field_info in (source.fields if source else [])
            if field_info.api_name == link.field_name
        ),
        None,
    )
    if field is not None and field.required:
        return "1"
    return "0..1"


def _field_lines(obj: ObjectInfo, fk_names: Sequence[str]) -> list[str]:
    """Champs utiles : Id (PK), les FK du schema, puis les champs custom d'un standard.

    Un objet standard reste bleu ; ses champs custom sont cites avec leur
    suffixe ``__c``. Le corps est tronque : le schema ne liste pas tous les
    champs de l'objet.
    """

    lines = ["Id (PK)", *[f"{name} (FK)" for name in fk_names]]
    if not _is_custom_object(obj):
        foreign_keys = set(fk_names)
        lines.extend(
            field_info.api_name
            for field_info in obj.fields
            if field_info.api_name.endswith("__c") and field_info.api_name not in foreign_keys
        )
    if len(lines) <= MAX_BODY_LINES:
        return lines
    hidden = len(lines) - (MAX_BODY_LINES - 1)
    return [*lines[: MAX_BODY_LINES - 1], f"+ {hidden} champ(s)"]


def _box_height(line_count: int) -> int:
    return HEADER_HEIGHT + BODY_PADDING + LINE_HEIGHT * line_count


def _box_value(api_name: str, lines: Sequence[str], header: str, body: str) -> str:
    rows = "<br>".join(html.escape(line) for line in lines)
    return (
        f'<div style="background-color:{header};color:#FFFFFF;font-weight:bold;'
        f'text-align:center;padding:4px 6px;"><b>{html.escape(api_name)}</b></div>'
        f'<div style="background-color:{body};color:#1A1A1A;font-weight:normal;'
        f'text-align:left;padding:4px 8px;">{rows}</div>'
    )


def _split_zones(zones: Sequence[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    """Decoupe toute zone de plus de 10 objets, sans melanger les squads."""

    split: list[tuple[str, list[str]]] = []
    for label, names in zones:
        if len(names) <= MAX_OBJECTS_PER_ZONE:
            split.append((label, names))
            continue
        chunks = [
            names[start : start + MAX_OBJECTS_PER_ZONE]
            for start in range(0, len(names), MAX_OBJECTS_PER_ZONE)
        ]
        total = len(chunks)
        for index, chunk in enumerate(chunks, start=1):
            split.append((f"{label} ({index}/{total})", chunk))
    return split


def _cell(root: ET.Element, cell_id: str, parent: str = "1", **attributes: str) -> ET.Element:
    return ET.SubElement(root, "mxCell", id=cell_id, parent=parent, **attributes)


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

        by_name = {
            obj.api_name: obj for obj in exclude_virtual(objects) if obj.api_name
        }
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
            dx="1280",
            dy="720",
            grid="1",
            gridSize=str(GRID),
            guides="1",
            tooltips="1",
            connect="1",
            arrows="1",
            fold="1",
            page="1",
            pageScale="1",
            pageWidth=str(PAGE_WIDTH),
            pageHeight=str(PAGE_HEIGHT),
            math="0",
            shadow="0",
        )
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", id="0")
        ET.SubElement(root, "mxCell", id="1", parent="0")

        positions, bottom, used = self._render_zones(root, slug, cluster, by_name)
        if cluster.kind != UNRELATED:
            self._render_links(root, slug, cluster.links, positions, by_name)
        self._render_legend(root, slug, used, bottom)
        return diagram

    def _render_zones(
        self,
        root: ET.Element,
        slug: str,
        cluster: DataModelCluster,
        by_name: dict[str, ObjectInfo],
    ) -> tuple[dict[str, str], int, set[str]]:
        """Place chaque squad, scindee au dela de 10 objets. Renvoie les boites."""

        positions: dict[str, str] = {}
        used: set[str] = set()
        foreign_keys = _foreign_keys(cluster)
        y = MARGIN
        columns = max(1, (PAGE_WIDTH - 2 * MARGIN + NODE_GAP) // (NODE_WIDTH + NODE_GAP))

        for zone_index, (label, names) in enumerate(_split_zones(cluster.zones)):
            if not names:
                continue
            caption = _cell(
                root,
                f"{slug}-zone-{zone_index}",
                style=_CAPTION_STYLE,
                value=html.escape(label),
                vertex="1",
            )
            _geometry(caption, MARGIN, y, PAGE_WIDTH - 2 * MARGIN, LABEL_HEIGHT)
            y += LABEL_HEIGHT + GRID

            placed = [name for name in names if name in by_name]
            if not placed:
                continue
            heights = [
                _box_height(len(_field_lines(by_name[name], foreign_keys.get(name, []))))
                for name in placed
            ]
            row_height = max(heights) + NODE_GAP
            for position, name in enumerate(placed):
                column, row = position % columns, position // columns
                obj = by_name[name]
                kind = _object_kind(name, obj, cluster)
                used.add(kind)
                _label, stroke, fill, header = _PALETTE[kind]
                lines = _field_lines(obj, foreign_keys.get(name, []))
                node_id = f"{slug}-{safe_slug(name)}"
                box = _cell(
                    root,
                    node_id,
                    style=_BOX_STYLE.format(
                        fill=fill,
                        stroke=stroke,
                        dashed="1" if kind == "context" else "0",
                    ),
                    value=_box_value(name, lines, header, fill),
                    vertex="1",
                )
                _geometry(
                    box,
                    MARGIN + column * (NODE_WIDTH + NODE_GAP),
                    y + row * row_height,
                    NODE_WIDTH,
                    _box_height(len(lines)),
                )
                positions[name] = node_id

            rows = -(-len(placed) // columns)
            y += rows * row_height + ZONE_GAP

        return positions, y, used

    def _render_links(
        self,
        root: ET.Element,
        slug: str,
        links: Sequence[DataModelLink],
        positions: dict[str, str],
        by_name: dict[str, ObjectInfo],
    ) -> None:
        for index, link in enumerate(links):
            source = positions.get(link.source)
            target = positions.get(link.target)
            if source is None or target is None:
                continue
            edge_id = f"{slug}-e{index}"
            edge = _cell(
                root,
                edge_id,
                style=_EDGE_STYLE.format(dashed="0" if _is_direct(link) else "1"),
                value=html.escape(link.field_name),
                edge="1",
                source=source,
                target=target,
            )
            ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})
            self._cardinality(
                root,
                f"{edge_id}-source",
                edge_id,
                "0..*",
                "-0.8",
            )
            self._cardinality(
                root,
                f"{edge_id}-target",
                edge_id,
                _target_cardinality(link, by_name),
                "0.8",
            )

    def _cardinality(
        self,
        root: ET.Element,
        cell_id: str,
        edge_id: str,
        value: str,
        relative_x: str,
    ) -> None:
        label = _cell(
            root,
            cell_id,
            parent=edge_id,
            style=_EDGE_LABEL_STYLE,
            value=value,
            vertex="1",
            connectable="0",
        )
        geometry = ET.SubElement(
            label,
            "mxGeometry",
            x=relative_x,
            y="0",
            relative="1",
            **{"as": "geometry"},
        )
        ET.SubElement(geometry, "mxPoint", **{"as": "offset"})

    def _render_legend(
        self,
        root: ET.Element,
        slug: str,
        used: set[str],
        top: int,
    ) -> None:
        """Legende compacte, limitee aux couleurs reellement presentes."""

        x = MARGIN
        y = top
        for key in _LEGEND_ORDER:
            if key not in used:
                continue
            label, stroke, fill, _header = _PALETTE[key]
            swatch = _cell(
                root,
                f"{slug}-legend-{key}",
                style=_BOX_STYLE.format(
                    fill=fill,
                    stroke=stroke,
                    dashed="1" if key == "context" else "0",
                ),
                value="",
                vertex="1",
            )
            _geometry(swatch, x, y, LEGEND_SWATCH, LEGEND_SWATCH)
            caption = _cell(
                root,
                f"{slug}-legend-{key}-label",
                style=_LEGEND_TEXT_STYLE,
                value=label,
                vertex="1",
            )
            _geometry(caption, x + LEGEND_SWATCH + GRID, y, 180, LEGEND_SWATCH)
            x += LEGEND_SWATCH + GRID + 180 + LEGEND_GAP


def _foreign_keys(cluster: DataModelCluster) -> dict[str, list[str]]:
    """Champs de relation portes par chaque objet de l'onglet, sans doublon."""

    keys: dict[str, list[str]] = {}
    for link in cluster.links:
        names = keys.setdefault(link.source, [])
        if link.field_name not in names:
            names.append(link.field_name)
    return keys


def _object_kind(name: str, obj: ObjectInfo, cluster: DataModelCluster) -> str:
    """Sens de la couleur. Un hub n'est contexte que hors de la vue d'ensemble.

    Sur un onglet de domaine il est hors du sujet, donc gris pointille.
    Dans la vue d'ensemble il fait partie du perimetre et garde sa couleur
    d'objet standard ou custom.
    """

    if name in cluster.hub_names and cluster.kind != OVERVIEW:
        return "context"
    if _is_custom_object(obj):
        return "custom"
    return "standard"
