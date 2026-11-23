"""Regles Nebula Logger sur les classes et triggers Apex."""

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
    apex_method_ranges,
    code_slice,
    code_spans,
    find_calls,
    first_string_in,
    index_in_spans,
    line_of,
    match_closer,
    resolve_message,
    string_literals,
)
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import ApexArtifact


_LOGGER_CALL_RE = re.compile(
    r"\bLogger\s*\.\s*(error|warn|info|debug|fine|finer|finest|saveLog)\s*\("
)
_ADD_TAG_RE = re.compile(r"\.addTag\s*\(")
_SYSTEM_DEBUG_RE = re.compile(r"\bSystem\s*\.\s*debug\s*\(")
_JSON_RE = re.compile(r"\bJSON\s*\.\s*serialize(?:Pretty)?\s*\(")
_PARTIAL_DML_RE = re.compile(
    r"\bDatabase\s*\.\s*(?:insert|update|upsert|delete)\s*\("
)
_CATCH_RE = re.compile(r"\bcatch\s*\(")
_FINALLY_RE = re.compile(r"\bfinally\s*\{")
_LOOP_RE = re.compile(r"\b(?:for|while)\s*\(")
_LEVELS = frozenset({"error", "warn", "info", "debug", "fine", "finer", "finest"})
_NON_ERROR_LEVELS = frozenset({"warn", "info", "debug", "fine", "finer", "finest"})
_JSON_LEVELS = frozenset({"error", "warn", "info", "debug"})


def analyze_nebula_apex(
    artifact: ApexArtifact, catalog: RuleCatalog, config: NebulaConfig
) -> list[Finding]:
    if artifact.is_test or artifact.is_interface or not artifact.body:
        return []
    source = artifact.body
    spans = code_spans(source)
    literals = string_literals(source)
    kind = "ApexTrigger" if artifact.kind == "trigger" else "ApexClass"
    prefix = "NEBULA-TRIG" if artifact.kind == "trigger" else "NEBULA-APEX"
    findings: list[Finding] = []
    pattern = config.compiled_format()

    debug_lines = [
        line
        for line, _args_start, _args_end, _match in find_calls(source, _SYSTEM_DEBUG_RE, spans)
    ]
    add_finding(
        findings, catalog, f"{prefix}-001", kind, artifact.name, artifact.source_path,
        "nebula.system_debug", debug_lines,
    )

    ranges = apex_method_ranges(source, spans)
    save_gaps: list[int] = []
    multi_save: list[int] = []
    loop_lines: list[int] = []
    json_lines: list[int] = []
    format_lines: list[int] = []
    sensitive_lines: list[int] = []
    sensitive_words: list[str] = []
    language_lines: list[int] = []
    language_words: list[str] = []
    swallowed: list[int] = []
    wrong_level: list[int] = []
    partial_lines: list[int] = []
    tag_lines: list[int] = []
    tag_values: list[str] = []

    for region in ranges:
        calls = [
            call
            for call in find_calls(source, _LOGGER_CALL_RE, spans)
            if region[0] <= call[3].start() < region[1]
        ]
        level_calls = [call for call in calls if call[3].group(1) in _LEVELS]
        save_calls = [call for call in calls if call[3].group(1) == "saveLog"]
        if len(save_calls) > 1:
            multi_save.extend(call[0] for call in save_calls)
        if level_calls and not _finally_saves(source, spans, region):
            save_gaps.append(level_calls[0][0])

        error_spans = [
            (call[1], call[2]) for call in level_calls if call[3].group(1) == "error"
        ]
        for line, args_start, args_end, match in level_calls:
            level = match.group(1)
            args = source[args_start:args_end]
            message = resolve_message(source, spans, args_start, args_end, region[0])
            if message is not None and not message_matches(message, pattern):
                format_lines.append(line)
            if message is not None:
                issues = language_issues(message)
                if issues:
                    language_lines.append(line)
                    language_words.extend(issues)
            terms = sensitive_terms(code_slice(source, spans, args_start, args_end))
            if terms:
                sensitive_lines.append(line)
                sensitive_words.extend(terms)
            if level in _JSON_LEVELS and _JSON_RE.search(args):
                json_lines.append(line)

        loop_lines.extend(_logs_in_loops(source, spans, region, calls))
        swallowed.extend(_swallowed_catches(source, spans, region, level_calls))
        wrong_level.extend(_wrong_levels(source, spans, region, level_calls))
        partial_lines.extend(_partial_dml(source, spans, region, error_spans))
        for line, value in _bad_tags(source, spans, literals, region, config):
            tag_lines.append(line)
            tag_values.append(value)

    path = artifact.source_path
    name = artifact.name
    add_finding(findings, catalog, f"{prefix}-002", kind, name, path, "nebula.swallowed", swallowed)
    add_finding(findings, catalog, f"{prefix}-003", kind, name, path, "nebula.save_log_finally", save_gaps)
    add_finding(findings, catalog, f"{prefix}-004", kind, name, path, "nebula.multiple_save_log", multi_save)
    add_finding(findings, catalog, f"{prefix}-005", kind, name, path, "nebula.log_in_loop", loop_lines)
    add_finding(findings, catalog, f"{prefix}-006", kind, name, path, "nebula.json_serialize", json_lines)
    add_finding(findings, catalog, f"{prefix}-007", kind, name, path, "nebula.format", format_lines)
    add_finding(
        findings, catalog, f"{prefix}-008", kind, name, path, "nebula.sensitive",
        sensitive_lines, sample=", ".join(sorted(set(sensitive_words))[:6]),
    )
    add_finding(
        findings, catalog, f"{prefix}-009", kind, name, path, "nebula.language",
        language_lines, sample=", ".join(sorted(set(language_words))[:6]),
    )
    add_finding(findings, catalog, f"{prefix}-010", kind, name, path, "nebula.wrong_level", wrong_level)
    add_finding(findings, catalog, f"{prefix}-011", kind, name, path, "nebula.partial_dml", partial_lines)
    add_finding(
        findings, catalog, f"{prefix}-012", kind, name, path, "nebula.tag",
        tag_lines, sample=", ".join(tag_values[:6]),
    )
    return findings


def _finally_saves(source: str, spans: list[tuple[int, int]], region: tuple[int, int]) -> bool:
    start, end = region
    for match in _FINALLY_RE.finditer(source, start, end):
        if not index_in_spans(spans, match.start()):
            continue
        open_at = match.end() - 1
        close_at = match_closer(source, open_at, "{", "}")
        body = source[open_at:close_at]
        if re.search(r"\bLogger\s*\.\s*saveLog\s*\(", body):
            return True
    return False


def _logs_in_loops(
    source: str,
    spans: list[tuple[int, int]],
    region: tuple[int, int],
    calls: list[tuple[int, int, int, re.Match[str]]],
) -> list[int]:
    lines: list[int] = []
    start, end = region
    for match in _LOOP_RE.finditer(source, start, end):
        if not index_in_spans(spans, match.start()):
            continue
        open_paren = match.end() - 1
        close_paren = match_closer(source, open_paren, "(", ")")
        cursor = close_paren
        while cursor < end and source[cursor].isspace():
            cursor += 1
        if cursor >= end or source[cursor] != "{":
            continue
        body_end = match_closer(source, cursor, "{", "}")
        for line, _args_start, _args_end, call in calls:
            if cursor < call.start() < body_end:
                lines.append(line)
    return lines


def _catch_bodies(
    source: str, spans: list[tuple[int, int]], region: tuple[int, int]
) -> list[tuple[int, int, str, int]]:
    bodies: list[tuple[int, int, str, int]] = []
    start, end = region
    for match in _CATCH_RE.finditer(source, start, end):
        if not index_in_spans(spans, match.start()):
            continue
        open_paren = match.end() - 1
        close_paren = match_closer(source, open_paren, "(", ")")
        params = source[open_paren + 1 : close_paren - 1]
        names = re.findall(r"\b([A-Za-z_]\w*)\b", params)
        variable = names[-1] if names else ""
        cursor = close_paren
        while cursor < end and source[cursor].isspace():
            cursor += 1
        if cursor >= end or source[cursor] != "{":
            continue
        body_end = match_closer(source, cursor, "{", "}")
        bodies.append((cursor + 1, body_end - 1, variable, line_of(source, match.start())))
    return bodies


def _swallowed_catches(
    source: str,
    spans: list[tuple[int, int]],
    region: tuple[int, int],
    level_calls: list[tuple[int, int, int, re.Match[str]]],
) -> list[int]:
    lines: list[int] = []
    for body_start, body_end, variable, line in _catch_bodies(source, spans, region):
        logged = False
        for _call_line, args_start, args_end, match in level_calls:
            if match.group(1) != "error" or not (body_start <= match.start() < body_end):
                continue
            if not variable or re.search(rf"\b{re.escape(variable)}\b", source[args_start:args_end]):
                logged = True
                break
        if not logged:
            lines.append(line)
    return lines


def _wrong_levels(
    source: str,
    spans: list[tuple[int, int]],
    region: tuple[int, int],
    level_calls: list[tuple[int, int, int, re.Match[str]]],
) -> list[int]:
    lines: list[int] = []
    for body_start, body_end, _variable, _line in _catch_bodies(source, spans, region):
        for call_line, _args_start, _args_end, match in level_calls:
            if match.group(1) in _NON_ERROR_LEVELS and body_start <= match.start() < body_end:
                lines.append(call_line)
    return lines


def _split_args(args: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    i = 0
    while i < len(args):
        if args[i] == "'":
            end = _skip_apex_string(args, i)
            current.append(args[i:end])
            i = end
            continue
        ch = args[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
        i += 1
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _skip_apex_string(source: str, start: int) -> int:
    i = start + 1
    while i < len(source):
        if source[i] == "'" and i + 1 < len(source) and source[i + 1] == "'":
            i += 2
            continue
        if source[i] == "'":
            return i + 1
        i += 1
    return len(source)


def _partial_dml(
    source: str,
    spans: list[tuple[int, int]],
    region: tuple[int, int],
    error_spans: list[tuple[int, int]],
) -> list[int]:
    lines: list[int] = []
    start, end = region
    for match in _PARTIAL_DML_RE.finditer(source, start, end):
        if not index_in_spans(spans, match.start()):
            continue
        open_paren = match.end() - 1
        close_paren = match_closer(source, open_paren, "(", ")")
        args = _split_args(source[open_paren + 1 : close_paren - 1])
        if not any(arg == "false" for arg in args):
            continue
        if any(span_start <= match.start() < span_end for span_start, span_end in error_spans):
            continue
        window = source[max(start, match.start() - 80) : match.start()]
        assigned = re.search(r"\b(\w+)\s*=\s*$", window)
        logged = False
        for span_start, span_end in error_spans:
            error_args = source[span_start:span_end]
            if "SaveResult" in error_args or "DeleteResult" in error_args:
                logged = True
                break
            if assigned and re.search(rf"\b{re.escape(assigned.group(1))}\b", error_args):
                logged = True
                break
        if not logged:
            lines.append(line_of(source, match.start()))
    return lines


def _bad_tags(
    source: str,
    spans: list[tuple[int, int]],
    literals: list[tuple[int, int, str]],
    region: tuple[int, int],
    config: NebulaConfig,
) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for line, args_start, args_end, _match in find_calls(source, _ADD_TAG_RE, spans):
        if not (region[0] <= args_start < region[1]):
            continue
        value = first_string_in(literals, args_start, args_end)
        if value is None or tag_allowed(value, config.tags):
            continue
        found.append((line, value))
    return found
