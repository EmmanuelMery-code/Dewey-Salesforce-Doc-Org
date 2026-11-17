"""Regles Nebula Logger sur les composants LWC."""

from __future__ import annotations

import re

from src.analyzer.models import Finding
from src.analyzer.nebula_config import (
    NebulaConfig,
    language_issues,
    message_matches,
    sensitive_terms,
    tag_allowed,
)
from src.analyzer.nebula_scan import (
    add_finding,
    code_spans,
    find_calls,
    first_string_in,
    index_in_spans,
    line_of,
    match_closer,
    string_literals,
)
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import LwcInfo


_LOGGER_CALL_RE = re.compile(
    r"\blogger\s*\.\s*(error|warn|info|debug|fine|finer|finest|saveLog)\s*\(",
    re.IGNORECASE,
)
_CONSOLE_RE = re.compile(
    r"\bconsole\s*\.\s*(?:log|warn|error|debug|info)\s*\("
)
_ADD_TAG_RE = re.compile(r"\.addTag\s*\(")
_CATCH_RE = re.compile(r"\bcatch\s*\(")
_FUNC_RE = re.compile(
    r"(?m)^[ \t]*(?:async[ \t]+)?(?:function[ \t]+\w+|\w+)[ \t]*\([^)]*\)[ \t]*\{"
)
_JS_KEYWORDS = frozenset({
    "if", "for", "while", "switch", "catch", "function", "return", "do", "else",
})
_LEVELS = frozenset({"error", "warn", "info", "debug", "fine", "finer", "finest"})


def analyze_nebula_lwc(
    lwc: LwcInfo, catalog: RuleCatalog, config: NebulaConfig
) -> list[Finding]:
    if lwc.source_path is None:
        return []
    script = lwc.source_path / f"{lwc.name}.js"
    if not script.is_file():
        return []
    try:
        source = script.read_text(encoding="utf-8")
    except OSError:
        return []

    spans = code_spans(source, js=True)
    literals = string_literals(source, js=True)
    findings: list[Finding] = []
    pattern = config.compiled_format()
    console_lines = [line for line, _a, _b, _m in find_calls(source, _CONSOLE_RE, spans, js=True)]
    add_finding(
        findings, catalog, "NEBULA-LWC-001", "LWC", lwc.name, script,
        "nebula.lwc_console", console_lines,
    )

    ranges = _function_ranges(source, spans)
    save_gaps: list[int] = []
    format_lines: list[int] = []
    set_error_lines: list[int] = []
    sensitive_lines: list[int] = []
    sensitive_words: list[str] = []
    language_lines: list[int] = []
    language_words: list[str] = []
    tag_lines: list[int] = []
    tag_values: list[str] = []

    for region in ranges:
        calls = [
            call
            for call in find_calls(source, _LOGGER_CALL_RE, spans, js=True)
            if region[0] <= call[3].start() < region[1]
        ]
        level_calls = [call for call in calls if call[3].group(1).lower() in _LEVELS]
        if level_calls and not any(call[3].group(1).lower() == "savelog" for call in calls):
            save_gaps.append(level_calls[0][0])
        catches = _catch_bodies(source, spans, region)
        for line, args_start, args_end, match in level_calls:
            message = first_string_in(literals, args_start, args_end)
            if message is not None and not message_matches(message, pattern):
                format_lines.append(line)
            if message is not None:
                issues = language_issues(message)
                if issues:
                    language_lines.append(line)
                    language_words.extend(issues)
            terms = sensitive_terms(source[args_start:args_end])
            if terms:
                sensitive_lines.append(line)
                sensitive_words.extend(terms)
            if match.group(1).lower() == "error" and _inside_catch(match.start(), catches):
                if not _chains_set_error(source, match.end() - 1):
                    set_error_lines.append(line)
        for line, args_start, args_end, _match in find_calls(source, _ADD_TAG_RE, spans, js=True):
            if not (region[0] <= args_start < region[1]):
                continue
            value = first_string_in(literals, args_start, args_end)
            if value is None or tag_allowed(value, config.tags):
                continue
            tag_lines.append(line)
            tag_values.append(value)

    add_finding(findings, catalog, "NEBULA-LWC-002", "LWC", lwc.name, script, "nebula.lwc_save_log", save_gaps)
    add_finding(findings, catalog, "NEBULA-LWC-003", "LWC", lwc.name, script, "nebula.format", format_lines)
    add_finding(findings, catalog, "NEBULA-LWC-004", "LWC", lwc.name, script, "nebula.lwc_set_error", set_error_lines)
    add_finding(
        findings, catalog, "NEBULA-LWC-008", "LWC", lwc.name, script, "nebula.sensitive",
        sensitive_lines, sample=", ".join(sorted(set(sensitive_words))[:6]),
    )
    add_finding(
        findings, catalog, "NEBULA-LWC-009", "LWC", lwc.name, script, "nebula.language",
        language_lines, sample=", ".join(sorted(set(language_words))[:6]),
    )
    add_finding(
        findings, catalog, "NEBULA-LWC-012", "LWC", lwc.name, script, "nebula.tag",
        tag_lines, sample=", ".join(tag_values[:6]),
    )
    return findings


def _function_ranges(source: str, spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for match in _FUNC_RE.finditer(source):
        if not index_in_spans(spans, match.start()):
            continue
        name = match.group(0).strip().split()[-1].split("(")[0]
        if name in _JS_KEYWORDS:
            continue
        open_at = match.end() - 1
        if open_at < 0 or source[open_at] != "{":
            continue
        ranges.append((open_at, match_closer(source, open_at, "{", "}", js=True)))
    if ranges:
        return ranges
    return [(0, len(source))]


def _catch_bodies(
    source: str, spans: list[tuple[int, int]], region: tuple[int, int]
) -> list[tuple[int, int]]:
    bodies: list[tuple[int, int]] = []
    start, end = region
    for match in _CATCH_RE.finditer(source, start, end):
        if not index_in_spans(spans, match.start()):
            continue
        open_paren = match.end() - 1
        close_paren = match_closer(source, open_paren, "(", ")", js=True)
        cursor = close_paren
        while cursor < end and source[cursor].isspace():
            cursor += 1
        if cursor >= end or source[cursor] != "{":
            continue
        bodies.append((cursor + 1, match_closer(source, cursor, "{", "}", js=True) - 1))
    return bodies


def _inside_catch(index: int, catches: list[tuple[int, int]]) -> bool:
    return any(start <= index < end for start, end in catches)


def _chains_set_error(source: str, open_paren: int) -> bool:
    close_at = match_closer(source, open_paren, "(", ")", js=True)
    window = source[close_at : close_at + 80]
    return ".setError" in window
