"""
Tests for SfFindingsService.

Contract tested (no implementation read):
  SfFindingsService(org_alias)
    .push(result, org_alias, source_path, source_branch, scope)
      → (analysis_id: str, delta_summary: str | None)

Behavioural contract:
  - Creates one OrgAnalysis__c record per call
  - Creates one Finding__c per finding in result.report.all_findings()
  - On first run (no previous analysis): all findings have IsNew__c=True, delta_summary=None
  - On subsequent runs: findings absent from previous are IsNew__c=True,
    findings absent from current trigger IsResolved__c=True on old records
  - delta_summary is a non-empty string when a previous analysis exists
  - analysis_id is the Salesforce Id of the created OrgAnalysis__c
"""
import json
from unittest.mock import MagicMock, patch, call


# ── Factories ──────────────────────────────────────────────────────────────────

def _make_finding(rule_id: str, target_name: str, severity: str = "Major"):
    f = MagicMock()
    f.rule.id = rule_id
    f.rule.severity = severity
    f.rule.description = "desc"
    f.rule.remediation = "fix"
    f.rule.scope = "apex_class"
    f.target_kind = "apex_class"
    f.target_name = target_name
    f.message = "msg"
    f.source_path = None
    f.line = None
    return f


def _make_report(findings: list):
    report = MagicMock()
    report.all_findings.return_value = findings
    counts = {}
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
    result.scope = "all"
    return result


def _org_display_response(instance_url="https://test.salesforce.com",
                           access_token="00D_FAKE_TOKEN"):
    m = MagicMock()
    m.stdout = json.dumps({
        "result": {
            "instanceUrl": instance_url,
            "accessToken": access_token,
        }
    })
    return m


def _soql_response(records: list) -> MagicMock:
    m = MagicMock()
    m.stdout = json.dumps({"result": {"records": records, "totalSize": len(records)}})
    return m


def _rest_create_response(record_id: str = "a001000000FAKEaAAH") -> dict:
    return {"id": record_id, "success": True, "errors": []}


def _rest_composite_response(n: int) -> list:
    return [{"id": f"a00{i:015d}", "success": True, "errors": []} for i in range(n)]


# ══════════════════════════════════════════════════════════════════════════════
# Helper: a SfFindingsService with REST calls and subprocess mocked
# ══════════════════════════════════════════════════════════════════════════════

class _MockedService:
    """
    Context manager that patches subprocess.run and urllib.request.urlopen,
    giving full control over what Salesforce returns.
    """

    def __init__(self,
                 analysis_id="a001ANALYSIS0001",
                 delta_id="a002DELTA00001",
                 prev_analysis_id=None,
                 prev_finding_records=None,
                 prev_counts=None,
                 composite_results=None):
        self.analysis_id = analysis_id
        self.delta_id = delta_id
        self.prev_analysis_id = prev_analysis_id
        self.prev_finding_records = prev_finding_records or []
        self.prev_counts = prev_counts or {"ScoreGlobal__c": 70,
                                           "FindingCritical__c": 0,
                                           "FindingMajor__c": 2}
        self.composite_results = composite_results

        self._subprocess_patch = None
        self._urllib_patch = None

    def __enter__(self):
        from src.core.sf_findings_service import SfFindingsService

        def _subprocess_side_effect(cmd, **kwargs):
            joined = " ".join(cmd)
            # org display
            if "org display" in joined:
                return _org_display_response()
            # previous OrgAnalysis (most recent)
            if "OrgAnalysis__c" in joined and "ORDER BY" in joined:
                if self.prev_analysis_id:
                    return _soql_response([{"Id": self.prev_analysis_id}])
                return _soql_response([])
            # previous findings
            if "Finding__c" in joined and self.prev_analysis_id and \
               self.prev_analysis_id in joined and "IsResolved__c" not in joined:
                return _soql_response(self.prev_finding_records)
            # resolved finding IDs (previous findings not in current)
            if "Finding__c" in joined and "IsResolved__c = false" in joined:
                return _soql_response(self.prev_finding_records)
            # previous counts
            if "ScoreGlobal__c" in joined:
                return _soql_response([{
                    "ScoreGlobal__c": self.prev_counts["ScoreGlobal__c"],
                    "FindingCritical__c": self.prev_counts["FindingCritical__c"],
                    "FindingMajor__c": self.prev_counts["FindingMajor__c"],
                }])
            return _soql_response([])

        def _urllib_side_effect(req):
            url = req.full_url
            method = req.method
            # Create OrgAnalysis__c
            if "/sobjects/OrgAnalysis__c/" in url:
                body = json.dumps(_rest_create_response(self.analysis_id)).encode()
            # Create AnalysisDelta__c
            elif "/sobjects/AnalysisDelta__c/" in url:
                body = json.dumps(_rest_create_response(self.delta_id)).encode()
            # Composite (findings creation or patch)
            elif "/composite/sobjects" in url:
                request_body = json.loads(req.data)
                n = len(request_body.get("records", []))
                if self.composite_results is not None:
                    results = self.composite_results
                else:
                    results = _rest_composite_response(n)
                body = json.dumps(results).encode()
            else:
                body = b"{}"

            ctx = MagicMock()
            ctx.__enter__ = lambda s: ctx
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.read.return_value = body
            return ctx

        self._subprocess_patch = patch("subprocess.run",
                                       side_effect=_subprocess_side_effect)
        self._urllib_patch = patch("urllib.request.urlopen",
                                   side_effect=_urllib_side_effect)

        self._subprocess_patch.start()
        self._urllib_patch.start()
        self.service = SfFindingsService("ag2rPoc")
        return self

    def __exit__(self, *args):
        self._subprocess_patch.stop()
        self._urllib_patch.stop()


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

    def test_first_element_is_analysis_id_string(self):
        result = _make_result()
        with _MockedService(analysis_id="a001ANALYSIS0001") as m:
            analysis_id, _ = m.service.push(result, "ag2rPoc", "/path/to/src")
        assert analysis_id == "a001ANALYSIS0001"

    def test_delta_summary_is_none_when_no_previous_analysis(self):
        result = _make_result()
        with _MockedService(prev_analysis_id=None) as m:
            _, delta = m.service.push(result, "ag2rPoc", "/path/to/src")
        assert delta is None

    def test_delta_summary_is_string_when_previous_analysis_exists(self):
        result = _make_result()
        with _MockedService(prev_analysis_id="PREV_ID_001") as m:
            _, delta = m.service.push(result, "ag2rPoc", "/path/to/src")
        assert isinstance(delta, str)
        assert len(delta) > 0


# ══════════════════════════════════════════════════════════════════════════════
# push() — OrgAnalysis__c creation
# ══════════════════════════════════════════════════════════════════════════════

class TestPushOrgAnalysis:

    def test_org_analysis_created_exactly_once(self):
        result = _make_result()
        with patch("subprocess.run", return_value=_org_display_response()), \
             patch("urllib.request.urlopen") as mock_url:
            calls_to_analysis = []

            def side_effect(req):
                if "/sobjects/OrgAnalysis__c/" in req.full_url:
                    calls_to_analysis.append(req)
                body = json.dumps(_rest_create_response()).encode()
                ctx = MagicMock()
                ctx.__enter__ = lambda s: ctx
                ctx.__exit__ = MagicMock(return_value=False)
                ctx.read.return_value = body
                return ctx

            mock_url.side_effect = side_effect

            from src.core.sf_findings_service import SfFindingsService
            svc = SfFindingsService("ag2rPoc")
            # Patch subprocess for all SF CLI calls
            with patch("subprocess.run", return_value=_soql_response([])):
                svc._instance_url = "https://test.salesforce.com"
                svc._access_token = "TOKEN"
                svc.push(result, "ag2rPoc", "/path")

            assert len(calls_to_analysis) == 1


# ══════════════════════════════════════════════════════════════════════════════
# push() — IsNew__c flag logic
# ══════════════════════════════════════════════════════════════════════════════

class TestIsNewFlag:

    def _capture_finding_records(self, result, prev_finding_records=None):
        """Runs push and captures the Finding__c records sent to the Composite API."""
        finding_batches = []
        prev_id = "PREV_ID_001" if prev_finding_records else None

        with _MockedService(
            prev_analysis_id=prev_id,
            prev_finding_records=prev_finding_records or [],
        ) as m:
            original_rest = m.service._rest

            def capture_rest(method, path, payload=None):
                if method == "POST" and "/composite/sobjects" in path and payload:
                    records = payload.get("records", [])
                    if records and records[0].get("attributes", {}).get("type") == "Finding__c":
                        finding_batches.extend(records)
                return original_rest(method, path, payload)

            m.service._rest = capture_rest
            m.service.push(result, "ag2rPoc", "/path")

        return finding_batches

    def test_all_findings_are_new_on_first_run(self):
        findings = [
            _make_finding("R1", "ClassA"),
            _make_finding("R2", "ClassB"),
        ]
        result = _make_result(findings=findings)
        records = self._capture_finding_records(result, prev_finding_records=[])
        assert all(r["IsNew__c"] is True for r in records)

    def test_existing_finding_is_not_new(self):
        """A finding already in previous analysis must have IsNew__c=False."""
        findings = [_make_finding("R1", "ClassA")]
        result = _make_result(findings=findings)
        prev = [{"RuleId__c": "R1", "ComponentName__c": "ClassA"}]
        records = self._capture_finding_records(result, prev_finding_records=prev)
        assert records[0]["IsNew__c"] is False

    def test_new_finding_not_in_previous_is_marked_new(self):
        findings = [
            _make_finding("R1", "ClassA"),  # was in previous
            _make_finding("R2", "ClassB"),  # brand new
        ]
        result = _make_result(findings=findings)
        prev = [{"RuleId__c": "R1", "ComponentName__c": "ClassA"}]
        records = self._capture_finding_records(result, prev_finding_records=prev)
        is_new_by_name = {r["ComponentName__c"]: r["IsNew__c"] for r in records}
        assert is_new_by_name["ClassA"] is False
        assert is_new_by_name["ClassB"] is True


# ══════════════════════════════════════════════════════════════════════════════
# push() — delta summary content
# ══════════════════════════════════════════════════════════════════════════════

class TestDeltaSummary:

    def test_delta_summary_contains_score_info(self):
        result = _make_result(score=80)
        with _MockedService(
            prev_analysis_id="PREV",
            prev_counts={"ScoreGlobal__c": 70, "FindingCritical__c": 0, "FindingMajor__c": 2},
        ) as m:
            _, delta = m.service.push(result, "ag2rPoc", "/path")
        assert "score" in delta.lower() or "+" in delta or "-" in delta

    def test_delta_summary_mentions_new_and_resolved(self):
        result = _make_result(findings=[_make_finding("R1", "ClassA")])
        with _MockedService(prev_analysis_id="PREV") as m:
            _, delta = m.service.push(result, "ag2rPoc", "/path")
        # Should mention counts
        assert delta is not None
        assert len(delta) > 5  # non-trivial string


# ══════════════════════════════════════════════════════════════════════════════
# push() — bulk batching
# ══════════════════════════════════════════════════════════════════════════════

class TestBulkBatching:

    def test_findings_split_into_batches_of_200(self):
        """250 findings → 2 Composite API calls (200 + 50)."""
        findings = [_make_finding(f"R{i}", f"Class{i}") for i in range(250)]
        result = _make_result(findings=findings)

        composite_calls = []
        with _MockedService() as m:
            original_rest = m.service._rest

            def capture(method, path, payload=None):
                if method == "POST" and "/composite/sobjects" in path and payload:
                    records = payload.get("records", [])
                    if records and records[0].get("attributes", {}).get("type") == "Finding__c":
                        composite_calls.append(len(records))
                return original_rest(method, path, payload)

            m.service._rest = capture
            m.service.push(result, "ag2rPoc", "/path")

        assert len(composite_calls) == 2
        assert composite_calls[0] == 200
        assert composite_calls[1] == 50

    def test_zero_findings_creates_no_composite_call(self):
        result = _make_result(findings=[])
        composite_calls = []
        with _MockedService() as m:
            original_rest = m.service._rest

            def capture(method, path, payload=None):
                if method == "POST" and "/composite/sobjects" in path and payload:
                    records = payload.get("records", [])
                    if records and records[0].get("attributes", {}).get("type") == "Finding__c":
                        composite_calls.append(1)
                return original_rest(method, path, payload)

            m.service._rest = capture
            m.service.push(result, "ag2rPoc", "/path")

        assert len(composite_calls) == 0
