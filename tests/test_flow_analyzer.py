"""Tests for Flow parsing (DML/SOQL/API-call-in-loop) and the FLOW-PERF-* rules.

Contract tested:
  _FlowsMixin()._parse_flows(folder) -> list[FlowInfo]
    .dml_in_loop / .soql_in_loop / .api_call_in_loop (bool)
    .api_call_in_loop_actions (list[str] of the actionCalls node names involved)

  analyze_flow(flow, catalog) -> list[Finding]
    FLOW-PERF-004 fires when flow.api_call_in_loop is True.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.analyzer.flow_analyzer import analyze_flow
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import FlowInfo
from src.parsers.salesforce_parser.flows_mixin import _FlowsMixin


FLOW_API_IN_LOOP = """<?xml version="1.0" encoding="UTF-8"?>
<Flow xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>60.0</apiVersion>
    <label>Flow Api In Loop</label>
    <processType>AutoLaunchedFlow</processType>
    <status>Draft</status>
    <start>
        <connector>
            <targetReference>Loop_Accounts</targetReference>
        </connector>
    </start>
    <loops>
        <name>Loop_Accounts</name>
        <label>Loop Accounts</label>
        <collectionReference>AccountCollection</collectionReference>
        <nextValueConnector>
            <targetReference>Call_External_Service</targetReference>
        </nextValueConnector>
    </loops>
    <actionCalls>
        <name>Call_External_Service</name>
        <label>Call External Service</label>
        <actionName>WeatherService.getForecast</actionName>
        <actionType>externalService</actionType>
        <connector>
            <targetReference>Loop_Accounts</targetReference>
        </connector>
    </actionCalls>
</Flow>
"""

FLOW_API_OUTSIDE_LOOP = """<?xml version="1.0" encoding="UTF-8"?>
<Flow xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>60.0</apiVersion>
    <label>Flow Api Outside Loop</label>
    <processType>AutoLaunchedFlow</processType>
    <status>Draft</status>
    <start>
        <connector>
            <targetReference>Call_External_Service</targetReference>
        </connector>
    </start>
    <actionCalls>
        <name>Call_External_Service</name>
        <label>Call External Service</label>
        <actionName>WeatherService.getForecast</actionName>
        <actionType>externalService</actionType>
    </actionCalls>
</Flow>
"""

FLOW_APEX_ACTION_IN_LOOP = """<?xml version="1.0" encoding="UTF-8"?>
<Flow xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>60.0</apiVersion>
    <label>Flow Apex Action In Loop</label>
    <processType>AutoLaunchedFlow</processType>
    <status>Draft</status>
    <start>
        <connector>
            <targetReference>Loop_Accounts</targetReference>
        </connector>
    </start>
    <loops>
        <name>Loop_Accounts</name>
        <label>Loop Accounts</label>
        <collectionReference>AccountCollection</collectionReference>
        <nextValueConnector>
            <targetReference>Call_Apex_Action</targetReference>
        </nextValueConnector>
    </loops>
    <actionCalls>
        <name>Call_Apex_Action</name>
        <label>Call Apex Action</label>
        <actionName>SyncAccountToErp</actionName>
        <actionType>apex</actionType>
        <connector>
            <targetReference>Loop_Accounts</targetReference>
        </connector>
    </actionCalls>
</Flow>
"""


def _parse_single_flow(tmp_path: Path, filename: str, content: str) -> FlowInfo:
    flows_dir = tmp_path / "flows"
    flows_dir.mkdir(parents=True, exist_ok=True)
    (flows_dir / f"{filename}.flow-meta.xml").write_text(content, encoding="utf-8")
    flows = _FlowsMixin()._parse_flows(flows_dir)
    assert len(flows) == 1
    return flows[0]


class TestFlowParserApiCallInLoop:
    def test_external_service_action_in_loop_is_detected(self, tmp_path: Path) -> None:
        flow = _parse_single_flow(tmp_path, "Flow_Api_In_Loop", FLOW_API_IN_LOOP)
        assert flow.api_call_in_loop is True
        assert flow.api_call_in_loop_actions == ["Call_External_Service"]

    def test_external_service_action_outside_any_loop_is_not_flagged(self, tmp_path: Path) -> None:
        flow = _parse_single_flow(tmp_path, "Flow_Api_Outside_Loop", FLOW_API_OUTSIDE_LOOP)
        assert flow.api_call_in_loop is False
        assert flow.api_call_in_loop_actions == []

    def test_apex_action_in_loop_is_out_of_v1_scope(self, tmp_path: Path) -> None:
        """V1 only covers actionType == 'externalService'; a plain Apex invocable
        action (which might itself perform a callout) is intentionally not
        flagged without cross-referencing the target Apex class."""
        flow = _parse_single_flow(tmp_path, "Flow_Apex_Action_In_Loop", FLOW_APEX_ACTION_IN_LOOP)
        assert flow.api_call_in_loop is False
        assert flow.dml_in_loop is False
        assert flow.soql_in_loop is False


class TestFlowAnalyzerFlowPerf004:
    def _catalog(self) -> RuleCatalog:
        return RuleCatalog.load()

    def _base_flow(self, **overrides) -> FlowInfo:
        defaults = dict(
            name="Flow_Test",
            description="Un flow de test.",
            total_elements=1,
            described_elements=1,
        )
        defaults.update(overrides)
        return FlowInfo(**defaults)

    def test_rule_fires_when_api_call_in_loop(self) -> None:
        flow = self._base_flow(
            api_call_in_loop=True,
            api_call_in_loop_actions=["Call_External_Service"],
        )
        findings = analyze_flow(flow, self._catalog())
        matches = [f for f in findings if f.rule.id == "FLOW-PERF-004"]
        assert len(matches) == 1
        assert "Call_External_Service" in matches[0].details[0]

    def test_rule_does_not_fire_without_api_call_in_loop(self) -> None:
        flow = self._base_flow(api_call_in_loop=False)
        findings = analyze_flow(flow, self._catalog())
        matches = [f for f in findings if f.rule.id == "FLOW-PERF-004"]
        assert matches == []

    def test_rule_is_registered_as_critical(self) -> None:
        rule = self._catalog().get("FLOW-PERF-004")
        assert rule is not None
        assert rule.enabled is True
        assert rule.severity == "Critical"
