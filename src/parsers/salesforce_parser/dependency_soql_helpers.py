"""SOQL-in-Apex field usage extraction, used by :mod:`dependencies_mixin`.

Best-effort, regex-based SOQL parsing (there is no real SOQL grammar here):
good enough to stop a field that is *only* ever referenced inside a SOQL
projection (e.g. ``[SELECT Field__c FROM Object__c]``) from being wrongly
flagged as orphan, without needing a full parser. Handles the bracket
literal syntax, static SOQL string literals (e.g. passed to
``Database.query``), parent-relationship traversal (``Rel__r.Field__c``)
and one level of child-relationship subqueries.
"""

from __future__ import annotations

import re

from src.core.models import ObjectInfo

_SOQL_BLOCK_RE = re.compile(r"\[\s*(select\b.*?)\]", re.IGNORECASE | re.DOTALL)
_SOQL_STRING_LITERAL_RE = re.compile(
    r"'((?:[^'\\]|\\.)*?\bselect\b(?:[^'\\]|\\.)*?\bfrom\b(?:[^'\\]|\\.)*?)'",
    re.IGNORECASE | re.DOTALL,
)
_SOQL_FROM_RE = re.compile(r"\bfrom\b", re.IGNORECASE)
_SOQL_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
_SOQL_FUNC_WRAP_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\((.*)\)$", re.DOTALL)
_SOQL_SUBQUERY_RE = re.compile(r"^\(\s*(select\b.*)\)$", re.IGNORECASE | re.DOTALL)
_SOQL_LEADING_SELECT_RE = re.compile(r"^\s*select\b", re.IGNORECASE)


def _soql_strip_leading_select(query_text: str) -> str:
    """Remove the leading ``SELECT`` keyword captured alongside the query
    text so it is not mistaken for the first projected field/expression."""
    return _SOQL_LEADING_SELECT_RE.sub("", query_text, count=1)


def _soql_relationship_traversal_name(field) -> str | None:
    """Best-effort parent-relationship traversal name for a lookup/master-detail
    field, e.g. ``Account__r`` for a custom field ``Account__c``, or
    ``Account`` for the standard field ``AccountId``."""
    if not field.reference_to:
        return None
    api_name = field.api_name
    if api_name.endswith("__c"):
        return api_name[: -len("__c")] + "__r"
    if api_name.endswith("Id") and len(api_name) > 2:
        return api_name[: -len("Id")]
    return api_name


def _soql_top_level_from_span(query_text: str) -> tuple[int, int] | None:
    """Locate the ``FROM`` keyword that is not nested inside a parenthesized
    subquery (a child-relationship subselect)."""
    for match in _SOQL_FROM_RE.finditer(query_text):
        depth = query_text.count("(", 0, match.start()) - query_text.count(")", 0, match.start())
        if depth <= 0:
            return match.span()
    return None


def _soql_split_top_level_fields(select_clause: str) -> list[str]:
    """Split a SOQL SELECT field list on commas, ignoring commas nested
    inside subqueries or function calls (e.g. ``COUNT(Id)``)."""
    fields: list[str] = []
    depth = 0
    current: list[str] = []
    for char in select_clause:
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth = max(0, depth - 1)
            current.append(char)
        elif char == "," and depth == 0:
            fields.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        fields.append("".join(current).strip())
    return [f for f in fields if f]


def _extract_soql_subquery_field_usages(
    subquery_text: str, relationship_owners: dict[str, ObjectInfo]
) -> list[tuple[str, str]]:
    usages: list[tuple[str, str]] = []
    subquery_text = _soql_strip_leading_select(subquery_text)
    from_span = _soql_top_level_from_span(subquery_text)
    if not from_span:
        return usages

    select_clause = subquery_text[: from_span[0]]
    remainder = subquery_text[from_span[1]:].lstrip()
    rel_match = _SOQL_IDENTIFIER_RE.match(remainder)
    if not rel_match:
        return usages
    child_object = relationship_owners.get(rel_match.group(0).lower())
    if child_object is None:
        return usages

    child_fields_by_lower = {f.api_name.lower(): f.api_name for f in child_object.fields}
    for token in _soql_split_top_level_fields(select_clause):
        func_match = _SOQL_FUNC_WRAP_RE.match(token)
        inner = (func_match.group(1) if func_match else token).strip()
        if not inner or "." in inner or not _SOQL_IDENTIFIER_RE.fullmatch(inner):
            continue
        resolved = child_fields_by_lower.get(inner.lower())
        if resolved:
            usages.append((child_object.api_name, resolved))
    return usages


def _extract_soql_query_field_usages(
    query_text: str,
    objects_by_name: dict[str, ObjectInfo],
    relationship_owners: dict[str, ObjectInfo],
) -> list[tuple[str, str]]:
    usages: list[tuple[str, str]] = []
    query_text = _soql_strip_leading_select(query_text)
    from_span = _soql_top_level_from_span(query_text)
    if not from_span:
        return usages

    select_clause = query_text[: from_span[0]]
    remainder = query_text[from_span[1]:].lstrip()
    object_match = _SOQL_IDENTIFIER_RE.match(remainder)
    if not object_match:
        return usages
    main_object = objects_by_name.get(object_match.group(0).lower())
    if main_object is None:
        return usages

    main_fields_by_lower = {f.api_name.lower(): f.api_name for f in main_object.fields}

    for token in _soql_split_top_level_fields(select_clause):
        subquery_match = _SOQL_SUBQUERY_RE.match(token)
        if subquery_match:
            usages.extend(_extract_soql_subquery_field_usages(subquery_match.group(1), relationship_owners))
            continue

        func_match = _SOQL_FUNC_WRAP_RE.match(token)
        inner = (func_match.group(1) if func_match else token).strip()
        if not inner or not _SOQL_IDENTIFIER_RE.fullmatch(inner):
            continue

        parts = inner.split(".")
        field_part = parts[-1]
        relationship_parts = parts[:-1]

        if not relationship_parts:
            resolved = main_fields_by_lower.get(field_part.lower())
            if resolved:
                usages.append((main_object.api_name, resolved))
            continue

        # Best-effort parent-relationship traversal, one hop at a time
        # (e.g. ``Compte__r.Contact__r.Nom__c``).
        current_object = main_object
        resolved_ok = True
        for rel_part in relationship_parts:
            matched_field = next(
                (
                    f
                    for f in current_object.fields
                    if (_soql_relationship_traversal_name(f) or "").lower() == rel_part.lower()
                ),
                None,
            )
            if matched_field is None or not matched_field.reference_to:
                resolved_ok = False
                break
            next_object = objects_by_name.get(matched_field.reference_to[0].lower())
            if next_object is None:
                resolved_ok = False
                break
            current_object = next_object

        if resolved_ok:
            target_field = next(
                (f.api_name for f in current_object.fields if f.api_name.lower() == field_part.lower()),
                None,
            )
            if target_field:
                usages.append((current_object.api_name, target_field))

    return usages


def _extract_soql_field_usages(
    body: str,
    objects_by_name: dict[str, ObjectInfo],
    relationship_owners: dict[str, ObjectInfo],
) -> list[tuple[str, str]]:
    """Return the ``(ObjectApiName, FieldApiName)`` pairs referenced by any
    SOQL query found in ``body`` (an Apex class/trigger source), so that
    fields only ever used inside a SOQL projection are not flagged as
    orphans."""
    query_texts = [m.group(1) for m in _SOQL_BLOCK_RE.finditer(body)]
    query_texts += [m.group(1) for m in _SOQL_STRING_LITERAL_RE.finditer(body)]

    usages: list[tuple[str, str]] = []
    for query_text in query_texts:
        usages.extend(_extract_soql_query_field_usages(query_text, objects_by_name, relationship_owners))
    return usages
