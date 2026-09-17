"""Render the .drawio sources in this folder to SVG.

SVG stays crisp at any zoom, weighs a fraction of the PNG, and GitHub renders
it inline in Markdown.

    python _render_svg.py
"""
from __future__ import annotations

import glob
import os

from _drawio_common import ARROW, Diagram, Shape, label_layout, load, route

MARGIN = 12.0


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def stroke_of(shape: Shape) -> str:
    from _drawio_common import colour

    return colour(shape.style.get("strokeColor"), "#666666") or "#666666"


def fill_of(shape: Shape) -> str:
    from _drawio_common import colour

    return colour(shape.style.get("fillColor"), "#ffffff") or "#ffffff"


def shape_svg(shape: Shape) -> str:
    x, y, w, h = shape.x + MARGIN, shape.y + MARGIN, shape.w, shape.h
    fill, stroke = fill_of(shape), stroke_of(shape)
    dash = ' stroke-dasharray="7 4"' if shape.style.get("dashed") == "1" else ""
    common = f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"{dash}'
    kind = shape.kind

    if kind == "text":
        return ""
    if kind == "ellipse":
        return (
            f'<ellipse cx="{x + w / 2:.1f}" cy="{y + h / 2:.1f}" '
            f'rx="{w / 2:.1f}" ry="{h / 2:.1f}" {common}/>'
        )
    if kind == "rhombus":
        cx, cy = x + w / 2, y + h / 2
        pts = f"{cx:.1f},{y:.1f} {x + w:.1f},{cy:.1f} {cx:.1f},{y + h:.1f} {x:.1f},{cy:.1f}"
        return f'<polygon points="{pts}" {common}/>'
    if kind == "cylinder":
        lid = min(h * 0.18, 16.0)
        return (
            f'<path d="M {x:.1f} {y + lid / 2:.1f} '
            f"A {w / 2:.1f} {lid / 2:.1f} 0 0 1 {x + w:.1f} {y + lid / 2:.1f} "
            f"L {x + w:.1f} {y + h - lid / 2:.1f} "
            f"A {w / 2:.1f} {lid / 2:.1f} 0 0 1 {x:.1f} {y + h - lid / 2:.1f} "
            f'Z" {common}/>'
            f'<path d="M {x:.1f} {y + lid / 2:.1f} '
            f"A {w / 2:.1f} {lid / 2:.1f} 0 0 0 {x + w:.1f} {y + lid / 2:.1f}\" "
            f'fill="none" stroke="{stroke}" stroke-width="1.6"/>'
        )
    if kind == "note":
        fold = 14.0
        return (
            f'<path d="M {x:.1f} {y:.1f} L {x + w - fold:.1f} {y:.1f} '
            f"L {x + w:.1f} {y + fold:.1f} L {x + w:.1f} {y + h:.1f} "
            f'L {x:.1f} {y + h:.1f} Z" {common}/>'
            f'<path d="M {x + w - fold:.1f} {y:.1f} L {x + w - fold:.1f} {y + fold:.1f} '
            f'L {x + w:.1f} {y + fold:.1f}" fill="none" stroke="{stroke}" stroke-width="1.6"/>'
        )
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" {common}/>'


def label_svg(shape: Shape) -> str:
    from _drawio_common import colour

    out: list[str] = []
    style = shape.style
    size = float(style.get("fontSize", 12))
    weight = "bold" if style.get("fontStyle") == "1" else "normal"
    slant = "italic" if style.get("fontStyle") == "2" else "normal"
    fill = colour(style.get("fontColor"), "#000000") or "#000000"

    for x, y, line, font in label_layout(shape):
        if not line:
            continue
        baseline = y + (font.getbbox("Ag")[3] or size) * 0.82
        out.append(
            f'<text x="{x + MARGIN:.1f}" y="{baseline + MARGIN:.1f}" '
            f'font-family="Arial, Helvetica, sans-serif" font-size="{size:.0f}" '
            f'font-weight="{weight}" font-style="{slant}" fill="{fill}">{esc(line)}</text>'
        )
    return "".join(out)


def edge_svg(diagram: Diagram, edge) -> str:
    from _drawio_common import colour, font_for

    source, target = diagram.shape(edge.source), diagram.shape(edge.target)
    if not source or not target:
        return ""
    points, direction = route(source, target)
    stroke = colour(edge.style.get("strokeColor"), "#666666") or "#666666"
    dash = ' stroke-dasharray="6 4"' if edge.style.get("dashed") == "1" else ""
    path = " ".join(f"{px + MARGIN:.1f},{py + MARGIN:.1f}" for px, py in points)
    out = [
        f'<polyline points="{path}" fill="none" stroke="{stroke}" '
        f'stroke-width="1.6"{dash}/>'
    ]

    tip_x, tip_y = points[-1]
    dx, dy = direction
    if dx:
        pts = (
            f"{tip_x + dx * ARROW + MARGIN:.1f},{tip_y + MARGIN:.1f} "
            f"{tip_x + MARGIN:.1f},{tip_y - ARROW * 0.55 + MARGIN:.1f} "
            f"{tip_x + MARGIN:.1f},{tip_y + ARROW * 0.55 + MARGIN:.1f}"
        )
    else:
        pts = (
            f"{tip_x + MARGIN:.1f},{tip_y + dy * ARROW + MARGIN:.1f} "
            f"{tip_x - ARROW * 0.55 + MARGIN:.1f},{tip_y + MARGIN:.1f} "
            f"{tip_x + ARROW * 0.55 + MARGIN:.1f},{tip_y + MARGIN:.1f}"
        )
    out.append(f'<polygon points="{pts}" fill="{stroke}" stroke="none"/>')

    if edge.text:
        font = font_for(9)
        anchor = points[len(points) // 2]
        for index, line in enumerate(edge.text.split("\n")):
            width = font.getlength(line)
            cx = anchor[0] + MARGIN
            cy = anchor[1] + MARGIN + index * 11
            out.append(
                f'<rect x="{cx - width / 2 - 3:.1f}" y="{cy - 7:.1f}" '
                f'width="{width + 6:.1f}" height="12" fill="#ffffff" stroke="none"/>'
                f'<text x="{cx:.1f}" y="{cy + 2:.1f}" text-anchor="middle" '
                f'font-family="Arial, Helvetica, sans-serif" font-size="9" '
                f'fill="{stroke}">{esc(line)}</text>'
            )
    return "".join(out)


def render(path: str) -> str:
    diagram = load(path)
    width = diagram.width + 2 * MARGIN
    height = diagram.height + 2 * MARGIN

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" '
        f'height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">',
        f'<title>{esc(diagram.name)}</title>',
        f'<rect width="{width:.0f}" height="{height:.0f}" fill="#ffffff"/>',
    ]
    parts.extend(shape_svg(s) for s in diagram.shapes)
    parts.extend(edge_svg(diagram, e) for e in diagram.edges)
    parts.extend(label_svg(s) for s in diagram.shapes)
    parts.append("</svg>")

    out = os.path.splitext(path)[0] + ".svg"
    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(p for p in parts if p))
    return out


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    for path in sorted(glob.glob(os.path.join(here, "*.drawio"))):
        out = render(path)
        print(f"{os.path.basename(out):<42} {os.path.getsize(out) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
