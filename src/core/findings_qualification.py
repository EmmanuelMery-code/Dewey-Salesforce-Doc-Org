"""Per-org storage of the TechLead's findings qualification columns (M..S).

Dewey exports the findings workbook with the qualification and US columns
empty; the TechLead fills them in Excel and re-imports the file so the work
is not lost on the next export.

Rows are matched on the component name (column E) and the rule id (column C).
That pair is not unique — a component can break the same rule several times —
so an *occurrence index* completes the key: the rank of the row among the
duplicates of its pair, following the row order of the file. The export order
is deterministic, so re-importing an untouched export yields the same keys.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from src.analyzer.models import Finding

STORE_FILENAME = "findings_qualifications.json"
_STORE_VERSION = 1

#: ``(component name, rule id, occurrence index)``.
QualificationKey = tuple[str, str, int]

#: Number of columns owned by the TechLead: M..P (qualification) + Q..S (US).
QUALIFICATION_FIELD_COUNT = 7

#: Bucket used for runs made without an org alias.
UNNAMED_ALIAS = "(sans alias)"


def store_alias(alias: str) -> str:
    """Key ``alias`` is stored under, shared by every reader and writer.

    Runs made without an alias all land in the same bucket, so the findings
    screen and the full-documentation run agree on where to look.
    """
    return (alias or "").strip() or UNNAMED_ALIAS


@dataclass(slots=True)
class FindingQualification:
    """The TechLead's own values for one finding row, in column order."""

    status: str = ""
    team: str = ""
    target_sprint: str = ""
    us_number: str = ""
    us_title: str = ""
    us_description: str = ""
    acceptance_criteria: str = ""

    def as_row(self) -> list[str]:
        """The seven values in workbook column order (M..S)."""
        return [
            self.status,
            self.team,
            self.target_sprint,
            self.us_number,
            self.us_title,
            self.us_description,
            self.acceptance_criteria,
        ]

    def is_empty(self) -> bool:
        return not any(self.as_row())

    @classmethod
    def from_row(cls, values: Sequence[object]) -> FindingQualification:
        """Build a qualification from raw cell values, in M..S order.

        Shorter sequences are padded, longer ones truncated, so a workbook
        with unexpected extra columns cannot break the import.
        """
        cleaned = [
            "" if value is None else str(value).strip() for value in values
        ]
        cleaned += [""] * (QUALIFICATION_FIELD_COUNT - len(cleaned))
        return cls(*cleaned[:QUALIFICATION_FIELD_COUNT])


def assign_keys(pairs: Iterable[tuple[str, str]]) -> list[QualificationKey]:
    """Turn ``(component, rule id)`` pairs into unique keys, order preserved.

    Duplicated pairs get an increasing occurrence index, which is what makes
    the key unique for a component breaking the same rule several times.
    """
    occurrences: dict[tuple[str, str], int] = {}
    keys: list[QualificationKey] = []
    for component, rule_id in pairs:
        pair = ((component or "").strip(), (rule_id or "").strip())
        index = occurrences.get(pair, 0)
        occurrences[pair] = index + 1
        keys.append((pair[0], pair[1], index))
    return keys


def finding_keys(findings: Sequence[Finding]) -> list[QualificationKey]:
    """Keys of ``findings`` in the order given, which must be the export order."""
    return assign_keys(
        (finding.target_name, finding.rule.id) for finding in findings
    )


def load_qualifications(
    store_path: str | Path,
) -> dict[str, dict[QualificationKey, FindingQualification]]:
    """Read the whole store, keyed by org alias then by finding key.

    An unreadable or malformed file yields an empty store rather than an
    error: losing qualifications is bad, but blocking the screen is worse,
    and the next import rewrites the file anyway.
    """
    try:
        payload = json.loads(Path(store_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}

    store: dict[str, dict[QualificationKey, FindingQualification]] = {}
    raw_orgs = payload.get("orgs")
    if not isinstance(raw_orgs, dict):
        return {}
    for alias, entries in raw_orgs.items():
        if not isinstance(entries, list):
            continue
        by_key: dict[QualificationKey, FindingQualification] = {}
        for entry in entries:
            parsed = _deserialize(entry)
            if parsed is not None:
                by_key[parsed[0]] = parsed[1]
        if by_key:
            store[str(alias)] = by_key
    return store


def save_qualifications(
    store_path: str | Path,
    store: Mapping[str, Mapping[QualificationKey, FindingQualification]],
) -> Path:
    """Write the whole store back, dropping empty qualifications."""
    path = Path(store_path)
    orgs: dict[str, list[dict]] = {}
    for alias, by_key in store.items():
        entries = [
            _serialize(key, qualification)
            for key, qualification in sorted(by_key.items())
            if not qualification.is_empty()
        ]
        if entries:
            orgs[alias] = entries

    payload = {"version": _STORE_VERSION, "orgs": orgs}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _serialize(key: QualificationKey, qualification: FindingQualification) -> dict:
    component, rule_id, occurrence = key
    return {
        "component": component,
        "rule": rule_id,
        "occurrence": occurrence,
        "status": qualification.status,
        "team": qualification.team,
        "target_sprint": qualification.target_sprint,
        "us_number": qualification.us_number,
        "us_title": qualification.us_title,
        "us_description": qualification.us_description,
        "acceptance_criteria": qualification.acceptance_criteria,
    }


def _deserialize(entry: object) -> tuple[QualificationKey, FindingQualification] | None:
    if not isinstance(entry, dict):
        return None
    component = str(entry.get("component") or "").strip()
    rule_id = str(entry.get("rule") or "").strip()
    if not component and not rule_id:
        return None
    try:
        occurrence = int(entry.get("occurrence") or 0)
    except (TypeError, ValueError):
        occurrence = 0

    qualification = FindingQualification(
        status=str(entry.get("status") or ""),
        team=str(entry.get("team") or ""),
        target_sprint=str(entry.get("target_sprint") or ""),
        us_number=str(entry.get("us_number") or ""),
        us_title=str(entry.get("us_title") or ""),
        us_description=str(entry.get("us_description") or ""),
        acceptance_criteria=str(entry.get("acceptance_criteria") or ""),
    )
    if qualification.is_empty():
        return None
    return (component, rule_id, occurrence), qualification
