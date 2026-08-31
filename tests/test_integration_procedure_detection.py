"""Tests: Integration Procedures are detected through their `.oip` suffix.

The Metadata API suffix for OmniIntegrationProcedure is `.oip`, so a file is
named `<Name>.oip-meta.xml`. The `*.ip-meta.xml` glob previously used does not
match it, which left those components out of the customization metrics and out
of the dependency graph.
"""

from __future__ import annotations

from pathlib import Path

from src.parsers.salesforce_parser import SalesforceMetadataParser

INTEGRATION_PROCEDURE = """<?xml version="1.0" encoding="UTF-8"?>
<OmniIntegrationProcedure xmlns="http://soap.sforce.com/2006/04/metadata">
    <isActive>true</isActive>
    <name>GetAccountDetails</name>
    <propertySetConfig>{"remoteClass":"AccountService"}</propertySetConfig>
</OmniIntegrationProcedure>
"""

APEX_CLASS = """public with sharing class AccountService {
    public static void run() {}
}
"""


def _build_source(tmp_path: Path, *, suffix: str) -> Path:
    source = tmp_path / "source"
    procedures_dir = source / "omniIntegrationProcedures"
    procedures_dir.mkdir(parents=True, exist_ok=True)
    (procedures_dir / f"GetAccountDetails{suffix}.xml").write_text(
        INTEGRATION_PROCEDURE, encoding="utf-8"
    )
    classes_dir = source / "classes"
    classes_dir.mkdir(parents=True, exist_ok=True)
    (classes_dir / "AccountService.cls").write_text(APEX_CLASS, encoding="utf-8")
    return source


class TestIntegrationProcedureMetrics:
    def test_modern_oip_suffix_is_counted(self, tmp_path: Path) -> None:
        source = _build_source(tmp_path, suffix=".oip-meta")
        snapshot = SalesforceMetadataParser(source).parse()

        assert snapshot.metrics.omni_integration_procedures == 1

    def test_legacy_ip_suffix_is_still_counted(self, tmp_path: Path) -> None:
        source = _build_source(tmp_path, suffix=".ip-meta")
        snapshot = SalesforceMetadataParser(source).parse()

        assert snapshot.metrics.omni_integration_procedures == 1


class TestIntegrationProcedureDependencies:
    def test_apex_reference_is_recorded_for_the_oip_suffix(self, tmp_path: Path) -> None:
        source = _build_source(tmp_path, suffix=".oip-meta")
        snapshot = SalesforceMetadataParser(source).parse()

        matches = [
            dep
            for dep in snapshot.dependencies
            if dep.source_name == "GetAccountDetails"
            and dep.source_kind == "Omni"
            and dep.target_name == "AccountService"
            and dep.target_kind == "Apex"
        ]
        assert matches
