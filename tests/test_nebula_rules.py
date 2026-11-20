"""Detection des regles Nebula Logger."""

from __future__ import annotations

from pathlib import Path

from src.analyzer.engine import AnalyzerEngine
from src.analyzer.nebula_apex import analyze_nebula_apex
from src.analyzer.nebula_config import (
    DEFAULT_NEBULA_LOG_FORMAT,
    DEFAULT_NEBULA_TAGS,
    NebulaConfig,
    parse_nebula_enabled,
    parse_nebula_format,
    parse_nebula_tags,
)
from src.analyzer.nebula_flow import analyze_nebula_flow
from src.analyzer.nebula_lwc import analyze_nebula_lwc
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import ApexArtifact, FlowInfo, LwcInfo


def _catalog() -> RuleCatalog:
    catalog = RuleCatalog.load()
    for rule in catalog.all:
        if rule.id.startswith("NEBULA-"):
            rule.enabled = True
    return catalog


def _apex(name: str, body: str, kind: str = "class") -> ApexArtifact:
    return ApexArtifact(name=name, kind=kind, body=body, source_path=Path(f"{name}.cls"))


def _ids(findings) -> set[str]:
    return {finding.rule.id for finding in findings}


COMPLIANT = """
public with sharing class AccountService {
    public static void mergeDuplicates(List<Id> accountIds) {
        Logger.info('[AccountService.mergeDuplicates] Start | accountIds=' + accountIds.size());
        try {
            Logger.info('[AccountService.mergeDuplicates] End | merged=1');
        } catch (Exception e) {
            Logger.error('[AccountService.mergeDuplicates] Failed', e);
            throw e;
        } finally {
            Logger.saveLog();
        }
    }
}
"""


def test_compliant_apex_has_no_nebula_finding() -> None:
    findings = analyze_nebula_apex(_apex("AccountService", COMPLIANT), _catalog(), NebulaConfig.from_values(True, None, None))
    assert _ids(findings) == set()


def test_apex_rules_from_the_standard() -> None:
    body = """
public with sharing class AccountService {
    public static void mergeDuplicates(List<Id> accountIds) {
        System.debug('trace');
        String ignored = 'System.debug(';
        Logger.info('[AccountService.mergeDuplicates] Start | password=' + password).addTag('Nope');
        try {
            for (Integer i = 0; i < 2; i++) {
                Logger.debug('[AccountService.mergeDuplicates] Loop iteration | index=' + i);
            }
            Logger.info('[AccountService.mergeDuplicates] Payload | body=' + JSON.serialize(rows));
            Database.update(rows, false);
            Logger.info('[AccountService.mergeDuplicates] Echec traitement.');
        } catch (Exception e) {
            Logger.info('[AccountService.mergeDuplicates] Failed', e);
        } finally {
            Logger.saveLog();
            Logger.saveLog();
        }
    }
}
"""
    findings = analyze_nebula_apex(
        _apex("AccountService", body), _catalog(), NebulaConfig.from_values(True, None, None)
    )
    assert _ids(findings) == {
        "NEBULA-APEX-001",
        "NEBULA-APEX-002",
        "NEBULA-APEX-004",
        "NEBULA-APEX-005",
        "NEBULA-APEX-006",
        "NEBULA-APEX-008",
        "NEBULA-APEX-009",
        "NEBULA-APEX-010",
        "NEBULA-APEX-011",
        "NEBULA-APEX-012",
    }


def test_sensitive_word_inside_a_string_is_not_a_finding() -> None:
    body = """
public with sharing class AccountService {
    public static void mergeDuplicates(List<Id> accountIds) {
        Logger.info('[AccountService.mergeDuplicates] Start | password=' + accountIds.size());
        try {
            Logger.info('[AccountService.mergeDuplicates] End | token=redacted');
        } catch (Exception e) {
            Logger.error('[AccountService.mergeDuplicates] Failed', e);
            throw e;
        } finally {
            Logger.saveLog();
        }
    }
}
"""
    findings = analyze_nebula_apex(
        _apex("AccountService", body), _catalog(), NebulaConfig.from_values(True, None, None)
    )
    assert "NEBULA-APEX-008" not in _ids(findings)


def test_sensitive_variable_in_a_log_is_a_finding() -> None:
    body = """
public with sharing class AccountService {
    public static void mergeDuplicates(String password) {
        Logger.info('[AccountService.mergeDuplicates] Start | value=' + password);
        try {
            Logger.info('[AccountService.mergeDuplicates] End | merged=1');
        } catch (Exception e) {
            Logger.error('[AccountService.mergeDuplicates] Failed', e);
            throw e;
        } finally {
            Logger.saveLog();
        }
    }
}
"""
    findings = analyze_nebula_apex(
        _apex("AccountService", body), _catalog(), NebulaConfig.from_values(True, None, None)
    )
    assert "NEBULA-APEX-008" in _ids(findings)


def test_missing_save_log_is_limited_to_the_method() -> None:
    body = """
public with sharing class AccountService {
    public static void good() {
        try {
            Logger.info('[AccountService.good] End | merged=1');
        } catch (Exception e) {
            Logger.error('[AccountService.good] Failed', e);
        } finally {
            Logger.saveLog();
        }
    }
    public static void bad() {
        Logger.info('[AccountService.bad] Start | count=1');
    }
}
"""
    findings = analyze_nebula_apex(
        _apex("AccountService", body), _catalog(), NebulaConfig.from_values(True, None, None)
    )
    assert _ids(findings) == {"NEBULA-APEX-003"}


def test_swallowed_exception_and_logged_partial_dml() -> None:
    swallowed = """
public with sharing class AccountService {
    public static void run() {
        try {
            Logger.info('[AccountService.run] Start | count=1');
        } catch (Exception e) {
        } finally {
            Logger.saveLog();
        }
    }
}
"""
    logged = """
public with sharing class AccountService {
    public static void run() {
        List<Database.SaveResult> results = Database.update(rows, false);
        Logger.error('[AccountService.run] DML error', results);
        Logger.saveLog();
    }
}
"""
    config = NebulaConfig.from_values(True, None, None)
    catalog = _catalog()
    assert "NEBULA-APEX-002" in _ids(analyze_nebula_apex(_apex("AccountService", swallowed), catalog, config))
    assert "NEBULA-APEX-011" not in _ids(analyze_nebula_apex(_apex("AccountService", logged), catalog, config))


def test_trigger_uses_trigger_rule_ids() -> None:
    body = """
trigger AccountTrigger on Account (before insert) {
    System.debug('boom');
}
"""
    findings = analyze_nebula_apex(
        _apex("AccountTrigger", body, kind="trigger"),
        _catalog(),
        NebulaConfig.from_values(True, None, None),
    )
    assert _ids(findings) == {"NEBULA-TRIG-001"}


def test_format_and_tags_follow_the_configuration() -> None:
    body = """
public with sharing class AccountService {
    public static void run() {
        Logger.info('OK started').addTag('Integration-Payment');
        Logger.saveLog();
    }
}
"""
    strict = NebulaConfig.from_values(True, r"^OK", ["Sales"])
    findings = analyze_nebula_apex(_apex("AccountService", body), _catalog(), strict)
    assert "NEBULA-APEX-007" not in _ids(findings)
    assert "NEBULA-APEX-012" in _ids(findings)

    standard = NebulaConfig.from_values(True, None, None)
    findings = analyze_nebula_apex(_apex("AccountService", body), _catalog(), standard)
    assert "NEBULA-APEX-007" in _ids(findings)
    assert "NEBULA-APEX-012" not in _ids(findings)


def test_engine_ignores_nebula_until_the_switch_is_on() -> None:
    artifact = _apex("AccountService", "public class AccountService { public void run() { System.debug('x'); } }")
    catalog = _catalog()
    disabled = AnalyzerEngine(catalog, nebula=NebulaConfig.disabled())
    assert not any(item.rule.id.startswith("NEBULA-") for item in disabled.analyze_apex(artifact))
    enabled = AnalyzerEngine(catalog, nebula=NebulaConfig.from_values(True, None, None))
    assert any(item.rule.id == "NEBULA-APEX-001" for item in enabled.analyze_apex(artifact))


def test_flow_fault_path_and_message(tmp_path: Path) -> None:
    missing = tmp_path / "Missing.flow-meta.xml"
    missing.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<Flow xmlns="http://soap.sforce.com/2006/04/metadata">
    <actionCalls>
        <name>Boom</name>
        <label>Call</label>
        <actionName>DoSomething</actionName>
        <faultConnector><targetReference>EndStep</targetReference></faultConnector>
    </actionCalls>
    <screens>
        <name>EndStep</name>
        <label>End</label>
    </screens>
</Flow>
""",
        encoding="utf-8",
    )
    covered = tmp_path / "Covered.flow-meta.xml"
    covered.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<Flow xmlns="http://soap.sforce.com/2006/04/metadata">
    <actionCalls>
        <name>Boom</name>
        <label>Call</label>
        <actionName>DoSomething</actionName>
        <faultConnector><targetReference>Add</targetReference></faultConnector>
    </actionCalls>
    <actionCalls>
        <name>Add</name>
        <label>Add Log Entry</label>
        <actionName>FlowLogEntry</actionName>
        <connector><targetReference>Save</targetReference></connector>
        <inputParameters>
            <name>message</name>
            <value><stringValue>[Covered.step] Failed | status=500</stringValue></value>
        </inputParameters>
        <inputParameters>
            <name>tags</name>
            <value><stringValue>Flow</stringValue></value>
        </inputParameters>
    </actionCalls>
    <actionCalls>
        <name>Save</name>
        <label>Save Log</label>
        <actionName>FlowLogger</actionName>
    </actionCalls>
</Flow>
""",
        encoding="utf-8",
    )
    catalog = _catalog()
    config = NebulaConfig.from_values(True, None, None)
    missing_ids = _ids(analyze_nebula_flow(FlowInfo(name="Missing", source_path=missing), catalog, config))
    covered_ids = _ids(analyze_nebula_flow(FlowInfo(name="Covered", source_path=covered), catalog, config))
    assert "NEBULA-FLOW-001" in missing_ids
    assert "NEBULA-FLOW-001" not in covered_ids
    assert "NEBULA-FLOW-002" not in covered_ids


def test_lwc_console_format_and_save(tmp_path: Path) -> None:
    folder = tmp_path / "orderForm"
    folder.mkdir()
    (folder / "orderForm.js").write_text(
        """
import { LightningElement } from 'lwc';
export default class OrderForm extends LightningElement {
    handleSubmit() {
        console.error('x');
        try {
        } catch (error) {
            logger.error('erreur sauvegarde.');
        }
    }
}
""",
        encoding="utf-8",
    )
    findings = analyze_nebula_lwc(
        LwcInfo(name="orderForm", source_path=folder),
        _catalog(),
        NebulaConfig.from_values(True, None, None),
    )
    assert _ids(findings) >= {
        "NEBULA-LWC-001",
        "NEBULA-LWC-002",
        "NEBULA-LWC-003",
        "NEBULA-LWC-004",
        "NEBULA-LWC-009",
    }


def test_settings_fall_back_to_the_standard() -> None:
    assert parse_nebula_enabled({}) is False
    assert parse_nebula_enabled({"nebula_rules_enabled": True}) is True
    assert parse_nebula_format({"nebula_log_format": "["}) == DEFAULT_NEBULA_LOG_FORMAT
    assert parse_nebula_format({"nebula_log_format": r"^OK"}) == r"^OK"
    assert parse_nebula_tags({}) == list(DEFAULT_NEBULA_TAGS)
    assert parse_nebula_tags({"nebula_tags": ["Sales", "Sales", ""]}) == ["Sales"]
