"""
Tests for SfFindingsService (new lifecycle model).

Contract tested:
  SfFindingsService(org_alias)
    .push(result, org_alias, source_path, source_branch, scope)
      → (analysis_id: str, delta_summary: str | None)

Key behavioural contract (new model):
  - DeweyFinding__c is unique per (OrgAlias, RuleId, ComponentName).
  - On first run: all findings create new DeweyFinding__c + DeweyAnalysisFinding__c
    with IsNewInRun__c=True.
  - On subsequent runs with same findings: DeweyFinding__c is REUSED; only
    DeweyAnalysisFinding__c is created (IsNewInRun__c=False).
  - Findings no longer detected (non-terminal status) → Status__c set to "Disparu".
  - Findings previously Résolu/Accepté that reappear → new DeweyFinding__c created.
  - delta_summary is None when no previous analysis exists; a non-empty string otherwise.
  - DeweyDelta__c.ResolvedFindings__c = count of findings marked Disparu in this run.
"""
import json
from unittest.mock import MagicMock, patch


# ── Factories ──────────────────────────────────────────────────────────────────

def _make_finding(rule_id: str, target_name: str, severity: str = "Major"):
    f = MagicMock()
    f.rule.id = rule_id
    f.rule.severity = severity
    f.rule.description = "desc"
    f.rule.remediation = "fix"
    f.target_kind = "apex_class"
    f.target_name = target_name
    f.message = "msg"
    f.source_path = None
    f.line = None
    return f


def _make_report(findings: list):
    report = MagicMock()
    report.all_findings.return_value = findings
    counts: dict = {}
    for f in findings:
        counts[f.rule.severity] = counts.get(f.rule.severity, 0) + 1
    report.severity_counts.return_value = counts
    return report


def _make_snapshot(score: int = 75):
    snap = MagicMock()
    snap.metrics.score = score
    snap.metrics.apex_classes = 3
    snap.metrics.apex_triggers = 1
    snap.metrics.flows = 5
    snap.metrics.lwc_count = 2
    return snap


def _make_result(findings=None, score=75):
    result = MagicMock()
    result.report = _make_report(findings or [])
    result.snapshot = _make_snapshot(score)
    return result


def _soql_response(records: list) -> MagicMock:
    m = MagicMock()
    m.returncode = 0
    m.stdout = json.dumps({"result": {"records": records, "totalSize": len(records)}})
    return m


def _rest_create_response(record_id: str = "a001000000FAKEaAAH") -> dict:
    return {"id": record_id, "success": True, "errors": []}


def _rest_composite_response(n: int) -> list:
    return [{"id": f"a00{i:015d}", "success": True, "errors": []} for i in range(n)]


# ══════════════════════════════════════════════════════════════════════════════
# Mocked service context manager
# ══════════════════════════════════════════════════════════════════════════════

class _MockedService:
    """
    Patches subprocess.run to control all Salesforce CLI responses.

    existing_findings: list of dicts with keys Id, RuleId__c, ComponentName__c, Status__c.
    prev_analysis_id: Id of the previous DeweyAnalysis__c (for delta).
    """

    def __init__(
        self,
        analysis_id="a001ANALYSIS0001",
        delta_id="a002DELTA00001",
        existing_findings=None,
        prev_analysis_id=None,
        prev_counts=None,
    ):
        self.analysis_id = analysis_id
        self.delta_id = delta_id
        self.existing_findings = existing_findings or []
        self.prev_analysis_id = prev_analysis_id
        self.prev_counts = prev_counts or {
            "ScoreGlobal__c": 70,
            "FindingCritical__c": 0,
            "FindingMajor__c": 2,
        }
        self._patch = None
        self.service = None
        # Tracks REST calls made
        self.rest_calls: list[tuple[str, str, dict | None]] = []

    def __enter__(self):
        from src.core.sf_findings_service import SfFindingsService

        def _run_side_effect(cmd, **kwargs):
            joined = " ".join(str(c) for c in cmd)

            # SOQL: fetch active findings for org
            if "DeweyFinding__c" in joined and "OrgAlias__c" in joined and "data query" in joined:
                return _soql_response(self.existing_findings)

            # SOQL: fetch previous analysis (excludes current)
            if "DeweyAnalysis__c" in joined and "ORDER BY" in joined and "data query" in joined:
                if self.prev_analysis_id:
                    return _soql_response([{"Id": self.prev_analysis_id}])
                return _soql_response([])

            # SOQL: fetch previous counts
            if "ScoreGlobal__c" in joined and "data query" in joined:
                return _soql_response([{
                    "ScoreGlobal__c": self.prev_counts["ScoreGlobal__c"],
                    "FindingCritical__c": self.prev_counts["FindingCritical__c"],
                    "FindingMajor__c": self.prev_counts["FindingMajor__c"],
                }])

            return _soql_response([])

        self._patch = patch("subprocess.run", side_effect=_run_side_effect)
        self._patch.start()

        self.service = SfFindingsService("ag2rPoc")

        # Intercept _rest to return predictable responses and record calls
        original_rest = self.service._rest
        rest_calls = self.rest_calls
        analysis_id = self.analysis_id
        delta_id = self.delta_id

        def _fake_rest(method, path, payload=None):
            rest_calls.append((method, path, payload))
            if method == "POST" and "/sobjects/DeweyAnalysis__c/" in path:
                return _rest_create_response(analysis_id)
            if method == "POST" and "/sobjects/DeweyDelta__c/" in path:
                return _rest_create_response(delta_id)
            if method == "POST" and "/composite/sobjects" in path and payload:
                n = len(payload.get("records", []))
                return _rest_composite_response(n)
            if method == "PATCH" and "/composite/sobjects" in path:
                n = len(payload.get("records", [])) if payload else 0
                return _rest_composite_response(n)
            return {}

        self.service._rest = _fake_rest
        return self

    def __exit__(self, *args):
        self._patch.stop()

    def finding_create_calls(self) -> list[list[dict]]:
        """Returns list of record batches sent to create DeweyFinding__c."""
        return [
            payload["records"]
            for method, path, payload in self.rest_calls
            if method == "POST"
            and "/composite/sobjects" in path
            and payload
            and payload.get("records")
            and payload["records"][0].get("attributes", {}).get("type") == "DeweyFinding__c"
        ]

    def junction_create_calls(self) -> list[list[dict]]:
        """Returns list of record batches sent to create DeweyAnalysisFinding__c."""
        return [
            payload["records"]
            for method, path, payload in self.rest_calls
            if method == "POST"
            and "/composite/sobjects" in path
            and payload
            and payload.get("records")
            and payload["records"][0].get("attributes", {}).get("type") == "DeweyAnalysisFinding__c"
        ]

    def disparu_patch_calls(self) -> list[list[dict]]:
        """Returns list of record batches PATCHed to set Status__c='Disparu'."""
        return [
            payload["records"]
            for method, path, payload in self.rest_calls
            if method == "PATCH"
            and "/composite/sobjects" in path
            and payload
            and payload.get("records")
            and any(r.get("Status__c") == "Disparu" for r in payload["records"])
        ]


# ══════════════════════════════════════════════════════════════════════════════
# push() — return type and structure
# ══════════════════════════════════════════════════════════════════════════════

class TestPushReturnValues:

    def test_returns_tuple_of_two(self):
        result = _make_result()
        with _MockedService() as m:
            ret = m.service.push(result, "ag2rPoc", "/path/to/src")
        assert isinstance(ret, tuple)
        assert len(ret) == 2

    def test_first_element_is_analysis_id(self):
        result = _make_result()
        with _MockedService(analysis_id="a001ANALYSIS0001") as m:
            analysis_id, _ = m.service.push(result, "ag2rPoc", "/path")
        assert analysis_id == "a001ANALYSIS0001"

    def test_delta_is_none_when_no_previous_analysis(self):
        result = _make_result()
        with _MockedService(prev_analysis_id=None) as m:
            _, delta = m.service.push(result, "ag2rPoc", "/path")
        assert delta is None

    def test_delta_is_string_when_previous_analysis_exists(self):
        result = _make_result()
        with _MockedService(prev_analysis_id="PREV001") as m:
            _, delta = m.service.push(result, "ag2rPoc", "/path")
        assert isinstance(delta, str) and len(delta) > 0


# ══════════════════════════════════════════════════════════════════════════════
# push() — deduplication: new findings
# ══════════════════════════════════════════════════════════════════════════════

class TestFindingDeduplication:

    def test_first_run_creates_finding_records(self):
        """No existing findings → DeweyFinding__c created for each finding."""
        findings = [_make_finding("R1", "ClassA"), _make_finding("R2", "ClassB")]
        result = _make_result(findings=findings)
        with _MockedService(existing_findings=[]) as m:
            m.service.push(result, "ag2rPoc", "/path")
        batches = m.finding_create_calls()
        total = sum(len(b) for b in batches)
        assert total == 2

    def test_first_run_findings_have_status_decouvert(self):
        findings = [_make_finding("R1", "ClassA")]
        result = _make_result(findings=findings)
        with _MockedService(existing_findings=[]) as m:
            m.service.push(result, "ag2rPoc", "/path")
        records = [r for b in m.finding_create_calls() for r in b]
        assert all(r["Status__c"] == "Découvert" for r in records)

    def test_existing_active_finding_not_recreated(self):
        """Finding already active → no new DeweyFinding__c, only a junction."""
        findings = [_make_finding("R1", "ClassA")]
        result = _make_result(findings=findings)
        existing = [{"Id": "EXIST001", "RuleId__c": "R1",
                     "ComponentName__c": "ClassA", "Status__c": "Découvert"}]
        with _MockedService(existing_findings=existing) as m:
            m.service.push(result, "ag2rPoc", "/path")
        # No new DeweyFinding__c should be created
        assert sum(len(b) for b in m.finding_create_calls()) == 0

    def test_existing_active_finding_creates_junction(self):
        findings = [_make_finding("R1", "ClassA")]
        result = _make_result(findings=findings)
        existing = [{"Id": "EXIST001", "RuleId__c": "R1",
                     "ComponentName__c": "ClassA", "Status__c": "Pris en charge"}]
        with _MockedService(existing_findings=existing) as m:
            m.service.push(result, "ag2rPoc", "/path")
        junctions = [r for b in m.junction_create_calls() for r in b]
        assert len(junctions) == 1
        assert junctions[0]["IsNewInRun__c"] is False

    def test_resolved_finding_that_reappears_is_recreated(self):
        """A previously Résolu finding that reappears → new DeweyFinding__c."""
        findings = [_make_finding("R1", "ClassA")]
        result = _make_result(findings=findings)
        existing = [{"Id": "OLD001", "RuleId__c": "R1",
                     "ComponentName__c": "ClassA", "Status__c": "Résolu"}]
        with _MockedService(existing_findings=existing) as m:
            m.service.push(result, "ag2rPoc", "/path")
        assert sum(len(b) for b in m.finding_create_calls()) == 1

    def test_accepted_finding_that_reappears_is_recreated(self):
        """A previously Accepté finding that reappears → new DeweyFinding__c."""
        findings = [_make_finding("R1", "ClassA")]
        result = _make_result(findings=findings)
        existing = [{"Id": "OLD001", "RuleId__c": "R1",
                     "ComponentName__c": "ClassA", "Status__c": "Accepté"}]
        with _MockedService(existing_findings=existing) as m:
            m.service.push(result, "ag2rPoc", "/path")
        assert sum(len(b) for b in m.finding_create_calls()) == 1

    def test_new_finding_junction_is_new_in_run(self):
        """Newly created findings must have IsNewInRun__c=True on their junction."""
        findings = [_make_finding("R1", "ClassA")]
        result = _make_result(findings=findings)
        with _MockedService(existing_findings=[]) as m:
            m.service.push(result, "ag2rPoc", "/path")
        junctions = [r for b in m.junction_create_calls() for r in b]
        assert all(r["IsNewInRun__c"] is True for r in junctions)


# ══════════════════════════════════════════════════════════════════════════════
# push() — Disparu logic
# ══════════════════════════════════════════════════════════════════════════════

class TestDisparuLogic:

    def test_finding_not_in_run_is_marked_disparu(self):
        """Active finding absent from current run → Status__c = Disparu."""
        findings = []  # nothing detected this run
        result = _make_result(findings=findings)
        existing = [{"Id": "OLD001", "RuleId__c": "R1",
                     "ComponentName__c": "ClassA", "Status__c": "Découvert"}]
        with _MockedService(existing_findings=existing) as m:
            m.service.push(result, "ag2rPoc", "/path")
        disparu = [r for b in m.disparu_patch_calls() for r in b]
        assert len(disparu) == 1
        assert disparu[0]["Id"] == "OLD001"

    def test_pris_en_charge_finding_absent_becomes_disparu(self):
        findings = []
        result = _make_result(findings=findings)
        existing = [{"Id": "OLD002", "RuleId__c": "R2",
                     "ComponentName__c": "ClassB", "Status__c": "Pris en charge"}]
        with _MockedService(existing_findings=existing) as m:
            m.service.push(result, "ag2rPoc", "/path")
        disparu = [r for b in m.disparu_patch_calls() for r in b]
        assert len(disparu) == 1

    def test_resolu_finding_absent_is_not_touched(self):
        """A Résolu finding that stays absent must NOT be set to Disparu."""
        findings = []
        result = _make_result(findings=findings)
        existing = [{"Id": "OLD003", "RuleId__c": "R3",
                     "ComponentName__c": "ClassC", "Status__c": "Résolu"}]
        with _MockedService(existing_findings=existing) as m:
            m.service.push(result, "ag2rPoc", "/path")
        disparu = [r for b in m.disparu_patch_calls() for r in b]
        assert len(disparu) == 0

    def test_already_disparu_finding_absent_is_not_touched_again(self):
        findings = []
        result = _make_result(findings=findings)
        existing = [{"Id": "OLD004", "RuleId__c": "R4",
                     "ComponentName__c": "ClassD", "Status__c": "Disparu"}]
        with _MockedService(existing_findings=existing) as m:
            m.service.push(result, "ag2rPoc", "/path")
        disparu = [r for b in m.disparu_patch_calls() for r in b]
        assert len(disparu) == 0


# ══════════════════════════════════════════════════════════════════════════════
# push() — delta summary
# ══════════════════════════════════════════════════════════════════════════════

class TestDeltaSummary:

    def test_delta_mentions_new_and_disparu(self):
        result = _make_result(findings=[_make_finding("R1", "ClassA")])
        with _MockedService(prev_analysis_id="PREV001") as m:
            _, delta = m.service.push(result, "ag2rPoc", "/path")
        assert "new" in delta and "disparu" in delta

    def test_delta_mentions_score(self):
        result = _make_result(score=80)
        with _MockedService(
            prev_analysis_id="PREV",
            prev_counts={"ScoreGlobal__c": 70, "FindingCritical__c": 0, "FindingMajor__c": 2},
        ) as m:
            _, delta = m.service.push(result, "ag2rPoc", "/path")
        assert "score" in delta


# ══════════════════════════════════════════════════════════════════════════════
# push() — bulk batching
# ══════════════════════════════════════════════════════════════════════════════

class TestBulkBatching:

    def test_250_new_findings_split_into_two_batches(self):
        """250 new findings → 2 DeweyFinding__c composite calls (200 + 50)."""
        findings = [_make_finding(f"R{i}", f"Class{i}") for i in range(250)]
        result = _make_result(findings=findings)
        with _MockedService(existing_findings=[]) as m:
            m.service.push(result, "ag2rPoc", "/path")
        batch_sizes = [len(b) for b in m.finding_create_calls()]
        assert batch_sizes == [200, 50]

    def test_zero_findings_creates_no_finding_records(self):
        result = _make_result(findings=[])
        with _MockedService() as m:
            m.service.push(result, "ag2rPoc", "/path")
        assert m.finding_create_calls() == []

    def test_zero_findings_creates_no_junction_records(self):
        result = _make_result(findings=[])
        with _MockedService() as m:
            m.service.push(result, "ag2rPoc", "/path")
        assert m.junction_create_calls() == []
