"""Export the architecture documents to self-contained HTML.

Markdown only shows its images in a previewer. These HTML exports need no
previewer, no extension and no network: the diagrams are inlined as SVG, so a
single file can be opened by double-click or sent as an attachment.

Deliberately not a general Markdown implementation -- it supports exactly the
constructs ARCHITECTURE.md and ANALYSIS_RULES.md use.

    python docs/architecture/_make_html_docs.py
"""
from __future__ import annotations

import html
import os
import re

SOURCES = ("ARCHITECTURE.md", "ANALYSIS_RULES.md")

STYLE = """
:root { color-scheme: light }
body { margin: 0 auto; padding: 48px 32px 96px; max-width: 980px;
       font: 16px/1.65 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
       color: #1f2328; background: #fff; }
h1, h2, h3 { line-height: 1.25; margin: 1.8em 0 .6em; font-weight: 600; }
h1 { font-size: 2em; padding-bottom: .3em; border-bottom: 1px solid #d1d9e0; margin-top: 0; }
h2 { font-size: 1.5em; padding-bottom: .3em; border-bottom: 1px solid #d1d9e0; }
h3 { font-size: 1.2em; }
p, ul, ol, table { margin: 0 0 1em; }
li { margin: .25em 0; }
a { color: #0969da; text-decoration: none; }
a:hover { text-decoration: underline; }
hr { height: 1px; margin: 2em 0; background: #d1d9e0; border: 0; }
blockquote { margin: 0 0 1em; padding: .6em 1em; border-left: .25em solid #d1d9e0;
             color: #59636e; background: #f6f8fa; border-radius: 0 6px 6px 0; }
blockquote p:last-child { margin-bottom: 0; }
code { padding: .2em .4em; font-size: 85%; background: #eff1f3; border-radius: 6px;
       font-family: ui-monospace, "Cascadia Mono", Consolas, monospace; }
pre { margin: 0 0 1em; padding: 16px; overflow: auto; background: #f6f8fa; border-radius: 6px; }
pre code { padding: 0; font-size: 90%; background: none; }
table { border-collapse: collapse; display: block; width: max-content; max-width: 100%;
        overflow: auto; }
th, td { padding: 6px 13px; border: 1px solid #d1d9e0; text-align: left; vertical-align: top; }
th { background: #f6f8fa; font-weight: 600; }
tr:nth-child(2n) td { background: #f6f8fa; }
figure { margin: 1.5em 0; padding: 12px; border: 1px solid #d1d9e0; border-radius: 6px;
         background: #fff; text-align: center; }
figure svg { max-width: 100%; height: auto; }
figcaption { margin-top: 10px; font-size: .85em; color: #59636e; }
"""


def inline(text: str) -> str:
    """Inline Markdown -> HTML. Code spans are protected from other rules."""
    spans: list[str] = []

    def stash(match: re.Match) -> str:
        spans.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\x00{len(spans) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash, text)
    text = html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*([^*]+)\*(?![\w*])", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], text)


def figure(alt: str, src: str, base: str) -> str:
    """Inline the SVG twin of an image reference; fall back to a plain <img>."""
    svg_path = os.path.join(base, os.path.splitext(src)[0] + ".svg")
    caption = html.escape(alt)
    if os.path.exists(svg_path):
        with open(svg_path, encoding="utf-8") as handle:
            svg = handle.read()
        svg = re.sub(r'\s(?:width|height)="[\d.]+"', "", svg, count=2)
        return f"<figure>{svg}<figcaption>{caption}</figcaption></figure>"
    return f'<figure><img src="{html.escape(src)}" alt="{caption}">' \
           f"<figcaption>{caption}</figcaption></figure>"


def table(rows: list[str]) -> str:
    def cells(row: str) -> list[str]:
        return [c.strip() for c in row.strip().strip("|").split("|")]

    head = "".join(f"<th>{inline(c)}</th>" for c in cells(rows[0]))
    body = "".join(
        "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells(row)) + "</tr>"
        for row in rows[2:]
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def convert(text: str, base: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
        elif stripped.startswith("```"):
            index += 1
            block: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                block.append(lines[index])
                index += 1
            index += 1
            out.append(f"<pre><code>{html.escape(chr(10).join(block))}</code></pre>")
        elif re.fullmatch(r"-{3,}", stripped):
            out.append("<hr>")
            index += 1
        elif match := re.match(r"(#{1,6})\s+(.*)", stripped):
            level = len(match.group(1))
            out.append(f"<h{level}>{inline(match.group(2))}</h{level}>")
            index += 1
        elif match := re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", stripped):
            out.append(figure(match.group(1), match.group(2), base))
            index += 1
        elif stripped.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(lines[index])
                index += 1
            out.append(table(rows) if len(rows) > 2 else "")
        elif stripped.startswith(">"):
            quote = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip().lstrip(">").strip())
                index += 1
            out.append(
                "<blockquote>"
                + "".join(f"<p>{inline(q)}</p>" for q in quote if q)
                + "</blockquote>"
            )
        elif re.match(r"[-*]\s+|\d+\.\s+", stripped):
            ordered = bool(re.match(r"\d+\.\s+", stripped))
            items = []
            while index < len(lines) and re.match(r"\s*([-*]|\d+\.)\s+", lines[index]):
                items.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[index]))
                index += 1
            tag = "ol" if ordered else "ul"
            out.append(
                f"<{tag}>" + "".join(f"<li>{inline(i)}</li>" for i in items) + f"</{tag}>"
            )
        else:
            paragraph = []
            while index < len(lines) and lines[index].strip() and not re.match(
                r"\s*(#{1,6}\s|```|\||>|-{3,}$|[-*]\s|\d+\.\s|!\[)", lines[index]
            ):
                paragraph.append(lines[index].strip())
                index += 1
            out.append(f"<p>{inline(' '.join(paragraph))}</p>")

    return "\n".join(part for part in out if part)


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    for name in SOURCES:
        with open(os.path.join(here, name), encoding="utf-8") as handle:
            source = handle.read()
        title = source.split("\n", 1)[0].lstrip("# ").strip()
        # Point cross-document links at the HTML twins.
        for other in SOURCES:
            source = source.replace(f"]({other})", f"]({other[:-3]}.html)")
        body = convert(source, here)
        target = os.path.join(here, f"{name[:-3]}.html")
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(
                '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
                '<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                f"<title>{html.escape(title)}</title>\n<style>{STYLE}</style>\n"
                f"</head>\n<body>\n{body}\n</body>\n</html>\n"
            )
        print(f"{os.path.basename(target):<28} {os.path.getsize(target) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
