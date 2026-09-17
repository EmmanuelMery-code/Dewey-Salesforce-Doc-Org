"""Render the .drawio sources in this folder to PNG.

A raster fallback for viewers that do not display SVG. Layout comes from
``_drawio_common``, so PNG and SVG stay identical.

    python _render_png.py
"""
from __future__ import annotations

import glob
import os

from PIL import Image, ImageDraw

from _drawio_common import ARROW, Diagram, Shape, colour, label_layout, load, route

SCALE = 2
MARGIN = 12.0


def dashed_rect(draw, box, outline, width):
    x0, y0, x1, y1 = box
    dash, gap = 8 * SCALE, 5 * SCALE
    for x in range(int(x0), int(x1), dash + gap):
        draw.line([x, y0, min(x + dash, x1), y0], fill=outline, width=width)
        draw.line([x, y1, min(x + dash, x1), y1], fill=outline, width=width)
    for y in range(int(y0), int(y1), dash + gap):
        draw.line([x0, y, x0, min(y + dash, y1)], fill=outline, width=width)
        draw.line([x1, y, x1, min(y + dash, y1)], fill=outline, width=width)


def draw_shape(draw, shape: Shape):
    x = (shape.x + MARGIN) * SCALE
    y = (shape.y + MARGIN) * SCALE
    w, h = shape.w * SCALE, shape.h * SCALE
    box = [x, y, x + w, y + h]
    fill = colour(shape.style.get("fillColor"), "#ffffff")
    stroke = colour(shape.style.get("strokeColor"), "#666666")
    width = max(SCALE, 2)
    kind = shape.kind

    if kind == "text":
        return
    if kind == "ellipse":
        draw.ellipse(box, fill=fill, outline=stroke, width=width)
    elif kind == "rhombus":
        cx, cy = x + w / 2, y + h / 2
        draw.polygon([(cx, y), (x + w, cy), (cx, y + h), (x, cy)], fill=fill, outline=stroke)
    elif kind == "cylinder":
        lid = min(h * 0.18, 16 * SCALE)
        draw.rectangle([x, y + lid / 2, x + w, y + h - lid / 2], fill=fill, outline=None)
        draw.ellipse([x, y + h - lid, x + w, y + h], fill=fill, outline=stroke, width=width)
        draw.rectangle([x + width, y + lid / 2, x + w - width, y + h - lid / 2], fill=fill)
        draw.line([x, y + lid / 2, x, y + h - lid / 2], fill=stroke, width=width)
        draw.line([x + w, y + lid / 2, x + w, y + h - lid / 2], fill=stroke, width=width)
        draw.ellipse([x, y, x + w, y + lid], fill=fill, outline=stroke, width=width)
    elif kind == "note":
        fold = 14 * SCALE
        draw.polygon(
            [(x, y), (x + w - fold, y), (x + w, y + fold), (x + w, y + h), (x, y + h)],
            fill=fill,
            outline=stroke,
        )
        draw.line([x + w - fold, y, x + w - fold, y + fold], fill=stroke, width=width)
        draw.line([x + w - fold, y + fold, x + w, y + fold], fill=stroke, width=width)
    elif shape.style.get("dashed") == "1":
        draw.rectangle(box, fill=fill, outline=None)
        dashed_rect(draw, box, stroke, width)
    else:
        draw.rectangle(box, fill=fill, outline=stroke, width=width)


def draw_label(draw, shape: Shape):
    fill = colour(shape.style.get("fontColor"), "#000000")
    for x, y, line, font in label_layout(shape, SCALE):
        if line:
            draw.text((x + MARGIN * SCALE, y + MARGIN * SCALE), line, font=font, fill=fill)


def draw_edge(draw, diagram: Diagram, edge):
    from _drawio_common import font_for

    source, target = diagram.shape(edge.source), diagram.shape(edge.target)
    if not source or not target:
        return
    points, direction = route(source, target, SCALE)
    points = [(px + MARGIN * SCALE, py + MARGIN * SCALE) for px, py in points]
    stroke = colour(edge.style.get("strokeColor"), "#666666")
    width = max(SCALE, 2)

    for a, b in zip(points, points[1:]):
        draw.line([a, b], fill=stroke, width=width)

    tip_x, tip_y = points[-1]
    dx, dy = direction
    size = ARROW * SCALE
    if dx:
        head = [(tip_x + dx * size, tip_y), (tip_x, tip_y - size * 0.55), (tip_x, tip_y + size * 0.55)]
    else:
        head = [(tip_x, tip_y + dy * size), (tip_x - size * 0.55, tip_y), (tip_x + size * 0.55, tip_y)]
    draw.polygon(head, fill=stroke)

    if edge.text:
        font = font_for(9, scale=SCALE)
        anchor = points[len(points) // 2]
        for index, line in enumerate(edge.text.split("\n")):
            text_width = font.getlength(line)
            top = anchor[1] - 7 * SCALE + index * 11 * SCALE
            draw.rectangle(
                [anchor[0] - text_width / 2 - 3 * SCALE, top,
                 anchor[0] + text_width / 2 + 3 * SCALE, top + 12 * SCALE],
                fill="#ffffff",
            )
            draw.text((anchor[0] - text_width / 2, top), line, font=font, fill=stroke)


def render(path: str) -> str:
    diagram = load(path)
    size = (
        int((diagram.width + 2 * MARGIN) * SCALE),
        int((diagram.height + 2 * MARGIN) * SCALE),
    )
    image = Image.new("RGB", size, "#ffffff")
    draw = ImageDraw.Draw(image)

    for shape in diagram.shapes:
        draw_shape(draw, shape)
    for edge in diagram.edges:
        draw_edge(draw, diagram, edge)
    for shape in diagram.shapes:
        draw_label(draw, shape)

    out = os.path.splitext(path)[0] + ".png"
    image.save(out, "PNG")
    return out


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    for path in sorted(glob.glob(os.path.join(here, "*.drawio"))):
        out = render(path)
        with Image.open(out) as image:
            print(
                f"{os.path.basename(out):<42} {image.width}x{image.height}px  "
                f"{os.path.getsize(out) / 1024:.0f} KB"
            )


if __name__ == "__main__":
    main()
