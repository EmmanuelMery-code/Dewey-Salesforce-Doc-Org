"""SARIF 2.1.0 export of the static analyzer findings.

SARIF (Static Analysis Results Interchange Format) is the JSON format
consumed by GitHub Code Scanning, Azure DevOps, SonarQube and most CI
dashboards. This module converts an
:class:`~src.analyzer.engine.AnalyzerReport` into a single ``.sarif`` file so
a Dewey run can be wired into a CI pipeline alongside other static analysis
tools.

Reference: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from src.analyzer.models import Finding, Rule

if TYPE_CHECKING:
    from src.analyzer.engine import AnalyzerReport

SARIF_SCHEMA_URI = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/"
    "Schemata/sarif-schema-2.1.0.json"
)
SARIF_VERSION = "2.1.0"
TOOL_NAME = "Dewey"
TOOL_INFORMATION_URI = "https://github.com/EmmanuelMery-code/Dewey-Salesforce-Doc-Org"

# Dewey uses a 4-level severity scale; SARIF results only know
# error / warning / note / none. Critical and Major both map to "error" so
# CI gates that fail the build on "error" catch both.
_SEVERITY_TO_LEVEL: dict[str, str] = {
    "Critical": "error",
    "Major": "error",
    "Minor": "warning",
    "Info": "note",
}


def _severity_to_level(severity: str) -> str:
    return _SEVERITY_TO_LEVEL.get(severity, "warning")


def _artifact_uri(source_path: Path | None, source_root: Path | None) -> str | None:
    """Return a POSIX, repo-relative URI for ``source_path`` when possible."""
    if source_path is None:
        return None
    path = Path(source_path)
    if source_root is not None:
        try:
            path = path.resolve().relative_to(Path(source_root).resolve())
        except (ValueError, OSError):
            path = Path(source_path)
    return path.as_posix()


def _build_rule_descriptor(rule: Rule) -> dict:
    full_description = rule.description or rule.title or rule.id
    if rule.rationale:
        full_description = f"{full_description} {rule.rationale}".strip()
    descriptor: dict = {
        "id": rule.id,
        "name": rule.id,
        "shortDescription": {"text": rule.title or rule.id},
        "fullDescription": {"text": full_description},
        "defaultConfiguration": {"level": _severity_to_level(rule.severity)},
        "properties": {
            "severity": rule.severity,
            "category": rule.category,
            "subcategory": rule.subcategory,
            "source": rule.source,
            "tags": [tag for tag in (rule.category, rule.subcategory) if tag],
        },
    }
    if rule.remediation:
        descriptor["help"] = {"text": rule.remediation}
    if rule.reference:
        descriptor["helpUri"] = rule.reference
    return descriptor


def _build_result(
    finding: Finding, rule_index: dict[str, int], source_root: Path | None
) -> dict:
    result: dict = {
        "ruleId": finding.rule.id,
        "ruleIndex": rule_index[finding.rule.id],
        "level": _severity_to_level(finding.rule.severity),
        "message": {"text": finding.message or finding.rule.title or finding.rule.id},
        "properties": {
            "targetKind": finding.target_kind,
            "targetName": finding.target_name,
        },
    }
    if finding.details:
        result["properties"]["details"] = list(finding.details)

    uri = _artifact_uri(finding.source_path, source_root)
    if uri:
        location: dict = {"artifactLocation": {"uri": uri}}
        if finding.line:
            location["region"] = {"startLine": max(1, int(finding.line))}
        result["locations"] = [{"physicalLocation": location}]
    return result


def build_sarif_payload(
    analyzer_report: "AnalyzerReport",
    source_root: Path | str | None = None,
    tool_version: str = "1.0.0",
) -> dict:
    """Build the SARIF 2.1.0 JSON payload for an analyzer report.

    ``source_root`` (typically the Salesforce DX source directory) is used
    to turn each finding's absolute ``source_path`` into a repo-relative
    URI, which is what GitHub / Azure DevOps expect in order to correlate a
    result with a file in the checked-out repository.
    """
    root = Path(source_root).resolve() if source_root else None
    findings = analyzer_report.all_findings()

    rules: list[Rule] = []
    seen_rule_ids: set[str] = set()
    for finding in findings:
        if finding.rule.id not in seen_rule_ids:
            seen_rule_ids.add(finding.rule.id)
            rules.append(finding.rule)
    rules.sort(key=lambda rule: rule.id)
    rule_index = {rule.id: index for index, rule in enumerate(rules)}

    results = [_build_result(finding, rule_index, root) for finding in findings]

    return {
        "$schema": SARIF_SCHEMA_URI,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": TOOL_NAME,
                        "informationUri": TOOL_INFORMATION_URI,
                        "version": tool_version,
                        "rules": [_build_rule_descriptor(rule) for rule in rules],
                    }
                },
                "results": results,
            }
        ],
    }


def write_sarif_report(
    analyzer_report: "AnalyzerReport",
    output_path: Path | str,
    source_root: Path | str | None = None,
    tool_version: str = "1.0.0",
) -> Path:
    """Write the SARIF export of ``analyzer_report`` to ``output_path``."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_sarif_payload(
        analyzer_report, source_root=source_root, tool_version=tool_version
    )
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return output_path
