"""Tests: ``soql_count`` / ``dml_count`` only count genuine SOQL queries and
genuine DML operations, so that the data-access rules (APEX-SEC-004 CRUD/FLS,
APEX-REL-001 try/catch, APEX-PERF-001/002 in-loop) cannot fire on a class that
merely mentions 'update' or 'DELETE' in a comment, a string or an HTTP verb.

Contract tested:
  src.parsers.salesforce_parser.apex_helpers
    _SOQL_RE / _SOSL_RE / _DML_RE match only real data-access syntax.

  SalesforceMetadataParser(...).parse() -> MetadataSnapshot
    the parsed ApexArtifact carries counts computed on executable code only.

  src.analyzer.apex_analyzer.analyze_apex_artifact(...)
    APEX-SEC-004 is not reported for a callout-only class.
"""

from __future__ import annotations

from pathlib import Path

from src.analyzer.apex_analyzer import analyze_apex_artifact
from src.analyzer.rule_catalog import RuleCatalog
from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.parsers.salesforce_parser.apex_helpers import _DML_RE, _SOQL_RE, _SOSL_RE


CLASS_META = """<?xml version="1.0" encoding="UTF-8"?>
<ApexClass xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>59.0</apiVersion>
    <status>Active</status>
</ApexClass>
"""

# A token-client class: no SOQL, no DML, but plenty of DML-looking words in
# comments, string literals and identifiers.
CALLOUT_ONLY_CLASS = """public with sharing class CIAMTokenClient {
    // Il faut update le token avant expiration, sinon on doit delete le cache.
    /* On peut aussi merge les scopes demandes. */
    private static final String VERB_DELETE = 'DELETE';

    public static String getToken(String scope) {
        HttpRequest req = new HttpRequest();
        req.setEndpoint('callout:CIAM/token');
        req.setMethod('POST');
        req.setBody('{"grant_type":"client_credentials","action":"update"}');
        try {
            HttpResponse res = new Http().send(req);
            return res.getBody();
        } catch (CalloutException e) {
            throw new CalloutException('insert failed: ' + e.getMessage());
        }
    }

    private static void updateCache(String value) {
        Cache.Org.put('token', value);
    }

    private static void deleteCache() {
        Cache.Org.remove('token');
    }
}
"""

REAL_DATA_ACCESS_CLASS = """public with sharing class AccountService {
    public static void run(Id ownerId) {
        List<Account> accounts = [SELECT Id, Name FROM Account WHERE OwnerId = :ownerId];
        for (Account a : accounts) {
            a.Name = a.Name + ' (audited)';
        }
        update accounts;
        Contact c = new Contact(LastName = 'x');
        insert c;
        Database.delete(accounts, false);
    }
}
"""


def _write_class(root: Path, name: str, body: str) -> None:
    folder = root / "force-app" / "main" / "default" / "classes"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.cls").write_text(body, encoding="utf-8")
    (folder / f"{name}.cls-meta.xml").write_text(CLASS_META, encoding="utf-8")


def _artifact(root: Path, name: str):
    snapshot = SalesforceMetadataParser(root).parse()
    matches = [a for a in snapshot.apex_artifacts if a.name == name]
    assert matches, f"artifact {name} not parsed"
    return matches[0]


# ---------------------------------------------------------------- regex level


def test_dml_regex_ignores_bare_english_words():
    assert not _DML_RE.findall("String verb = VERB;")
    assert not _DML_RE.findall("Boolean isUpdate = Trigger.isUpdate;")
    assert not _DML_RE.findall("TriggerOperation.AFTER_INSERT")
    assert not _DML_RE.findall("public void update(List<Account> accounts) {")
    assert not _DML_RE.findall("trigger T on Account (after insert, before update) {")
    assert not _DML_RE.findall("List<Account> a = [SELECT Id FROM Account FOR UPDATE];")
    assert not _DML_RE.findall("Schema.SObjectType.Account.isUpdateable()")


def test_dml_regex_matches_real_operations():
    assert len(_DML_RE.findall("insert acc;")) == 1
    assert len(_DML_RE.findall("update as user records;")) == 1
    assert len(_DML_RE.findall("upsert records Account.Ext__c;")) == 1
    assert len(_DML_RE.findall("undelete scope;")) == 1
    assert len(_DML_RE.findall("merge master duplicate;")) == 1
    assert len(_DML_RE.findall("Database.insert(records, false);")) == 1
    assert len(_DML_RE.findall("Database.upsertImmediate(records);")) == 1
    assert len(_DML_RE.findall("Database.insertAsync(records, cb);")) == 1
    assert len(_DML_RE.findall("if (flag) delete records;")) == 1
    assert len(_DML_RE.findall("{ insert records; }")) == 1


def test_soql_regex_matches_dynamic_query_entry_points():
    assert len(_SOQL_RE.findall("List<Account> a = [SELECT Id FROM Account];")) == 1
    assert len(_SOQL_RE.findall("Database.query(q)")) == 1
    assert len(_SOQL_RE.findall("Database.queryWithBinds(q, binds, AccessLevel.USER_MODE)")) == 1
    assert len(_SOQL_RE.findall("Database.getQueryLocator(q)")) == 1
    assert len(_SOQL_RE.findall("Database.countQuery(q)")) == 1
    assert not _SOQL_RE.findall("String q = 'SELECT Id FROM Account';")
    assert len(_SOSL_RE.findall("[FIND 'x' IN ALL FIELDS RETURNING Account(Id)]")) == 1


# --------------------------------------------------------------- parser level


def test_callout_only_class_has_no_data_access(tmp_path):
    _write_class(tmp_path, "CIAMTokenClient", CALLOUT_ONLY_CLASS)
    artifact = _artifact(tmp_path, "CIAMTokenClient")
    assert artifact.soql_count == 0
    assert artifact.dml_count == 0
    assert artifact.sosl_count == 0
    assert artifact.query_in_loop is False
    assert artifact.dml_in_loop is False


def test_real_data_access_class_is_counted(tmp_path):
    _write_class(tmp_path, "AccountService", REAL_DATA_ACCESS_CLASS)
    artifact = _artifact(tmp_path, "AccountService")
    assert artifact.soql_count == 1
    assert artifact.dml_count == 3


# ------------------------------------------------------------- analyzer level


def test_apex_sec_004_not_reported_on_callout_only_class(tmp_path):
    _write_class(tmp_path, "CIAMTokenClient", CALLOUT_ONLY_CLASS)
    artifact = _artifact(tmp_path, "CIAMTokenClient")
    catalog = RuleCatalog.load()
    rule_ids = {f.rule.id for f in analyze_apex_artifact(artifact, catalog)}
    assert "APEX-SEC-004" not in rule_ids
    assert "APEX-REL-001" not in rule_ids


def test_apex_sec_004_still_reported_on_unprotected_data_access(tmp_path):
    _write_class(tmp_path, "AccountService", REAL_DATA_ACCESS_CLASS)
    artifact = _artifact(tmp_path, "AccountService")
    catalog = RuleCatalog.load()
    rule_ids = {f.rule.id for f in analyze_apex_artifact(artifact, catalog)}
    assert "APEX-SEC-004" in rule_ids
