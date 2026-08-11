"""Tests for the SARIF 2.1.0 export of analyzer findings."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.analyzer.engine import AnalyzerReport
from src.analyzer.models import Finding, Rule
from src.reporting.sarif_writer import build_sarif_payload, write_sarif_report


def _rule(
    rule_id: str = "APEX-PERF-003",
    severity: str = "Critical",
    **overrides,
) -> Rule:
    defaults = dict(
        id=rule_id,
        enabled=True,
        scope="apex_class",
        category="Easy",
        subcategory="Efficiency",
        severity=severity,
        source="PMD OperationWithLimitsInLoop",
        reference="https://example.com/rule",
        title="Callout HTTP potentiellement execute dans une boucle",
        description="Une instance Http/HttpRequest est construite dans une boucle.",
        rationale="Les limites Apex plafonnent a 100 callouts par transaction.",
        remediation="Sortir le callout de la boucle.",
    )
    defaults.update(overrides)
    return Rule(**defaults)


class TestBuildSarifPayload:
    def test_empty_report_has_no_results_and_valid_shell(self) -> None:
        report = AnalyzerReport()
        payload = build_sarif_payload(report)

        assert payload["version"] == "2.1.0"
        assert payload["$schema"].endswith("sarif-schema-2.1.0.json")
        run = payload["runs"][0]
        assert run["tool"]["driver"]["name"] == "Dewey"
        assert run["tool"]["driver"]["rules"] == []
        assert run["results"] == []

    def test_finding_is_mapped_to_a_result_with_expected_fields(self, tmp_path: Path) -> None:
        source_file = tmp_path / "force-app" / "main" / "default" / "classes" / "Foo.cls"
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_text("public class Foo {}", encoding="utf-8")

        rule = _rule()
        finding = Finding(
            rule=rule,
            target_kind="ApexClass",
            target_name="Foo",
            message="Un callout HTTP apparait potentiellement dans une boucle.",
            details=["Ligne 42"],
            source_path=source_file,
            line=42,
        )
        report = AnalyzerReport(apex={"Foo": [finding]})

        payload = build_sarif_payload(report, source_root=tmp_path)
        run = payload["runs"][0]

        assert len(run["tool"]["driver"]["rules"]) == 1
        rule_descriptor = run["tool"]["driver"]["rules"][0]
        assert rule_descriptor["id"] == "APEX-PERF-003"
        assert rule_descriptor["defaultConfiguration"]["level"] == "error"
        assert rule_descriptor["help"]["text"] == rule.remediation
        assert rule_descriptor["helpUri"] == rule.reference

        assert len(run["results"]) == 1
        result = run["results"][0]
        assert result["ruleId"] == "APEX-PERF-003"
        assert result["ruleIndex"] == 0
        assert result["level"] == "error"
        assert result["message"]["text"] == finding.message
        assert result["properties"]["targetKind"] == "ApexClass"
        assert result["properties"]["targetName"] == "Foo"
        assert result["properties"]["details"] == ["Ligne 42"]

        location = result["locations"][0]["physicalLocation"]
        assert location["artifactLocation"]["uri"] == "force-app/main/default/classes/Foo.cls"
        assert location["region"]["startLine"] == 42

    def test_finding_without_source_path_has_no_locations(self) -> None:
        finding = Finding(
            rule=_rule(rule_id="SEC-001", severity="Minor"),
            target_kind="Profile",
            target_name="Admin",
            message="Profil trop permissif.",
        )
        report = AnalyzerReport(security={"Admin": [finding]})

        payload = build_sarif_payload(report)
        result = payload["runs"][0]["results"][0]

        assert "locations" not in result
        assert result["level"] == "warning"

    def test_duplicate_rule_is_declared_once_and_shared_by_index(self) -> None:
        rule = _rule(rule_id="APEX-PERF-003")
        findings = [
            Finding(rule=rule, target_kind="ApexClass", target_name="Foo"),
            Finding(rule=rule, target_kind="ApexClass", target_name="Bar"),
        ]
        report = AnalyzerReport(apex={"Foo": [findings[0]], "Bar": [findings[1]]})

        payload = build_sarif_payload(report)
        run = payload["runs"][0]

        assert len(run["tool"]["driver"]["rules"]) == 1
        assert len(run["results"]) == 2
        assert {r["ruleIndex"] for r in run["results"]} == {0}

    @pytest.mark.parametrize(
        ("severity", "expected_level"),
        [
            ("Critical", "error"),
            ("Major", "error"),
            ("Minor", "warning"),
            ("Info", "note"),
        ],
    )
    def test_severity_mapping(self, severity: str, expected_level: str) -> None:
        finding = Finding(
            rule=_rule(rule_id=f"RULE-{severity}", severity=severity),
            target_kind="ApexClass",
            target_name="Foo",
        )
        report = AnalyzerReport(apex={"Foo": [finding]})

        payload = build_sarif_payload(report)
        result = payload["runs"][0]["results"][0]
        assert result["level"] == expected_level


class TestWriteSarifReport:
    def test_writes_valid_json_file(self, tmp_path: Path) -> None:
        finding = Finding(
            rule=_rule(),
            target_kind="ApexClass",
            target_name="Foo",
        )
        report = AnalyzerReport(apex={"Foo": [finding]})
        output_path = tmp_path / "out" / "dewey.sarif"

        result_path = write_sarif_report(report, output_path, source_root=tmp_path)

        assert result_path == output_path
        assert output_path.exists()
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["version"] == "2.1.0"
        assert len(payload["runs"][0]["results"]) == 1
