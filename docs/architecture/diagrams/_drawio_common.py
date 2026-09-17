"""Shared reading of the .drawio sources in this folder.

Covers only the style vocabulary these six diagrams use. Both renderers
(``_render_png.py`` and ``_render_svg.py``) build on this so the two outputs
stay identical in layout.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from PIL import ImageFont

FONT_REGULAR = r"C:\Windows\Fonts\arial.ttf"
FONT_BOLD = r"C:\Windows\Fonts\arialbd.ttf"
FONT_ITALIC = r"C:\Windows\Fonts\ariali.ttf"
_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}

LINE_SPACING = 1.28
LABEL_PAD = 6.0
ARROW = 7.0


def font_for(size: float, bold: bool = False, italic: bool = False, scale: float = 1.0):
    path = FONT_BOLD if bold else (FONT_ITALIC if italic else FONT_REGULAR)
    key = (path, max(int(round(size * scale)), 7))
    if key not in _FONT_CACHE:
        try:
            _FONT_CACHE[key] = ImageFont.truetype(path, key[1])
        except OSError:
            _FONT_CACHE[key] = ImageFont.load_default()
    return _FONT_CACHE[key]


def parse_style(style: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (style or "").split(";"):
        if not part:
            continue
        key, _, value = part.partition("=")
        out[key.strip()] = value.strip()
    return out


def colour(value: str | None, default: str | None) -> str | None:
    if not value or value in ("none", "default"):
        return default
    return value if re.fullmatch(r"#[0-9A-Fa-f]{6}", value or "") else default


def label_text(value: str | None) -> str:
    """draw.io label (HTML) -> plain text with real newlines."""
    text = re.sub(r"<br\s*/?>", "\n", value or "")
    text = re.sub(r"<[^>]+>", "", text)
    for entity, char in (
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", '"'),
        ("&#39;", "'"),
        ("&amp;", "&"),
    ):
        text = text.replace(entity, char)
    return text


def wrap(text: str, font, max_width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for word in paragraph.split(" "):
            candidate = f"{current} {word}".strip()
            if font.getlength(candidate) <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


@dataclass
class Shape:
    id: str
    x: float
    y: float
    w: float
    h: float
    text: str
    style: dict[str, str] = field(default_factory=dict)

    @property
    def kind(self) -> str:
        if "text" in self.style and "shape" not in self.style:
            return "text"
        if "ellipse" in self.style:
            return "ellipse"
        if "rhombus" in self.style:
            return "rhombus"
        shape = self.style.get("shape", "")
        if shape.startswith("cylinder"):
            return "cylinder"
        if shape == "note":
            return "note"
        return "rect"

    @property
    def center(self) -> tuple[float, float]:
        return self.x + self.w / 2, self.y + self.h / 2

    def border_toward(self, target: tuple[float, float]):
        """Exit point on the shape border facing *target*, plus its direction."""
        cx, cy = self.center
        dx, dy = target[0] - cx, target[1] - cy
        if abs(dx) * self.h > abs(dy) * self.w:
            return (self.x + self.w if dx > 0 else self.x, cy), (1 if dx > 0 else -1, 0)
        return (cx, self.y + self.h if dy > 0 else self.y), (0, 1 if dy > 0 else -1)


@dataclass
class Edge:
    source: str
    target: str
    text: str
    style: dict[str, str] = field(default_factory=dict)


@dataclass
class Diagram:
    name: str
    width: float
    height: float
    shapes: list[Shape]
    edges: list[Edge]

    def shape(self, shape_id: str | None) -> Shape | None:
        return next((s for s in self.shapes if s.id == shape_id), None)


def load(path: str) -> Diagram:
    root = ET.parse(path).getroot()
    model = root.find("diagram/mxGraphModel")
    page = root.find("diagram")
    shapes: list[Shape] = []
    edges: list[Edge] = []

    for cell in root.iter("mxCell"):
        geometry = cell.find("mxGeometry")
        style = parse_style(cell.get("style"))
        if cell.get("vertex") == "1" and geometry is not None:
            try:
                w = float(geometry.get("width") or 0)
                h = float(geometry.get("height") or 0)
            except ValueError:
                continue
            if not w or not h:
                continue
            shapes.append(
                Shape(
                    id=cell.get("id") or "",
                    x=float(geometry.get("x") or 0),
                    y=float(geometry.get("y") or 0),
                    w=w,
                    h=h,
                    text=label_text(cell.get("value")),
                    style=style,
                )
            )
        elif cell.get("edge") == "1" and cell.get("source") and cell.get("target"):
            edges.append(
                Edge(
                    source=cell.get("source") or "",
                    target=cell.get("target") or "",
                    text=label_text(cell.get("value")),
                    style=style,
                )
            )

    return Diagram(
        name=page.get("name") if page is not None else "",
        width=float(model.get("pageWidth", 1200)) if model is not None else 1200,
        height=float(model.get("pageHeight", 900)) if model is not None else 900,
        shapes=shapes,
        edges=edges,
    )


def label_layout(shape: Shape, scale: float = 1.0):
    """Yield (x, y, line, font) for each wrapped line of a shape label."""
    if not shape.text:
        return
    style = shape.style
    size = float(style.get("fontSize", 12))
    weight = style.get("fontStyle", "0")
    font = font_for(size, weight == "1", weight == "2", scale)
    pad = LABEL_PAD * scale
    spacing_left = float(style.get("spacingLeft", 0)) * scale
    width = shape.w * scale
    lines = wrap(shape.text, font, width - 2 * pad - spacing_left)
    line_h = (font.getbbox("Ag")[3] or size * scale) * LINE_SPACING
    total = line_h * len(lines)

    if style.get("verticalAlign") == "top":
        top = shape.y * scale + float(style.get("spacingTop", 2)) * scale
    else:
        top = shape.y * scale + (shape.h * scale - total) / 2

    left_aligned = style.get("align") == "left"
    for index, line in enumerate(lines):
        y = top + index * line_h
        if left_aligned:
            x = shape.x * scale + pad + spacing_left
        else:
            x = shape.x * scale + (width - font.getlength(line)) / 2
        yield x, y, line, font


def route(source: Shape, target: Shape, scale: float = 1.0):
    """Orthogonal polyline between two shape borders, plus the arrow direction."""
    start, _ = source.border_toward(target.center)
    end, direction = target.border_toward(source.center)
    start = (start[0] * scale, start[1] * scale)
    end = (end[0] * scale, end[1] * scale)
    back = (end[0] - direction[0] * ARROW * scale, end[1] - direction[1] * ARROW * scale)

    if abs(start[0] - back[0]) < 2 or abs(start[1] - back[1]) < 2:
        points = [start, back]
    elif direction[0]:
        mid_x = start[0] + (back[0] - start[0]) / 2
        points = [start, (mid_x, start[1]), (mid_x, back[1]), back]
    else:
        mid_y = start[1] + (back[1] - start[1]) / 2
        points = [start, (start[0], mid_y), (back[0], mid_y), back]

    return points, direction
