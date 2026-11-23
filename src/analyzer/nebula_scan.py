"""Decoupage de source Apex ou JavaScript pour les regles Nebula."""

from __future__ import annotations

import re
from pathlib import Path

from src.analyzer.models import Finding
from src.analyzer.rule_catalog import RuleCatalog


_APEX_METHOD_RE = re.compile(
    r"(?m)^[ \t]*(?:@\w+(?:\([^)\n]*\))?[ \t]*)*"
    r"(?:(?:public|private|protected|global|static|override|virtual|webservice|testmethod)[ \t]+)+"
    r"(?:[\w.<>,\[\] \t]+[ \t]+)?"
    r"(\w+)[ \t]*\([^;{}]*\)[ \t]*\{"
)


def line_of(source: str, index: int) -> int:
    return source.count("\n", 0, index) + 1


def _skip_string(source: str, start: int, js: bool) -> int:
    quote = source[start]
    i = start + 1
    n = len(source)
    while i < n:
        if js and source[i] == "\\":
            i += 2
            continue
        if quote == "'" and source[i] == "'" and i + 1 < n and source[i + 1] == "'":
            i += 2
            continue
        if source[i] == quote:
            return i + 1
        i += 1
    return n


def _skip_non_code(source: str, index: int, js: bool) -> int | None:
    n = len(source)
    nxt = source[index + 1] if index + 1 < n else ""
    ch = source[index]
    if ch == "/" and nxt == "/":
        newline = source.find("\n", index)
        return n if newline < 0 else newline + 1
    if ch == "/" and nxt == "*":
        end = source.find("*/", index + 2)
        return n if end < 0 else end + 2
    quotes = ("'", '"', "`") if js else ("'",)
    if ch in quotes:
        return _skip_string(source, index, js)
    return None


def code_spans(source: str, js: bool = False) -> list[tuple[int, int]]:
    """Return the source ranges that are neither comments nor string literals."""

    spans: list[tuple[int, int]] = []
    i = 0
    start = 0
    n = len(source)
    while i < n:
        skipped = _skip_non_code(source, i, js)
        if skipped is None:
            i += 1
            continue
        if i > start:
            spans.append((start, i))
        i = skipped
        start = i
    if n > start:
        spans.append((start, n))
    return spans


def index_in_spans(spans: list[tuple[int, int]], index: int) -> bool:
    for start, end in spans:
        if start <= index < end:
            return True
        if start > index:
            return False
    return False


def code_slice(source: str, spans: list[tuple[int, int]], start: int, end: int) -> str:
    """Return the non-comment, non-string fragment of ``source[start:end]``."""

    pieces: list[str] = []
    for span_start, span_end in spans:
        if span_end <= start:
            continue
        if span_start >= end:
            break
        pieces.append(source[max(span_start, start) : min(span_end, end)])
    return " ".join(pieces)


def match_closer(
    source: str, open_at: int, open_ch: str, close_ch: str, js: bool = False
) -> int:
    """Return the index just after the closer matching ``source[open_at]``."""

    if open_at >= len(source) or source[open_at] != open_ch:
        return len(source)
    depth = 0
    i = open_at
    n = len(source)
    while i < n:
        skipped = _skip_non_code(source, i, js)
        if skipped is not None:
            i = skipped
            continue
        ch = source[i]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def string_literals(source: str, js: bool = False) -> list[tuple[int, int, str]]:
    """Return ``(start, end, content)`` for each string literal."""

    found: list[tuple[int, int, str]] = []
    i = 0
    n = len(source)
    quotes = ("'", '"', "`") if js else ("'",)
    while i < n:
        if source[i] == "/" and i + 1 < n and source[i + 1] in "/*":
            skipped = _skip_non_code(source, i, js)
            i = n if skipped is None else skipped
            continue
        if source[i] not in quotes:
            i += 1
            continue
        end = _skip_string(source, i, js)
        raw = source[i + 1 : end - 1] if end > i + 1 else ""
        if source[i] == "'":
            raw = raw.replace("''", "'")
        found.append((i, end, raw))
        i = end
    return found


def first_string_in(literals: list[tuple[int, int, str]], start: int, end: int) -> str | None:
    for lit_start, _lit_end, content in literals:
        if start <= lit_start < end:
            return content
    return None


_IDENT_RE = re.compile(r"[A-Za-z_$][\w$]*")
_TEMPLATE_EXPR_RE = re.compile(r"\$\{([^}]*)\}")
_PLACEHOLDER = "x"
_MAX_RESOLVE_DEPTH = 3


def _split_top(
    source: str, start: int, end: int, seps: str, js: bool
) -> list[tuple[int, int]]:
    """Split ``source[start:end]`` on ``seps`` found outside strings and brackets."""

    parts: list[tuple[int, int]] = []
    depth = 0
    part_start = start
    i = start
    while i < end:
        skipped = _skip_non_code(source, i, js)
        if skipped is not None:
            i = skipped
            continue
        ch = source[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and ch in seps:
            parts.append((part_start, i))
            part_start = i + 1
        i += 1
    parts.append((part_start, min(i, end)))
    return parts


def _literal_text(raw: str, quote: str, js: bool, resolve_name) -> str:
    if quote == "'":
        raw = raw.replace("''", "'")
    if js and quote == "`":
        def _substitute(match: re.Match[str]) -> str:
            name = match.group(1).strip()
            if _IDENT_RE.fullmatch(name):
                value = resolve_name(name)
                if value is not None:
                    return value
            return _PLACEHOLDER

        raw = _TEMPLATE_EXPR_RE.sub(_substitute, raw)
    return raw


def _resolve_identifier(
    source: str,
    spans: list[tuple[int, int]],
    name: str,
    before: int,
    region_start: int,
    js: bool,
    depth: int,
) -> str | None:
    """Return the text assigned to ``name`` (method scope first, then the whole file)."""

    if depth >= _MAX_RESOLVE_DEPTH:
        return None
    assign = re.compile(r"(?<![\w.$])" + re.escape(name) + r"\s*=(?![=>])")
    local = [
        m for m in assign.finditer(source, max(region_start, 0), before)
        if index_in_spans(spans, m.start())
    ]
    if local:
        match = local[-1]
    else:
        anywhere = [m for m in assign.finditer(source) if index_in_spans(spans, m.start())]
        if not anywhere:
            return None
        match = anywhere[0]
    init_start, init_end = _split_top(source, match.end(), len(source), ";", js)[0]
    return _concat_text(
        source, spans, init_start, init_end, match.start(), region_start, js, depth + 1
    )


def _concat_text(
    source: str,
    spans: list[tuple[int, int]],
    start: int,
    end: int,
    before: int,
    region_start: int,
    js: bool,
    depth: int,
) -> str | None:
    """Evaluate ``a + 'b' + c`` into text; unknown pieces become a placeholder.

    Returns ``None`` when the first piece cannot be determined, because the
    beginning of the message is then unknown.
    """

    pieces: list[str] = []
    for index, (part_start, part_end) in enumerate(_split_top(source, start, end, "+", js)):
        raw = source[part_start:part_end]
        text = raw.strip()
        piece = _piece_text(
            source, spans, part_start + len(raw) - len(raw.lstrip()), text,
            before, region_start, js, depth,
        )
        if piece is None:
            if index == 0:
                return None
            piece = _PLACEHOLDER
        pieces.append(piece)
    return "".join(pieces)


def _piece_text(
    source: str,
    spans: list[tuple[int, int]],
    at: int,
    text: str,
    before: int,
    region_start: int,
    js: bool,
    depth: int,
) -> str | None:
    if not text:
        return None

    def resolve_name(name: str) -> str | None:
        return _resolve_identifier(source, spans, name, before, region_start, js, depth)

    quotes = ("'", '"', "`") if js else ("'",)
    if text[0] in quotes:
        if _skip_string(source, at, js) != at + len(text) or len(text) < 2:
            return None
        return _literal_text(text[1:-1], text[0], js, resolve_name)
    if _IDENT_RE.fullmatch(text):
        return resolve_name(text)
    if text[0] == "(" and match_closer(source, at, "(", ")", js) == at + len(text):
        return _concat_text(source, spans, at + 1, at + len(text) - 1, before, region_start, js, depth)
    return None


def resolve_message(
    source: str,
    spans: list[tuple[int, int]],
    args_start: int,
    args_end: int,
    region_start: int = 0,
    js: bool = False,
) -> str | None:
    """Return the text of the first call argument as it will be built at runtime.

    String literals are kept, variables are replaced by the text they were
    assigned (``String scope = '[A.' + op + '] '``) and other dynamic pieces are
    replaced by a placeholder. ``None`` means the beginning of the message is
    unknown (parameter, field or method call), so no format verdict is possible.
    """

    first_start, first_end = _split_top(source, args_start, args_end, ",", js)[0]
    return _concat_text(
        source, spans, first_start, first_end, first_start, region_start, js, 0
    )


def find_calls(
    source: str,
    pattern: re.Pattern[str],
    spans: list[tuple[int, int]],
    js: bool = False,
) -> list[tuple[int, int, int, re.Match[str]]]:
    """Return ``(line, args_start, args_end, match)`` for each call in code."""

    found: list[tuple[int, int, int, re.Match[str]]] = []
    for span_start, span_end in spans:
        for match in pattern.finditer(source, span_start, span_end):
            open_at = match.end() - 1
            if open_at < 0 or open_at >= len(source) or source[open_at] != "(":
                continue
            close_at = match_closer(source, open_at, "(", ")", js)
            found.append((line_of(source, match.start()), open_at + 1, close_at - 1, match))
    return found


def apex_method_ranges(source: str, spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Return the body range of each Apex method, including the braces."""

    ranges: list[tuple[int, int]] = []
    for match in _APEX_METHOD_RE.finditer(source):
        if not index_in_spans(spans, match.start()):
            continue
        open_at = match.end() - 1
        close_at = match_closer(source, open_at, "{", "}")
        ranges.append((open_at, close_at))
    if ranges:
        return ranges
    brace = _first_code_char(source, spans, "{")
    if brace < 0:
        return [(0, len(source))]
    return [(brace, match_closer(source, brace, "{", "}"))]


def _first_code_char(source: str, spans: list[tuple[int, int]], char: str) -> int:
    for start, end in spans:
        found = source.find(char, start, end)
        if found >= 0:
            return found
    return -1


def add_finding(
    findings: list[Finding],
    catalog: RuleCatalog,
    rule_id: str,
    target_kind: str,
    target_name: str,
    source_path: Path | None,
    message_key: str,
    lines: list[int],
    sample: str = "",
) -> None:
    rule = catalog.get(rule_id)
    if rule is None or not rule.enabled or not lines:
        return
    unique = sorted(set(lines))
    preview = ", ".join(str(number) for number in unique[:8])
    findings.append(
        Finding(
            rule=rule,
            target_kind=target_kind,
            target_name=target_name,
            message=catalog.t(f"{message_key}.message"),
            details=[catalog.t(f"{message_key}.detail", lines=preview, sample=sample)],
            source_path=source_path,
            line=unique[0],
        )
    )
