"""Tests: a Flow called as a Subflow by another Flow must not be an orphan.

Contract tested:
  _FlowsMixin()._parse_flows(folder) -> list[FlowInfo]
    .called_flow_names collects the <flowName> of every <subflows> element.

  SalesforceMetadataParser(...).parse() -> MetadataSnapshot
    snapshot.orphans does not contain a Flow that is referenced via a
    Subflow element, but still contains a genuinely unreferenced Flow.
"""

from __future__ import annotations

from pathlib import Path

from src.core.models import FlowInfo
from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.parsers.salesforce_parser.flows_mixin import _FlowsMixin


FLOW_WITH_SUBFLOW_CALL = """<?xml version="1.0" encoding="UTF-8"?>
<Flow xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>60.0</apiVersion>
    <label>Parent Flow</label>
    <processType>AutoLaunchedFlow</processType>
    <status>Active</status>
    <start>
        <connector>
            <targetReference>Call_Subflow</targetReference>
        </connector>
    </start>
    <subflows>
        <name>Call_Subflow</name>
        <label>Call Subflow</label>
        <flowName>Called_Subflow</flowName>
    </subflows>
</Flow>
"""

FLOW_WITH_TWO_SUBFLOW_CALLS = """<?xml version="1.0" encoding="UTF-8"?>
<Flow xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>60.0</apiVersion>
    <label>Parent Flow Two Calls</label>
    <processType>AutoLaunchedFlow</processType>
    <status>Active</status>
    <start>
        <connector>
            <targetReference>Call_First_Subflow</targetReference>
        </connector>
    </start>
    <subflows>
        <name>Call_First_Subflow</name>
        <label>Call First Subflow</label>
        <flowName>First_Subflow</flowName>
        <connector>
            <targetReference>Call_Second_Subflow</targetReference>
        </connector>
    </subflows>
    <subflows>
        <name>Call_Second_Subflow</name>
        <label>Call Second Subflow</label>
        <flowName>Second_Subflow</flowName>
    </subflows>
</Flow>
"""

FLOW_WITHOUT_SUBFLOW_CALL = """<?xml version="1.0" encoding="UTF-8"?>
<Flow xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>60.0</apiVersion>
    <label>No Subflow Here</label>
    <processType>AutoLaunchedFlow</processType>
    <status>Active</status>
    <start>
        <connector>
            <targetReference>Do_Nothing</targetReference>
        </connector>
    </start>
    <assignments>
        <name>Do_Nothing</name>
        <label>Do Nothing</label>
    </assignments>
</Flow>
"""

SUBFLOW_TARGET = """<?xml version="1.0" encoding="UTF-8"?>
<Flow xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>60.0</apiVersion>
    <label>Called Subflow</label>
    <processType>AutoLaunchedFlow</processType>
    <status>Active</status>
    <start>
        <connector>
            <targetReference>Do_Nothing</targetReference>
        </connector>
    </start>
    <assignments>
        <name>Do_Nothing</name>
        <label>Do Nothing</label>
    </assignments>
</Flow>
"""


def _parse_single_flow(tmp_path: Path, filename: str, content: str) -> FlowInfo:
    flows_dir = tmp_path / "flows"
    flows_dir.mkdir(parents=True, exist_ok=True)
    (flows_dir / f"{filename}.flow-meta.xml").write_text(content, encoding="utf-8")
    flows = _FlowsMixin()._parse_flows(flows_dir)
    assert len(flows) == 1
    return flows[0]


class TestFlowParserCalledFlowNames:
    def test_subflow_element_flow_name_is_collected(self, tmp_path: Path) -> None:
        flow = _parse_single_flow(tmp_path, "Parent_Flow", FLOW_WITH_SUBFLOW_CALL)
        assert flow.called_flow_names == ["Called_Subflow"]

    def test_multiple_subflow_elements_are_all_collected(self, tmp_path: Path) -> None:
        flow = _parse_single_flow(tmp_path, "Parent_Flow_Two_Calls", FLOW_WITH_TWO_SUBFLOW_CALLS)
        assert flow.called_flow_names == ["First_Subflow", "Second_Subflow"]

    def test_flow_without_subflow_element_has_no_called_flow_names(self, tmp_path: Path) -> None:
        flow = _parse_single_flow(tmp_path, "No_Subflow_Here", FLOW_WITHOUT_SUBFLOW_CALL)
        assert flow.called_flow_names == []


class TestSubflowIsNotAnOrphan:
    def _build_source(self, tmp_path: Path) -> Path:
        source = tmp_path / "source"
        flows_dir = source / "flows"
        flows_dir.mkdir(parents=True, exist_ok=True)
        (flows_dir / "Parent_Flow.flow-meta.xml").write_text(FLOW_WITH_SUBFLOW_CALL, encoding="utf-8")
        (flows_dir / "Called_Subflow.flow-meta.xml").write_text(SUBFLOW_TARGET, encoding="utf-8")
        (flows_dir / "Truly_Orphan_Flow.flow-meta.xml").write_text(
            SUBFLOW_TARGET.replace("Called Subflow", "Truly Orphan Flow"), encoding="utf-8"
        )
        return source

    def test_called_subflow_is_excluded_from_orphans(self, tmp_path: Path) -> None:
        source = self._build_source(tmp_path)
        parser = SalesforceMetadataParser(source)
        snapshot = parser.parse()

        orphan_flow_names = {o.name for o in snapshot.orphans if o.kind == "Flow"}

        assert "Called_Subflow" not in orphan_flow_names, (
            "A Flow called via a Subflow element must not be reported as an orphan"
        )

    def test_genuinely_unreferenced_flow_is_still_an_orphan(self, tmp_path: Path) -> None:
        source = self._build_source(tmp_path)
        parser = SalesforceMetadataParser(source)
        snapshot = parser.parse()

        orphan_flow_names = {o.name for o in snapshot.orphans if o.kind == "Flow"}

        assert "Truly_Orphan_Flow" in orphan_flow_names

    def test_subflow_dependency_is_recorded(self, tmp_path: Path) -> None:
        source = self._build_source(tmp_path)
        parser = SalesforceMetadataParser(source)
        snapshot = parser.parse()

        matches = [
            dep
            for dep in snapshot.dependencies
            if dep.source_name == "Parent_Flow"
            and dep.source_kind == "Flow"
            and dep.target_name == "Called_Subflow"
            and dep.target_kind == "Flow"
        ]
        assert len(matches) == 1
