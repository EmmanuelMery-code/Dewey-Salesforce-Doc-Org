"""Persist the findings of the documentation runs, one cache per org.

The analyzer report only lives in memory for the duration of a run, but the
findings qualification screen must stay usable after the application is
closed and reopened, and for any org already analysed — not just the last
one. This module stores a flat JSON snapshot of the findings (rule
definition included, so the workbook stays faithful even if ``rules.xml``
changes afterwards) as one file per org alias.

The cache is also the org's *memory*: it is not replaced by each run but
merged with it. A finding the analyzer stops reporting stays in the file,
flagged as resolved, so later documents keep exporting it — with the
qualification it was given — instead of making it vanish silently.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, fields
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Collection, Iterable, Sequence

from src.analyzer.models import Finding, Rule
from src.core.findings_qualification import (
    QualificationKey,
    finding_keys,
    finding_sort_key,
    sort_findings,
)

if TYPE_CHECKING:
    from src.analyzer.engine import AnalyzerReport

#: Single-file cache written by older versions, still read on startup so an
#: existing install does not lose the findings of its last run.
CACHE_FILENAME = "last_findings.json"
#: Directory holding one ``<alias>.json`` cache per analysed org.
CACHE_DIRNAME = "findings_cache"
_CACHE_VERSION = 1

_RULE_FIELDS = {field.name for field in fields(Rule)}

_INVALID_FILENAME_CHARS_RE = re.compile(r"[^A-Za-z0-9_-]+")


@dataclass(slots=True)
class CachedFindings:
    """Everything known about an org, along with the context to label it.

    ``findings`` is in the canonical export order and holds the whole
    history, not just the last run; ``resolved_keys`` tells which of those
    the analyzer no longer reports.
    """

    findings: list[Finding]
    alias: str = ""
    generated_at: date | None = None
    resolved_keys: set[QualificationKey] = field(default_factory=set)


def merge_history(
    current: Sequence[Finding], history: Sequence[Finding]
) -> tuple[list[Finding], set[QualificationKey]]:
    """Merge a fresh run into what was already known about the org.

    Returns the findings to export, in canonical order, and the keys of the
    ones only ``history`` knows about. The latter are kept on purpose: a
    finding that disappears has been fixed, and the document must say so
    rather than drop the row and the qualification attached to it.

    A finding that comes back is simply detected again, which clears its
    resolved flag.
    """
    detected = sort_findings(current)
    detected_keys = set(finding_keys(detected))

    previous = sort_findings(history)
    gone = [
        finding
        for finding, key in zip(previous, finding_keys(previous))
        if key not in detected_keys
    ]
    if not gone:
        return detected, set()

    # Appending before sorting keeps the resolved findings behind the
    # detected ones sharing their sort key, so the occurrence indexes of the
    # detected findings — hence the keys their qualifications are filed
    # under — do not move.
    merged = sort_findings([*detected, *gone])
    gone_ids = {id(finding) for finding in gone}
    resolved = {
        key
        for key, finding in zip(finding_keys(merged), merged)
        if id(finding) in gone_ids
    }
    return merged, resolved


def adopt_findings(
    known: Sequence[Finding], additions: Sequence[Finding]
) -> list[Finding]:
    """``known`` findings plus ``additions``, which come from outside a run.

    Additions are rebuilt from a reviewed workbook, so their rule is only as
    good as the columns that were exported. A rule Dewey still knows about
    is substituted for it: the severity it carries drives the row order, and
    reusing it is what keeps an addition *behind* the existing occurrences
    of the same component and rule — hence what keeps the keys of the
    existing qualifications on the rows they were filed for.
    """
    rules = {finding.rule.id: finding.rule for finding in known}
    for finding in additions:
        finding.rule = rules.get(finding.rule.id, finding.rule)
    return sort_findings([*known, *additions])


def findings_cache_path(base_dir: str | Path, alias: str) -> Path:
    """Cache file of ``alias`` inside ``base_dir``.

    Aliases are slugified because they end up in a filename; an empty or
    fully non-alphanumeric alias falls back to ``org`` so runs made without
    an alias still get a cache instead of silently losing their findings.
    """
    slug = _INVALID_FILENAME_CHARS_RE.sub("_", alias or "").strip("_") or "org"
    return Path(base_dir) / CACHE_DIRNAME / f"{slug}.json"


def load_all_findings_caches(base_dir: str | Path) -> dict[str, CachedFindings]:
    """Every cached run in ``base_dir``, keyed by the alias it was run for.

    The legacy single-file cache is read too, but never overrides a per-alias
    cache for the same org since that one is at least as recent.
    """
    base = Path(base_dir)
    found: dict[str, CachedFindings] = {}
    cache_dir = base / CACHE_DIRNAME
    if cache_dir.is_dir():
        for path in sorted(cache_dir.glob("*.json")):
            cached = load_findings_cache(path)
            if cached is not None:
                found[cached.alias] = cached

    legacy = load_findings_cache(base / CACHE_FILENAME)
    if legacy is not None:
        found.setdefault(legacy.alias, legacy)
    return found


def save_findings_cache(
    analyzer_report: "AnalyzerReport | None",
    cache_path: str | Path,
    *,
    alias: str = "",
) -> Path | None:
    """Merge the findings of ``analyzer_report`` into the cache at ``cache_path``.

    Findings the run no longer reports are kept and flagged as resolved,
    which is what makes the org's findings document remember its past.
    """
    if analyzer_report is None:
        return None
    previous = load_findings_cache(cache_path)
    findings, resolved = merge_history(
        analyzer_report.all_findings(), previous.findings if previous else []
    )
    return write_findings_cache(
        findings, cache_path, alias=alias, resolved_keys=resolved
    )


def write_findings_cache(
    findings: Iterable[Finding],
    cache_path: str | Path,
    *,
    alias: str = "",
    generated_at: date | None = None,
    resolved_keys: Collection[QualificationKey] = (),
) -> Path:
    """Write ``findings`` and their resolved flags to ``cache_path``.

    Used directly when the findings do not come from a run — the findings
    screen adds the rows an imported workbook knows about and Dewey does
    not — and by :func:`save_findings_cache` once it has merged.
    """
    path = Path(cache_path)
    ordered = sort_findings(list(findings))
    resolved = set(resolved_keys)
    payload = {
        "version": _CACHE_VERSION,
        "alias": alias,
        "generated_at": (generated_at or date.today()).isoformat(),
        "findings": [
            _serialize(finding, key in resolved)
            for finding, key in zip(ordered, finding_keys(ordered))
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def load_findings_cache(cache_path: str | Path) -> CachedFindings | None:
    """Read back a cache written by :func:`write_findings_cache`.

    Returns ``None`` when the file is missing, unreadable or empty, so
    callers can fall back to asking the user for a fresh generation.
    """
    path = Path(cache_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None

    entries = [
        (finding, bool(isinstance(item, dict) and item.get("resolved")))
        for item in payload.get("findings") or []
        if (finding := _deserialize(item)) is not None
    ]
    if not entries:
        return None
    # Caches written before the history existed follow the analyzer order,
    # so the flags are re-attached to their finding before the list is put
    # back in the canonical order the keys are computed from.
    entries.sort(key=lambda entry: finding_sort_key(entry[0]))

    findings = [finding for finding, _resolved in entries]
    return CachedFindings(
        findings=findings,
        alias=str(payload.get("alias") or ""),
        generated_at=_parse_date(payload.get("generated_at")),
        resolved_keys={
            key
            for key, (_finding, resolved) in zip(finding_keys(findings), entries)
            if resolved
        },
    )


def _serialize(finding: Finding, resolved: bool = False) -> dict:
    return {
        "rule": asdict(finding.rule),
        "target_kind": finding.target_kind,
        "target_name": finding.target_name,
        "message": finding.message,
        "details": list(finding.details),
        "source_path": str(finding.source_path) if finding.source_path else None,
        "line": finding.line,
        "resolved": resolved,
    }


def _deserialize(item: object) -> Finding | None:
    if not isinstance(item, dict):
        return None
    raw_rule = item.get("rule")
    if not isinstance(raw_rule, dict) or not raw_rule.get("id"):
        return None
    rule_kwargs = {key: value for key, value in raw_rule.items() if key in _RULE_FIELDS}
    try:
        rule = Rule(**rule_kwargs)
    except TypeError:
        return None
    source_path = item.get("source_path")
    return Finding(
        rule=rule,
        target_kind=str(item.get("target_kind") or ""),
        target_name=str(item.get("target_name") or ""),
        message=str(item.get("message") or ""),
        details=[str(detail) for detail in item.get("details") or []],
        source_path=Path(source_path) if source_path else None,
        line=item.get("line"),
    )


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None
