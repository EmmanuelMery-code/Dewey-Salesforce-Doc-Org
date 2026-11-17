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


FLOW_MISSING_FAULT_PATH = """<?xml version="1.0" encoding="UTF-8"?>
<Flow xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>60.0</apiVersion>
    <label>Flow Missing Fault Path</label>
    <processType>AutoLaunchedFlow</processType>
    <status>Active</status>
    <start>
        <connector>
            <targetReference>Get_Account</targetReference>
        </connector>
    </start>
    <recordLookups>
        <name>Get_Account</name>
        <label>Get Account</label>
        <object>Account</object>
        <connector>
            <targetReference>Update_Account</targetReference>
        </connector>
        <faultConnector>
            <targetReference>Log_Error</targetReference>
        </faultConnector>
    </recordLookups>
    <recordUpdates>
        <name>Update_Account</name>
        <label>Update Account</label>
        <object>Account</object>
        <connector>
            <targetReference>Set_Flag</targetReference>
        </connector>
    </recordUpdates>
    <assignments>
        <name>Set_Flag</name>
        <label>Set Flag</label>
    </assignments>
    <actionCalls>
        <name>Log_Error</name>
        <label>Log Error</label>
        <actionName>ErrorLogger.log</actionName>
        <actionType>apex</actionType>
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


class TestFlowAnalyzerFlowRel001:
    """FLOW-REL-001 : elements pouvant echouer et depourvus de fault path."""

    def _catalog(self) -> RuleCatalog:
        return RuleCatalog.load()

    def _analyze(self, flow: FlowInfo):
        return [f for f in analyze_flow(flow, self._catalog()) if f.rule.id == "FLOW-REL-001"]

    def test_rule_is_registered_as_major(self) -> None:
        rule = self._catalog().get("FLOW-REL-001")
        assert rule is not None
        assert rule.enabled is True
        assert rule.severity == "Major"

    def test_element_without_fault_connector_is_flagged(self, tmp_path: Path) -> None:
        flow = _parse_single_flow(tmp_path, "Flow_Missing_Fault_Path", FLOW_MISSING_FAULT_PATH)
        matches = self._analyze(flow)
        assert len(matches) == 1
        # Get_Account porte un faultConnector, Update_Account et Log_Error non.
        # Set_Flag (assignment) ne supporte pas de fault path : hors perimetre.
        details = " | ".join(matches[0].details)
        assert "Update Account" in details
        assert "Log Error" in details
        assert "Get Account" not in details
        assert "Set Flag" not in details
        assert "2 element(s) sur 3" in matches[0].message

    def test_rule_does_not_fire_when_every_element_is_protected(self, tmp_path: Path) -> None:
        content = FLOW_MISSING_FAULT_PATH.replace(
            "        <name>Update_Account</name>\n"
            "        <label>Update Account</label>\n"
            "        <object>Account</object>\n"
            "        <connector>\n"
            "            <targetReference>Set_Flag</targetReference>\n"
            "        </connector>\n",
            "        <name>Update_Account</name>\n"
            "        <label>Update Account</label>\n"
            "        <object>Account</object>\n"
            "        <connector>\n"
            "            <targetReference>Set_Flag</targetReference>\n"
            "        </connector>\n"
            "        <faultConnector>\n"
            "            <targetReference>Log_Error</targetReference>\n"
            "        </faultConnector>\n",
        ).replace(
            "        <actionName>ErrorLogger.log</actionName>\n"
            "        <actionType>apex</actionType>\n",
            "        <actionName>ErrorLogger.log</actionName>\n"
            "        <actionType>apex</actionType>\n"
            "        <faultConnector>\n"
            "            <targetReference>Set_Flag</targetReference>\n"
            "        </faultConnector>\n",
        )
        flow = _parse_single_flow(tmp_path, "Flow_All_Protected", content)
        assert self._analyze(flow) == []

    def test_flow_without_fault_capable_element_is_not_flagged(self) -> None:
        flow = FlowInfo(name="Flow_Screens_Only", description="Un flow de test.")
        assert self._analyze(flow) == []

    def test_before_save_record_update_without_fault_is_not_an_error(self, tmp_path: Path) -> None:
        """RecordBeforeSave ne peut pas poser de fault path sur un Update Records."""
        content = _triggered_flow(
            "RecordBeforeSave",
            """
    <recordUpdates>
        <name>Update_Triggering</name>
        <label>Update Triggering</label>
        <inputReference>$Record</inputReference>
    </recordUpdates>
    <recordLookups>
        <name>Get_Account</name>
        <label>Get Account</label>
        <object>Account</object>
    </recordLookups>
    <recordCreates>
        <name>Create_Task</name>
        <label>Create Task</label>
        <object>Task</object>
    </recordCreates>
""",
        )
        flow = _parse_single_flow(tmp_path, "Flow_Before_Save", content)
        matches = self._analyze(flow)
        assert len(matches) == 1
        details = " | ".join(matches[0].details)
        assert "Update Triggering" not in details
        assert "Get Account" in details
        assert "Create Task" in details
        # L'update before-save ne compte ni comme erreur ni dans le total.
        assert "2 element(s) sur 2" in matches[0].message

    def test_after_save_record_update_without_fault_stays_an_error(self, tmp_path: Path) -> None:
        content = _triggered_flow(
            "RecordAfterSave",
            """
    <recordUpdates>
        <name>Update_Account</name>
        <label>Update Account</label>
        <object>Account</object>
    </recordUpdates>
""",
        )
        flow = _parse_single_flow(tmp_path, "Flow_After_Save", content)
        matches = self._analyze(flow)
        assert len(matches) == 1
        assert "Update Account" in matches[0].details[0]
        assert "1 element(s) sur 1" in matches[0].message

    def test_nebula_elements_are_ignored_for_fault_paths(self, tmp_path: Path) -> None:
        """Une action ou un sous-flux Nebula ne fonde pas FLOW-REL-001."""
        content = _triggered_flow(
            "RecordAfterSave",
            """
    <actionCalls>
        <name>Add_Log_Entry</name>
        <label>Add Log Entry</label>
        <actionName>nebula__FlowLogEntry</actionName>
        <actionType>apex</actionType>
    </actionCalls>
    <actionCalls>
        <name>Save_Log</name>
        <label>Save Log</label>
        <actionName>FlowLogger</actionName>
        <actionType>apex</actionType>
    </actionCalls>
    <subflows>
        <name>Call_Nebula</name>
        <label>Call Nebula</label>
        <flowName>nebula__Logger</flowName>
    </subflows>
    <recordUpdates>
        <name>Update_Nebula_Shadow</name>
        <label>Update shadow</label>
        <object>Account</object>
    </recordUpdates>
    <actionCalls>
        <name>Call_Erp</name>
        <label>Call Erp</label>
        <actionName>SyncAccountToErp</actionName>
        <actionType>apex</actionType>
    </actionCalls>
    <recordUpdates>
        <name>Update_Account</name>
        <label>Update Account</label>
        <object>Account</object>
    </recordUpdates>
""",
        )
        flow = _parse_single_flow(tmp_path, "Flow_Nebula_Fault", content)
        matches = self._analyze(flow)
        assert len(matches) == 1
        details = " | ".join(matches[0].details)
        assert "Call Erp" in details
        assert "Update Account" in details
        assert "Add Log Entry" not in details
        assert "Save Log" not in details
        assert "Call Nebula" not in details
        assert "Update shadow" not in details
        assert "Nebula" not in details
        # Quatre elements Nebula exclus du perimetre, deux vrais elements non proteges.
        assert "2 element(s) sur 2" in matches[0].message

    def test_only_nebula_action_does_not_raise_fault_path(self, tmp_path: Path) -> None:
        content = _triggered_flow(
            "RecordAfterSave",
            """
    <actionCalls>
        <name>Add_Log_Entry</name>
        <label>Add Log Entry</label>
        <actionName>FlowLogEntry</actionName>
        <actionType>apex</actionType>
    </actionCalls>
""",
        )
        flow = _parse_single_flow(tmp_path, "Flow_Nebula_Only", content)
        assert self._analyze(flow) == []


def _triggered_flow(trigger_type: str, body: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Flow xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>60.0</apiVersion>
    <label>Triggered flow</label>
    <processType>AutoLaunchedFlow</processType>
    <status>Active</status>
    <start>
        <object>Account</object>
        <recordTriggerType>Update</recordTriggerType>
        <triggerType>{trigger_type}</triggerType>
    </start>
    {body}
</Flow>
"""
