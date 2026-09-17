"""Generate the SVG-linked copies of the architecture documents.

``ARCHITECTURE.md`` and ``ANALYSIS_RULES.md`` embed the PNG renders, which any
Markdown viewer displays. This script derives ``*.svg.md`` twins that embed the
SVG renders instead, so the prose exists once and cannot drift.

    python docs/architecture/_make_svg_docs.py
"""
from __future__ import annotations

import os
import re

SOURCES = ("ARCHITECTURE.md", "ANALYSIS_RULES.md")

BANNER = (
    "> **Generated file — do not edit.** This is [`{origin}`]({origin}) with the "
    "diagrams embedded as SVG instead of PNG. Edit the original, then run "
    "`python docs/architecture/_make_svg_docs.py`.\n"
)

# §10 of ARCHITECTURE.md points at the other format; flip the direction.
PNG_POINTER = (
    "This document embeds the PNG, so it displays in any Markdown viewer without a "
    "draw.io plugin. A parallel copy, [`ARCHITECTURE.svg.md`](ARCHITECTURE.svg.md), "
    "embeds the SVG instead — identical prose, sharper at any zoom, and about fifteen "
    "times lighter."
)
SVG_POINTER = (
    "This copy embeds the SVG, which stays sharp at any zoom and weighs about fifteen "
    "times less. The original, [`ARCHITECTURE.md`](ARCHITECTURE.md), embeds the PNG "
    "instead — identical prose, and displayable in any Markdown viewer."
)


def convert(text: str, origin: str) -> str:
    text = re.sub(r"(!\[[^\]]*\]\(diagrams/[^)]+)\.png\)", r"\1.svg)", text)
    for name in SOURCES:
        twin = f"{name[:-3]}.svg.md"
        # Retarget cross-document links, and keep the visible label in step.
        text = text.replace(f"[`{name}`]({name})", f"[`{twin}`]({twin})")
        text = text.replace(f"]({name})", f"]({twin})")
    text = text.replace(PNG_POINTER, SVG_POINTER)

    lines = text.split("\n")
    insert_at = next(i for i, line in enumerate(lines) if line.startswith("# ")) + 1
    lines[insert_at:insert_at] = ["", BANNER.format(origin=origin)]
    return "\n".join(lines)


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    for name in SOURCES:
        with open(os.path.join(here, name), encoding="utf-8") as handle:
            source = handle.read()
        target = os.path.join(here, f"{name[:-3]}.svg.md")
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(convert(source, name))
        print(f"{os.path.basename(target):<28} <- {name}")


if __name__ == "__main__":
    main()
