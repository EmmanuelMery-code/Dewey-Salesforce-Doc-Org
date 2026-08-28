"""Persist the findings of the documentation runs, one cache per org.

The analyzer report only lives in memory for the duration of a run, but the
findings qualification screen must stay usable after the application is
closed and reopened, and for any org already analysed — not just the last
one. This module stores a flat JSON snapshot of the findings (rule
definition included, so the workbook stays faithful even if ``rules.xml``
changes afterwards) as one file per org alias.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from src.analyzer.models import Finding, Rule

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
    """Findings of a past run, along with the context needed to label them."""

    findings: list[Finding]
    alias: str = ""
    generated_at: date | None = None


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
    """Write the findings of ``analyzer_report`` to ``cache_path``."""
    if analyzer_report is None:
        return None
    path = Path(cache_path)
    payload = {
        "version": _CACHE_VERSION,
        "alias": alias,
        "generated_at": date.today().isoformat(),
        "findings": [_serialize(finding) for finding in analyzer_report.all_findings()],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def load_findings_cache(cache_path: str | Path) -> CachedFindings | None:
    """Read back a cache written by :func:`save_findings_cache`.

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

    findings = [
        finding
        for item in payload.get("findings") or []
        if (finding := _deserialize(item)) is not None
    ]
    if not findings:
        return None
    return CachedFindings(
        findings=findings,
        alias=str(payload.get("alias") or ""),
        generated_at=_parse_date(payload.get("generated_at")),
    )


def _serialize(finding: Finding) -> dict:
    return {
        "rule": asdict(finding.rule),
        "target_kind": finding.target_kind,
        "target_name": finding.target_name,
        "message": finding.message,
        "details": list(finding.details),
        "source_path": str(finding.source_path) if finding.source_path else None,
        "line": finding.line,
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
