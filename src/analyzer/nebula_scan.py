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
