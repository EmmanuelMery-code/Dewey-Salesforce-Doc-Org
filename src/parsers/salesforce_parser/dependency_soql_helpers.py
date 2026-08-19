"""SOQL-in-Apex field usage extraction, used by :mod:`dependencies_mixin`.

Best-effort, regex-based SOQL parsing (there is no real SOQL grammar here).
A field projected by a SOQL query (e.g. ``[SELECT Field__c FROM Object__c]``)
is only treated as "used" — and therefore excluded from orphan detection —
when the record(s) returned by that query are assigned to a variable (or an
implicit ``for`` loop variable) which is itself later accessed with that
field, e.g.::

    Account acc = [SELECT Name, CustomField__c FROM Account LIMIT 1];
    System.debug(acc.CustomField__c); // CustomField__c is used

    List<Account> accs = [SELECT Name, OtherField__c FROM Account];
    for (Account a : accs) { System.debug(a.Name); } // OtherField__c stays orphan

Merely projecting a field without reading it back through the assigned
variable is not enough. Handles the bracket literal syntax, static SOQL
string literals (e.g. passed to ``Database.query``), parent-relationship
traversal (``Rel__r.Field__c``) and one level of child-relationship
subqueries — in each case requiring the corresponding variable access to be
found elsewhere in the class body.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

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

# --- Root-variable resolution (what receives the query result) ------------

_SOQL_ROOT_VAR_FOR_LOOP_RE = re.compile(
    r"for\s*\(\s*[\w.$<>\[\],\s]+?\s+(\w+)\s*:\s*$", re.IGNORECASE
)
_SOQL_ROOT_VAR_ASSIGNMENT_RE = re.compile(r"(?:[\w.$<>\[\],\s]+?\s+)?(\w+)\s*=\s*$")
_SOQL_DATABASE_QUERY_CALL_RE = re.compile(r"Database\s*\.\s*query\s*\($", re.IGNORECASE)
_ROOT_VAR_LOOKUP_WINDOW = 200


@dataclass(frozen=True, slots=True)
class _SoqlFieldProjection:
    """One field projected by a SOQL query, plus enough context to verify
    it is genuinely read back from the query's result variable."""

    object_api_name: str
    field_api_name: str
    access_path: tuple[str, ...]
    is_child_relationship: bool


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
) -> list[tuple[str, str, str]]:
    """Return ``(ObjectApiName, FieldApiName, ChildRelationshipAsWritten)``
    for each field projected by a child-relationship subquery."""
    usages: list[tuple[str, str, str]] = []
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
            usages.append((child_object.api_name, resolved, rel_match.group(0)))
    return usages


def _extract_soql_query_field_usages(
    query_text: str,
    objects_by_name: dict[str, ObjectInfo],
    relationship_owners: dict[str, ObjectInfo],
) -> list[_SoqlFieldProjection]:
    """Return every field projected by ``query_text`` (main object, parent
    traversals and child subqueries), without checking whether it is
    actually read back from the query's result variable — that check
    happens in :func:`_extract_soql_field_usages`, which has access to the
    surrounding Apex source."""
    usages: list[_SoqlFieldProjection] = []
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
            for obj_name, field_name, child_rel in _extract_soql_subquery_field_usages(
                subquery_match.group(1), relationship_owners
            ):
                usages.append(_SoqlFieldProjection(obj_name, field_name, (child_rel, field_name), True))
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
                usages.append(_SoqlFieldProjection(main_object.api_name, resolved, (resolved,), False))
            continue

        # Best-effort parent-relationship traversal, one hop at a time
        # (e.g. ``Compte__r.Contact__r.Nom__c``).
        current_object = main_object
        traversal_path: list[str] = []
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
            traversal_path.append(_soql_relationship_traversal_name(matched_field))
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
                usages.append(
                    _SoqlFieldProjection(
                        current_object.api_name, target_field, (*traversal_path, target_field), False
                    )
                )

    return usages


def _soql_resolve_root_variable(body: str, value_start: int) -> str | None:
    """Best-effort detection of the variable a query result is assigned to
    (declaration, plain re-assignment, or the implicit iteration variable
    of a ``for`` loop), by inspecting the source text immediately preceding
    the "value" at ``value_start`` (a bracket-literal query, or a
    ``Database.query(`` call, in ``body``)."""
    prefix = body[max(0, value_start - _ROOT_VAR_LOOKUP_WINDOW) : value_start]

    match = _SOQL_ROOT_VAR_FOR_LOOP_RE.search(prefix)
    if match:
        return match.group(1)

    match = _SOQL_ROOT_VAR_ASSIGNMENT_RE.search(prefix)
    if match:
        return match.group(1)

    return None


def _soql_resolve_root_variable_for_string_literal(body: str, literal_start: int) -> str | None:
    """Same as :func:`_soql_resolve_root_variable`, for a SOQL query
    embedded in a string literal. Handles the literal being passed directly
    to ``Database.query('...')``, or first assigned to a variable that is
    later passed to ``Database.query(thatVariable)``."""
    call_window_start = max(0, literal_start - 60)
    call_match = _SOQL_DATABASE_QUERY_CALL_RE.search(body[call_window_start:literal_start])
    if call_match:
        return _soql_resolve_root_variable(body, call_window_start + call_match.start())

    assign_match = _SOQL_ROOT_VAR_ASSIGNMENT_RE.search(
        body[max(0, literal_start - _ROOT_VAR_LOOKUP_WINDOW) : literal_start]
    )
    if not assign_match:
        return None

    query_string_var = assign_match.group(1)
    call_re = re.compile(
        r"Database\s*\.\s*query\s*\(\s*" + re.escape(query_string_var) + r"\s*\)", re.IGNORECASE
    )
    call_match = call_re.search(body)
    if not call_match:
        return None
    return _soql_resolve_root_variable(body, call_match.start())


def _soql_variable_reference_pattern(var_name: str) -> str:
    """Regex fragment matching a bare variable reference, optionally
    indexed (e.g. ``accs[0]``)."""
    return re.escape(var_name) + r"(?:\s*\[\s*[^\]\[]+\s*\])?"


def _soql_dotted_path_used(body: str, root_pattern: str, path: tuple[str, ...]) -> bool:
    """Search for ``root_pattern.path[0].path[1]...`` in ``body``, allowing
    optional list indexing (``[0]``) after any segment — including the
    root — since each hop of a relationship/collection traversal may be
    indexed independently (e.g. ``c[0].Contacts__r[0].Email__c``)."""
    optional_index = r"(?:\s*\[\s*[^\]\[]+\s*\])?"
    segments_pattern = (r"\s*\.\s*").join(re.escape(segment) + optional_index for segment in path)
    pattern = re.compile(root_pattern + r"\s*\.\s*" + segments_pattern + r"\b", re.IGNORECASE)
    return bool(pattern.search(body))


def _soql_loop_variables_over(body: str, source_pattern: str) -> list[str]:
    """``for (Type loopVar : <source_pattern>)`` loop variables iterating
    over an expression matching ``source_pattern``."""
    pattern = re.compile(
        r"for\s*\(\s*[\w.$<>\[\],\s]+?\s+(\w+)\s*:\s*" + source_pattern + r"\s*\)",
        re.IGNORECASE,
    )
    return [m.group(1) for m in pattern.finditer(body)]


def _soql_variable_uses_field(body: str, root_var: str, projection: _SoqlFieldProjection) -> bool:
    """Best-effort check that the record(s) held by ``root_var`` (the
    variable/loop-var the SOQL result was assigned to) are actually
    accessed with the projected field somewhere in the class, rather than
    merely projected. Handles one level of list iteration/indexing, and
    (for child-relationship subqueries) one further level of nested
    iteration/indexing over the relationship."""
    root_pattern = _soql_variable_reference_pattern(root_var)

    if not projection.is_child_relationship:
        if _soql_dotted_path_used(body, root_pattern, projection.access_path):
            return True
        for loop_var in _soql_loop_variables_over(body, root_pattern):
            if _soql_dotted_path_used(body, _soql_variable_reference_pattern(loop_var), projection.access_path):
                return True
        return False

    child_relationship, field_name = projection.access_path
    for candidate in (root_var, *_soql_loop_variables_over(body, root_pattern)):
        candidate_pattern = _soql_variable_reference_pattern(candidate)
        if _soql_dotted_path_used(body, candidate_pattern, (child_relationship, field_name)):
            return True
        child_collection_pattern = candidate_pattern + r"\s*\.\s*" + re.escape(child_relationship)
        for nested_loop_var in _soql_loop_variables_over(body, child_collection_pattern):
            if _soql_dotted_path_used(body, _soql_variable_reference_pattern(nested_loop_var), (field_name,)):
                return True
    return False


def _extract_soql_field_usages(
    body: str,
    objects_by_name: dict[str, ObjectInfo],
    relationship_owners: dict[str, ObjectInfo],
) -> list[tuple[str, str]]:
    """Return the ``(ObjectApiName, FieldApiName)`` pairs genuinely used
    from any SOQL query found in ``body`` (an Apex class/trigger source):
    the field must be both projected by the query *and* read back through
    the variable (or loop variable) the query result was assigned to —
    projection alone no longer counts, so a field selected but never
    actually accessed is still flagged as orphan."""
    usages: list[tuple[str, str]] = []

    for match in _SOQL_BLOCK_RE.finditer(body):
        root_var = _soql_resolve_root_variable(body, match.start())
        if not root_var:
            continue
        for projection in _extract_soql_query_field_usages(match.group(1), objects_by_name, relationship_owners):
            if _soql_variable_uses_field(body, root_var, projection):
                usages.append((projection.object_api_name, projection.field_api_name))

    for match in _SOQL_STRING_LITERAL_RE.finditer(body):
        root_var = _soql_resolve_root_variable_for_string_literal(body, match.start())
        if not root_var:
            continue
        for projection in _extract_soql_query_field_usages(match.group(1), objects_by_name, relationship_owners):
            if _soql_variable_uses_field(body, root_var, projection):
                usages.append((projection.object_api_name, projection.field_api_name))

    return usages
