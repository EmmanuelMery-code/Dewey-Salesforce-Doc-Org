"""Scan a :class:`MetadataSnapshot` for AI usage tags.

Holds the :class:`AIUsageEntry` result type plus the pure tag-matching
helpers and the :func:`scan_ai_usage` entry point. Split out of
:mod:`ai_usage` to keep that module under the repo's 500-line convention;
the customisation-universe helpers (with/without tag population) live in
the sibling :mod:`ai_usage_universe` module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.models import MetadataSnapshot


@dataclass(slots=True)
class AIUsageEntry:
    """One element flagged as AI-assisted.

    ``element_type`` is a short, human-readable category (``"Field"``,
    ``"ApexClass"``...) that the detail page renders as-is. ``element_name``
    points to the unique identifier of the element (e.g. ``"Account.Foo__c"``
    for fields). ``tag`` is the matched tag value, kept exactly as it was
    written in the metadata so users can spot typos. ``source`` and
    ``line_number`` help the reader open the right file. ``excerpt`` is the
    full line where the tag was found, trimmed of leading/trailing
    whitespace.
    """

    element_type: str
    element_name: str
    tag: str
    source: str = ""
    line_number: int | None = None
    excerpt: str = ""
    location: str = ""


# ---------------------------------------------------------------------------
# Tag matching helpers
# ---------------------------------------------------------------------------


def _match_tags(text: str, tags: list[str]) -> list[tuple[int, str, str]]:
    """Return ``(line_number, matched_tag, line_text)`` triples found in ``text``.

    Matching is case-insensitive and operates line by line; a single line may
    yield several entries when it carries more than one configured tag. The
    matched tag is the value as configured (preserving the user-chosen case)
    so the report stays consistent across descriptions written with mixed
    capitalisation.
    """

    if not text or not tags:
        return []

    matches: list[tuple[int, str, str]] = []
    lowered_tags = [(tag, tag.casefold()) for tag in tags if tag]
    for index, line in enumerate(text.splitlines(), start=1):
        haystack = line.casefold()
        for tag, lowered in lowered_tags:
            if lowered and lowered in haystack:
                matches.append((index, tag, line.strip()))
    return matches


def _extract_apex_comments(body: str) -> list[tuple[int, str]]:
    """Return ``(line_number, comment_text)`` for every Apex comment line.

    Tracks block-comment state across lines so multi-line ``/* ... */``
    blocks are correctly captured, including javadoc-style ``/** ... */``
    markers used for headers. Single-line ``//`` comments (full-line or
    trailing) are also captured. Strings are not pre-stripped: tags inside
    string literals would not normally collide with the configured markers
    (which start with ``@``).
    """

    if not body:
        return []

    comments: list[tuple[int, str]] = []
    in_block = False
    for index, line in enumerate(body.splitlines(), start=1):
        cursor = 0
        n = len(line)
        buffer: list[str] = []
        while cursor < n:
            ch = line[cursor]
            nxt = line[cursor + 1] if cursor + 1 < n else ""
            if in_block:
                end = line.find("*/", cursor)
                if end == -1:
                    buffer.append(line[cursor:])
                    cursor = n
                else:
                    buffer.append(line[cursor:end])
                    cursor = end + 2
                    in_block = False
            elif ch == "/" and nxt == "/":
                buffer.append(line[cursor + 2 :])
                cursor = n
            elif ch == "/" and nxt == "*":
                in_block = True
                cursor += 2
            elif ch in ('"', "'"):
                quote = ch
                cursor += 1
                while cursor < n:
                    if line[cursor] == "\\" and cursor + 1 < n:
                        cursor += 2
                    elif line[cursor] == quote:
                        cursor += 1
                        break
                    else:
                        cursor += 1
            else:
                cursor += 1
        comment_text = " ".join(part.strip() for part in buffer if part.strip())
        if comment_text:
            comments.append((index, comment_text))
    return comments


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_ai_usage(
    snapshot: MetadataSnapshot,
    tags: list[str] | tuple[str, ...] | None,
) -> list[AIUsageEntry]:
    """Walk the metadata snapshot and return every AI-tagged element.

    Returned entries are sorted by element type then element name to keep
    the rendered table stable across runs (and easier to diff across
    releases).
    """

    if not tags:
        return []

    tag_list = [t for t in tags if isinstance(t, str) and t.strip()]
    if not tag_list:
        return []

    entries: list[AIUsageEntry] = []

    def _emit_from_text(
        element_type: str,
        element_name: str,
        text: str,
        source_path: Path | None,
        location: str = "",
    ) -> None:
        for line_number, tag, line_text in _match_tags(text, tag_list):
            entries.append(
                AIUsageEntry(
                    element_type=element_type,
                    element_name=element_name,
                    tag=tag,
                    source=str(source_path) if source_path else "",
                    line_number=line_number,
                    excerpt=line_text,
                    location=location or "description",
                )
            )

    for obj in snapshot.objects:
        _emit_from_text(
            "Object",
            obj.api_name,
            obj.description,
            obj.source_path,
            "object description",
        )
        for field_info in obj.fields:
            _emit_from_text(
                "Field",
                f"{obj.api_name}.{field_info.api_name}",
                field_info.description,
                obj.source_path,
                "field description",
            )
        for record_type in obj.record_types:
            _emit_from_text(
                "RecordType",
                f"{obj.api_name}.{record_type.full_name}",
                record_type.description,
                obj.source_path,
                "record type description",
            )
        for validation_rule in obj.validation_rules:
            _emit_from_text(
                "ValidationRule",
                f"{obj.api_name}.{validation_rule.full_name}",
                validation_rule.description,
                obj.source_path,
                "validation rule description",
            )

    for flow in snapshot.flows:
        _emit_from_text(
            "Flow",
            flow.name,
            flow.description,
            flow.source_path,
            "flow description",
        )
        for element in flow.elements:
            _emit_from_text(
                "FlowElement",
                f"{flow.name}.{element.name or element.label or element.element_type}",
                element.description,
                flow.source_path,
                f"flow element {element.element_type}",
            )

    for profile in snapshot.profiles:
        _emit_from_text(
            "Profile",
            profile.name,
            profile.description,
            profile.source_path,
            "profile description",
        )

    for permission_set in snapshot.permission_sets:
        _emit_from_text(
            "PermissionSet",
            permission_set.name,
            permission_set.description,
            permission_set.source_path,
            "permission set description",
        )

    for artifact in snapshot.apex_artifacts:
        if artifact.kind == "trigger":
            element_type = "ApexTrigger"
        elif artifact.is_test:
            element_type = "ApexClass (Test)"
        else:
            element_type = "ApexClass"

        for line_number, comment_text in _extract_apex_comments(artifact.body):
            for line_idx, tag, line_text in _match_tags(comment_text, tag_list):
                # ``_match_tags`` may split a multi-segment comment back into
                # several lines; in our case ``comment_text`` is already a
                # single logical line so ``line_idx`` is always 1 and we keep
                # the original ``line_number`` from the source body.
                _ = line_idx
                entries.append(
                    AIUsageEntry(
                        element_type=element_type,
                        element_name=artifact.name,
                        tag=tag,
                        source=str(artifact.source_path),
                        line_number=line_number,
                        excerpt=line_text,
                        location="apex comment",
                    )
                )

    entries.sort(
        key=lambda entry: (
            entry.element_type.casefold(),
            entry.element_name.casefold(),
            entry.line_number or 0,
            entry.tag.casefold(),
        )
    )
    return entries


def count_unique_elements(entries: list[AIUsageEntry]) -> int:
    """Count the number of distinct (element_type, element_name) pairs.

    The index card displays this aggregated value: a single field with two
    tags should count once, not twice.
    """

    return len({(entry.element_type, entry.element_name) for entry in entries})
