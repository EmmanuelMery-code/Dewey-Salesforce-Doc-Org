"""Sanity check for the .drawio sources in this folder.

Checks, per file: XML parses, every edge endpoint and parent id exists, no two
shapes partially overlap (full containment is fine: that is a background band),
and every label fits inside its shape once <br> line breaks are accounted for.
"""
from __future__ import annotations

import glob
import itertools
import os
import re
import xml.etree.ElementTree as ET

LINE_HEIGHT = 1.30
CHAR_WIDTH = 0.55
PADDING_X = 16
PADDING_Y = 12


def plain_label(value: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", value)
    return text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def font_size(style: str) -> float:
    match = re.search(r"fontSize=(\d+)", style or "")
    return float(match.group(1)) if match else 12.0


def needed_height(label: str, width: float, size: float, borderless: bool = False) -> float:
    # A borderless text label has no shape padding to fit inside.
    padding_x = 2 if borderless else PADDING_X
    padding_y = 2 if borderless else PADDING_Y
    usable = max(width - padding_x, 20)
    chars_per_line = max(int(usable / (size * CHAR_WIDTH)), 8)
    lines = sum(max(1, -(-len(seg) // chars_per_line)) for seg in label.split("\n"))
    return lines * size * LINE_HEIGHT + padding_y


def box(cell: ET.Element) -> tuple[float, float, float, float] | None:
    geometry = cell.find("mxGeometry")
    if geometry is None:
        return None
    try:
        return (
            float(geometry.get("x") or 0),
            float(geometry.get("y") or 0),
            float(geometry.get("width") or 0),
            float(geometry.get("height") or 0),
        )
    except ValueError:
        return None


def contains(outer, inner) -> bool:
    ax, ay, aw, ah = outer
    bx, by, bw, bh = inner
    return ax <= bx and ay <= by and ax + aw >= bx + bw and ay + ah >= by + bh


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    problems = 0

    for path in sorted(glob.glob(os.path.join(here, "*.drawio"))):
        name = os.path.basename(path)
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as error:
            print(f"{name}: XML INVALID — {error}")
            problems += 1
            continue

        cells = list(root.iter("mxCell"))
        ids = {c.get("id") for c in cells}
        dangling = [
            (c.get("id"), attr, c.get(attr))
            for c in cells
            for attr in ("source", "target", "parent")
            if c.get(attr) and c.get(attr) not in ids
        ]

        shapes = {c.get("id"): box(c) for c in cells if c.get("vertex") == "1"}
        shapes = {k: v for k, v in shapes.items() if v and v[2] and v[3]}
        overlaps = []
        for a, b in itertools.combinations(shapes, 2):
            ra, rb = shapes[a], shapes[b]
            ox = min(ra[0] + ra[2], rb[0] + rb[2]) - max(ra[0], rb[0])
            oy = min(ra[1] + ra[3], rb[1] + rb[3]) - max(ra[1], rb[1])
            if ox > 1 and oy > 1 and not contains(ra, rb) and not contains(rb, ra):
                overlaps.append((a, b, int(ox), int(oy)))

        tight = []
        for cell in cells:
            value = cell.get("value")
            rect = box(cell)
            if not value or cell.get("vertex") != "1" or not rect or not rect[2]:
                continue
            style = cell.get("style") or ""
            label = plain_label(value)
            required = needed_height(
                label, rect[2], font_size(style), borderless=style.startswith("text;")
            )
            if required > rect[3] + 1:
                tight.append((cell.get("id"), int(rect[3]), int(required)))

        raw_newlines = sum(1 for c in cells if "\n" in (c.get("value") or ""))
        status = "OK" if not (dangling or overlaps or tight or raw_newlines) else "PROBLEM"
        print(
            f"{name:<42} {status:<8} shapes={len(shapes):<3} "
            f"dangling={len(dangling)} overlaps={len(overlaps)} "
            f"overflow={len(tight)} rawNewlines={raw_newlines}"
        )
        for item in dangling + overlaps + tight:
            print("     ", item)
        problems += len(dangling) + len(overlaps) + len(tight) + raw_newlines

    print()
    print("ALL DIAGRAMS CLEAN" if not problems else f"{problems} problem(s) remain")
    return problems


if __name__ == "__main__":
    raise SystemExit(0 if main() == 0 else 1)
