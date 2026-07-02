"""RTF token helpers shared by the FR/EN guide builders.

Structured content -> RTF tokens. Kept simple on purpose.
"""
from __future__ import annotations


# Map of common non-ASCII characters used in the documents to their cp1252
# escape representation. Anything missing falls back to the unicode escape
# form (\uNNNN?) so the writer stays robust if extra characters slip in.
CP1252_MAP = {
    "\u00e0": "\\'e0", "\u00e2": "\\'e2", "\u00e4": "\\'e4",
    "\u00e7": "\\'e7",
    "\u00e8": "\\'e8", "\u00e9": "\\'e9", "\u00ea": "\\'ea", "\u00eb": "\\'eb",
    "\u00ee": "\\'ee", "\u00ef": "\\'ef",
    "\u00f4": "\\'f4", "\u00f6": "\\'f6",
    "\u00f9": "\\'f9", "\u00fb": "\\'fb", "\u00fc": "\\'fc",
    "\u00ff": "\\'ff",
    "\u00c0": "\\'c0", "\u00c2": "\\'c2",
    "\u00c7": "\\'c7",
    "\u00c8": "\\'c8", "\u00c9": "\\'c9", "\u00ca": "\\'ca",
    "\u00ce": "\\'ce", "\u00cf": "\\'cf",
    "\u00d4": "\\'d4",
    "\u00d9": "\\'d9", "\u00db": "\\'db",
    "\u00b0": "\\'b0",
    "\u00ab": "\\'ab", "\u00bb": "\\'bb",
    "\u20ac": "\\'80",
}


def rtf_escape(text: str) -> str:
    out: list[str] = []
    for char in text:
        if char in ("\\", "{", "}"):
            out.append("\\" + char)
        elif char in CP1252_MAP:
            out.append(CP1252_MAP[char])
        elif ord(char) < 128:
            out.append(char)
        else:
            out.append(f"\\u{ord(char)}?")
    return "".join(out)


HEADER = (
    "{\\rtf1\\ansi\\ansicpg1252\\deff0\\nouicompat\\deflang1036\n"
    "{\\fonttbl{\\f0\\fnil\\fcharset0 Calibri;}{\\f1\\fnil\\fcharset0 Consolas;}}\n"
    "{\\colortbl ;\\red0\\green0\\blue0;\\red0\\green70\\blue140;\\red80\\green80\\blue80;\\red200\\green80\\blue40;}\n"
    "{\\*\\generator Lucie Process Doc;}\\viewkind4\\uc1\n"
    "\\paperw11906\\paperh16838\\margl1134\\margr1134\\margt1134\\margb1134\n"
    "\\pard\\sa120\\sl276\\slmult1\\f0\\fs22 "
)
FOOTER = "}\n"


def h1(text: str) -> str:
    return (
        "\\pard\\sb240\\sa120\\keepn\\f0\\fs40\\b\\cf2 "
        + rtf_escape(text)
        + "\\b0\\cf1\\fs22\\par\n"
    )


def h2(text: str) -> str:
    return (
        "\\pard\\sb200\\sa100\\keepn\\f0\\fs30\\b\\cf2 "
        + rtf_escape(text)
        + "\\b0\\cf1\\fs22\\par\n"
    )


def h3(text: str) -> str:
    return (
        "\\pard\\sb160\\sa80\\keepn\\f0\\fs26\\b "
        + rtf_escape(text)
        + "\\b0\\fs22\\par\n"
    )


def paragraph(text: str) -> str:
    return "\\pard\\sa120\\sl276\\slmult1\\fs22 " + rtf_escape(text) + "\\par\n"


def quote(text: str) -> str:
    return (
        "\\pard\\sa120\\sl276\\slmult1\\li567\\ri567\\i\\cf3\\fs22 "
        + rtf_escape(text)
        + "\\i0\\cf1\\par\n"
    )


def bullets(items: list[str]) -> str:
    chunks = []
    for item in items:
        chunks.append(
            "\\pard\\fi-360\\li720\\sa80\\sl276\\slmult1\\fs22 "
            "\\bullet\\tab "
            + rtf_escape(item)
            + "\\par\n"
        )
    return "".join(chunks)


def numbered(items: list[str]) -> str:
    chunks = []
    for index, item in enumerate(items, start=1):
        chunks.append(
            "\\pard\\fi-360\\li720\\sa80\\sl276\\slmult1\\fs22 "
            f"{index}.\\tab "
            + rtf_escape(item)
            + "\\par\n"
        )
    return "".join(chunks)


def code_block(lines: list[str]) -> str:
    chunks = ["\\pard\\sa60\\sl240\\slmult1\\li360\\f1\\fs20\\cf4 "]
    for line in lines:
        chunks.append(rtf_escape(line) + "\\line ")
    chunks.append("\\f0\\fs22\\cf1\\par\n")
    return "".join(chunks)


def page_break() -> str:
    return "\\page\n"


def placeholder(text: str) -> str:
    return (
        "\\pard\\sa160\\sb160\\li360\\ri360\\b\\cf4\\fs24 "
        + rtf_escape(text)
        + "\\b0\\cf1\\fs22\\par\n"
    )


def build_document(parts: list[str]) -> str:
    return HEADER + "".join(parts) + FOOTER
