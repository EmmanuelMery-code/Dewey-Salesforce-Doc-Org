"""Brace-aware DML/SOQL-in-loop detection helpers for Apex bodies."""

from __future__ import annotations

import re

_SOQL_IN_LOOP_RE = re.compile(
    r"\[\s*SELECT\b|Database\.query\s*\(", re.IGNORECASE
)
_DML_IN_LOOP_RE = re.compile(
    r"\b(?:insert|update|upsert|delete|undelete|merge)\b"
    r"|Database\.(?:insert|update|upsert|delete|undelete|merge)\s*\(",
    re.IGNORECASE,
)
_LOOP_KEYWORD_RE = re.compile(r"\b(for|while|do)\b", re.IGNORECASE)


def _strip_apex_comments(body: str) -> str:
    """Return *body* with comments (// and /* */) and string literals replaced
    by spaces, preserving newlines so that line numbers stay correct."""
    out = list(body)
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        nxt = body[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            # single-line comment: blank to end of line
            while i < n and body[i] != "\n":
                out[i] = " "
                i += 1
        elif ch == "/" and nxt == "*":
            # block comment
            out[i] = " "
            i += 1
            out[i] = " "
            i += 1
            while i < n:
                if body[i] == "*" and i + 1 < n and body[i + 1] == "/":
                    out[i] = " "
                    i += 1
                    out[i] = " "
                    i += 1
                    break
                elif body[i] != "\n":
                    out[i] = " "
                i += 1
        elif ch in ('"', "'"):
            quote = ch
            out[i] = " "
            i += 1
            while i < n and body[i] != quote:
                if body[i] == "\\" and i + 1 < n:
                    out[i] = " "
                    i += 1
                    out[i] = " "
                    i += 1
                elif body[i] != "\n":
                    out[i] = " "
                    i += 1
                else:
                    i += 1
            if i < n:
                out[i] = " "
                i += 1
        else:
            i += 1
    return "".join(out)


def _detect_pattern_in_loop(body: str, pattern: re.Pattern) -> int | None:
    """Return the 1-based line number of the first *pattern* match found
    inside an Apex loop body (for / while / do-while), or ``None``.

    The search is brace-aware: it extracts the exact body delimited by the
    matching closing brace before searching, so a DML/SOQL statement written
    *after* a loop (but within a few hundred characters) is **not** reported
    as a false positive.

    The function also ignores matches in the loop header itself — e.g. the
    SOQL written directly in ``for (SObject s : [SELECT ...])`` is skipped
    because that is the recommended pattern and does not cause governor issues.
    """
    clean = _strip_apex_comments(body)
    n = len(clean)
    i = 0

    while i < n:
        m = _LOOP_KEYWORD_RE.search(clean, i)
        if not m:
            break

        keyword = m.group(1).lower()
        pos = m.end()

        if keyword == "do":
            # do { ... } while (...)
            while pos < n and clean[pos] in " \t\r\n":
                pos += 1
            if pos >= n or clean[pos] != "{":
                i = m.end()
                continue
        else:
            # for / while: skip the condition (...)
            while pos < n and clean[pos] in " \t\r\n":
                pos += 1
            if pos >= n or clean[pos] != "(":
                i = m.end()
                continue
            # skip the entire condition, counting nested parens
            depth = 1
            pos += 1
            while pos < n and depth > 0:
                if clean[pos] == "(":
                    depth += 1
                elif clean[pos] == ")":
                    depth -= 1
                pos += 1
            # skip whitespace/newlines to reach the loop body {
            while pos < n and clean[pos] in " \t\r\n":
                pos += 1
            if pos >= n or clean[pos] != "{":
                # No braces: single-statement loop — still check it
                # by scanning to end of statement (next ;)
                stmt_start = pos
                stmt_end = clean.find(";", pos)
                if stmt_end == -1:
                    i = m.end()
                    continue
                hit = pattern.search(clean, stmt_start, stmt_end + 1)
                if hit:
                    return clean[: hit.end()].count("\n") + 1
                i = stmt_end + 1
                continue

        # Found the loop body opening brace — extract body by depth
        body_start = pos + 1
        depth = 1
        pos += 1
        while pos < n and depth > 0:
            if clean[pos] == "{":
                depth += 1
            elif clean[pos] == "}":
                depth -= 1
            pos += 1
        body_end = pos - 1  # exclusive; points at char after '}'

        hit = pattern.search(clean, body_start, body_end)
        if hit:
            return clean[: hit.end()].count("\n") + 1

        # Move past this loop and continue (handles nested / sequential loops)
        i = pos

    return None
