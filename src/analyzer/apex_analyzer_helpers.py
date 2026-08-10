"""Low-level Apex parsing helpers (comment/string stripping, method-body extraction,
hardcoded-Id detection, recursion detection, SOQL-injection detection, CRUD/FLS
enforcement detection) used by ``src.analyzer.apex_analyzer``.
"""
from __future__ import annotations

import re


SALESFORCE_ID_RE = re.compile(r"['\"]([0-9a-zA-Z]{15}|[0-9a-zA-Z]{18})['\"]")
RESERVED_METHOD_NAMES = {
    "if", "for", "while", "do", "switch", "return", "new", "throw",
    "catch", "try", "else", "super", "this",
}
RECURSION_GUARD_HINTS = (
    "static",
    "set<id>",
    "set<string>",
    "recursionguard",
    "alreadyprocessed",
    "bypass",
    "recursion",
    "isfirstrun",
)
TRIGGER_DECLARATION_RE = re.compile(
    r"(?is)\btrigger\s+\w+\s+on\s+\w+\s*\(([^)]+)\)\s*\{"
)
TRIGGER_AFTER_EVENT_RE = re.compile(
    r"(?i)\bafter\s+(?:insert|update|undelete)\b"
)
PROD_ID_PREFIXES = {
    "001",
    "003",
    "005",
    "006",
    "00D",
    "00E",
    "00Q",
    "00T",
    "00U",
    "500",
    "800",
    "701",
    "801",
    "a0",
    "a1",
    "a2",
    "a3",
    "a4",
    "a5",
    "a6",
    "a7",
    "a8",
    "a9",
}


def _find_hardcoded_ids(body: str) -> set[str]:
    found: set[str] = set()
    for match in SALESFORCE_ID_RE.finditer(body):
        raw = match.group(1)
        prefix = raw[:3]
        if prefix in PROD_ID_PREFIXES:
            found.add(raw)
        elif prefix[:2] in {p for p in PROD_ID_PREFIXES if len(p) == 2}:
            found.add(raw)
    return found


def _count_code_lines(body: str) -> int:
    count = 0
    in_block_comment = False
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped[2:]:
                in_block_comment = True
            continue
        if stripped.startswith("//"):
            continue
        count += 1
    return count


def _strip_comments_and_strings(body: str) -> str:
    """Supprime les commentaires // et /* */ ainsi que les chaines litterales, en conservant les positions (remplacees par des espaces)."""
    out = []
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        nxt = body[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            while i < n and body[i] != "\n":
                out.append(" ")
                i += 1
        elif ch == "/" and nxt == "*":
            out.append("  ")
            i += 2
            while i < n and not (body[i] == "*" and i + 1 < n and body[i + 1] == "/"):
                out.append(" " if body[i] != "\n" else "\n")
                i += 1
            if i < n:
                out.append("  ")
                i += 2
        elif ch in ('"', "'"):
            quote = ch
            out.append(" ")
            i += 1
            while i < n and body[i] != quote:
                if body[i] == "\\" and i + 1 < n:
                    out.append("  ")
                    i += 2
                else:
                    out.append(" " if body[i] != "\n" else "\n")
                    i += 1
            if i < n:
                out.append(" ")
                i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


METHOD_HEADER_RE = re.compile(
    r"(?m)"
    r"^[ \t]*"
    r"(?:(?:public|private|protected|global)\s+)?"
    r"(?:(?:static|virtual|abstract|override|webservice|final|transient)\s+)*"
    r"(?:[\w<>\[\],\. ]+?)\s+"
    r"(\w+)\s*\([^;{}]*?\)\s*"
    r"\{"
)


def _extract_method_bodies(clean_body: str) -> list[tuple[str, str]]:
    """Retourne [(nom_methode, corps_complet)] en parcourant le code (commentaires deja retires)."""
    results: list[tuple[str, str]] = []
    for match in METHOD_HEADER_RE.finditer(clean_body):
        name = match.group(1)
        if name.lower() in RESERVED_METHOD_NAMES:
            continue
        brace_start = match.end() - 1
        depth = 0
        idx = brace_start
        end = brace_start
        while idx < len(clean_body):
            ch = clean_body[idx]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = idx + 1
                    break
            idx += 1
        if end > brace_start:
            results.append((name, clean_body[brace_start:end]))
    return results


def _detect_self_recursive_methods(body: str) -> list[str]:
    """Retourne la liste des noms de methodes qui s'invoquent elles-memes depuis leur propre corps.

    La detection est volontairement conservatrice :
      - on ne reporte que si aucune garde de reentrance evidente n'apparait dans la classe ;
      - on ignore les methodes dont le nom est un mot reserve / courant.
    """
    clean = _strip_comments_and_strings(body)
    lowered = clean.lower()
    if any(hint in lowered for hint in RECURSION_GUARD_HINTS):
        return []

    recursive: set[str] = set()
    for name, method_body in _extract_method_bodies(clean):
        if len(name) < 3:
            continue
        call_re = re.compile(rf"\b{re.escape(name)}\s*\(")
        if call_re.search(method_body):
            recursive.add(name)
    return sorted(recursive)


def _detect_trigger_after_save_recursion(body: str) -> tuple[set[str], str] | None:
    """Detecte un trigger after-save qui modifie ses propres enregistrements declencheurs.

    Retourne :
      - None si le pattern n'est pas detecte ;
      - (events, dml_sample) si le risque existe, ou events est l'ensemble "after insert/update/undelete"
        declare et dml_sample est l'extrait textuel du DML incrimine.
    """
    clean = _strip_comments_and_strings(body)

    header = TRIGGER_DECLARATION_RE.search(clean)
    if not header:
        return None
    events_raw = header.group(1)
    after_events = {
        f"after {m.group(0).split()[-1].lower()}"
        for m in TRIGGER_AFTER_EVENT_RE.finditer(events_raw)
    }
    if not after_events:
        return None

    if any(hint in clean.lower() for hint in RECURSION_GUARD_HINTS):
        return None

    direct_dml_re = re.compile(
        r"(?i)\b(?:insert|update|upsert|delete|undelete)\s+Trigger\s*\.\s*(?:new|newMap)\b"
    )
    direct_dml_values_re = re.compile(
        r"(?i)\b(?:insert|update|upsert|delete|undelete)\s+Trigger\s*\.\s*newMap\s*\.\s*values\s*\(\s*\)"
    )
    database_dml_re = re.compile(
        r"(?i)\bDatabase\s*\.\s*(?:insert|update|upsert|delete|undelete)\s*\(\s*"
        r"Trigger\s*\.\s*(?:new|newMap\s*\.\s*values\s*\(\s*\))"
    )
    for pat in (direct_dml_values_re, direct_dml_re, database_dml_re):
        match = pat.search(clean)
        if match:
            return after_events, _shorten(match.group(0))

    assign_re = re.compile(
        r"(?i)\b([A-Za-z_]\w*)\s*=\s*Trigger\s*\.\s*(?:new|newMap\s*\.\s*values\s*\(\s*\))"
    )
    aliases = {m.group(1) for m in assign_re.finditer(clean)}
    for alias in aliases:
        alias_direct = re.compile(
            rf"(?i)\b(?:insert|update|upsert|delete|undelete)\s+{re.escape(alias)}\b"
        )
        alias_db = re.compile(
            rf"(?i)\bDatabase\s*\.\s*(?:insert|update|upsert|delete|undelete)\s*\(\s*{re.escape(alias)}\b"
        )
        for pat in (alias_direct, alias_db):
            match = pat.search(clean)
            if match:
                return after_events, _shorten(match.group(0))
    return None


def _shorten(text: str, limit: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "..."


def _detect_soql_injection(body: str) -> list[int]:
    """Detect dynamic SOQL queries with potential injection risks."""
    clean = _strip_comments_and_strings(body)
    injection_lines = []

    # Look for Database.query(dynamic_string)
    # We look for concatenation (+) or variable interpolation ($)
    # while excluding String.escapeSingleQuotes
    query_re = re.compile(r"Database\.query\s*\(([^)]+)\)", re.IGNORECASE)

    for match in query_re.finditer(clean):
        arg = match.group(1)
        # If the argument contains concatenation or variable interpolation
        # and doesn't seem to use escapeSingleQuotes or bind variables
        if ("+" in arg or "$" in arg) and "escapesinglequotes" not in arg.lower() and ":" not in arg:
            line_num = body[: match.start()].count("\n") + 1
            injection_lines.append(line_num)

    return injection_lines


def _has_security_enforcement(body: str) -> bool:
    """Check if the class uses any explicit CRUD/FLS enforcement mechanism."""
    clean = _strip_comments_and_strings(body).upper()

    enforcements = [
        "WITH USER_MODE",
        "WITH SYSTEM_MODE",
        "WITH SECURITY_ENFORCED",
        "SECURITY.STRIPINACCESSIBLE",
        "ACCESSLEVEL.USER_MODE",
        "ACCESSLEVEL.SYSTEM_MODE",
        "ISACCESSIBLE(",
        "ISCREATEABLE(",
        "ISUPDATEABLE(",
        "ISDELETABLE(",
    ]

    return any(e in clean for e in enforcements)
