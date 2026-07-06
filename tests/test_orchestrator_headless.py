"""
Tests for HeadlessOrchestrator and AssessmentResult.

Contract tested (no implementation read):
  HeadlessOrchestrator(source_path, rule_catalog, exclusions, scope, config)
    .run() → AssessmentResult

  AssessmentResult
    .snapshot  — MetadataSnapshot (has .metrics.score)
    .report    — AnalyzerReport   (has .severity_counts(), .all_findings())
    .scope     — str

Scope filtering contract:
  "all"      → all findings pass through
  "apex"     → only findings whose rule.scope starts with "apex"
  "flows"    → only findings whose rule.scope starts with "flow"
  "security" → only findings whose rule.scope starts with "security" / "profile" / "permission"
  "omni"     → only findings whose rule.scope starts with "omni" / "data_transform"
"""
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock


# ── Factories ──────────────────────────────────────────────────────────────────

def _make_rule(rule_id: str, scope: str = "apex_class", severity: str = "Major"):
    r = MagicMock()
    r.id = rule_id
    r.scope = scope
    r.severity = severity
    r.description = ""
    r.remediation = ""
    return r


def _make_finding(rule_id: str, scope: str, target_name: str = "SomeClass"):
    f = MagicMock()
    f.rule = _make_rule(rule_id, scope)
    f.target_kind = scope
    f.target_name = target_name
    f.message = ""
    f.source_path = None
    f.line = None
    return f


def _make_report(findings: list):
    """Builds a minimal fake AnalyzerReport whose all_findings() returns `findings`."""
    report = MagicMock()
    report.all_findings.return_value = findings
    # severity_counts derived from mocked findings
    counts = {}
    for f in findings:
        sev = f.rule.severity
        counts[sev] = counts.get(sev, 0) + 1
    report.severity_counts.return_value = counts
    # All dict-of-dict attributes empty by default (scope filter iterates them)
    for attr in ("apex", "flows", "objects", "validation_rules", "duplicate_rules",
                 "data_transforms", "agents", "prompts", "lwc", "aura", "security"):
        setattr(report, attr, {})
    report.rules_used = []
    return report


def _make_snapshot():
    snap = MagicMock()
    snap.metrics.score = 72
    snap.metrics.apex_classes = 5
    snap.metrics.apex_triggers = 2
    snap.metrics.flows = 10
    snap.metrics.lwc_count = 3
    return snap


def _make_catalog():
    from src.analyzer.rule_catalog import RuleCatalog
    return RuleCatalog.load()


def _make_orchestrator(scope="all", exclusions=None, source_path=None):
    from src.core.orchestrator_headless import HeadlessOrchestrator
    return HeadlessOrchestrator(
        source_path=source_path or Path("/tmp/fake-project"),
        rule_catalog=_make_catalog(),
        exclusions=exclusions or {},
        scope=scope,
    )


# ══════════════════════════════════════════════════════════════════════════════
# AssessmentResult — structural contract
# ══════════════════════════════════════════════════════════════════════════════

class TestAssessmentResult:

    def test_has_snapshot_report_scope_attributes(self):
        from src.core.orchestrator_headless import AssessmentResult
        snap = _make_snapshot()
        report = _make_report([])
        result = AssessmentResult(snapshot=snap, report=report, scope="all")
        assert result.snapshot is snap
        assert result.report is report
        assert result.scope == "all"


# ══════════════════════════════════════════════════════════════════════════════
# HeadlessOrchestrator.run() — parser and engine are mocked
# ══════════════════════════════════════════════════════════════════════════════

class TestHeadlessOrchestratorRun:

    def _run_with_mocks(self, scope="all", findings=None, exclusions=None):
        """Helper: patches parser + engine, runs orchestrator, returns (result, engine_mock)."""
        snap = _make_snapshot()
        report = _make_report(findings or [])
        engine_mock = MagicMock()
        engine_mock.analyze_snapshot.return_value = report
        engine_mock.rule_exclusions = {}

        with patch("src.parsers.salesforce_parser.SalesforceMetadataParser") as MockParser, \
             patch("src.analyzer.engine.AnalyzerEngine") as MockEngine:
            MockParser.return_value.parse.return_value = snap
            MockEngine.return_value = engine_mock

            orch = _make_orchestrator(scope=scope, exclusions=exclusions or {})
            result = orch.run()

        return result, engine_mock

    def test_run_returns_assessment_result(self):
        from src.core.orchestrator_headless import AssessmentResult
        result, _ = self._run_with_mocks()
        assert isinstance(result, AssessmentResult)

    def test_result_contains_snapshot(self):
        result, _ = self._run_with_mocks()
        assert result.snapshot is not None
        assert hasattr(result.snapshot, "metrics")

    def test_result_contains_report(self):
        result, _ = self._run_with_mocks()
        assert result.report is not None
        assert hasattr(result.report, "severity_counts")
        assert hasattr(result.report, "all_findings")

    def test_result_scope_matches_input(self):
        result, _ = self._run_with_mocks(scope="apex")
        assert result.scope == "apex"

    def test_exclusions_injected_into_engine(self):
        exclusions = {"APEX-001": {"ClassA", "ClassB"}}
        _, engine_mock = self._run_with_mocks(exclusions=exclusions)
        assert engine_mock.rule_exclusions == exclusions

    def test_engine_receives_parsed_snapshot(self):
        snap = _make_snapshot()
        report = _make_report([])
        engine_mock = MagicMock()
        engine_mock.analyze_snapshot.return_value = report
        engine_mock.rule_exclusions = {}

        with patch("src.parsers.salesforce_parser.SalesforceMetadataParser") as MockParser, \
             patch("src.analyzer.engine.AnalyzerEngine") as MockEngine:
            MockParser.return_value.parse.return_value = snap
            MockEngine.return_value = engine_mock
            _make_orchestrator(scope="all").run()

        engine_mock.analyze_snapshot.assert_called_once_with(snap)


# ══════════════════════════════════════════════════════════════════════════════
# Scope filtering — findings with mismatched scopes must be dropped
# ══════════════════════════════════════════════════════════════════════════════

class TestScopeFiltering:
    """
    Tests scope filtering by injecting findings with known rule.scope values
    and asserting which survive. Parser + engine are mocked.
    """

    def _run_scoped(self, scope: str, findings: list):
        snap = _make_snapshot()
        report = _make_report(findings)

        # Populate the dict attributes so _filter_report can iterate
        for f in findings:
            attr = self._scope_attr(f.rule.scope)
            if attr:
                existing = getattr(report, attr, {})
                existing.setdefault(f.target_name, []).append(f)
                setattr(report, attr, existing)

        engine_mock = MagicMock()
        engine_mock.analyze_snapshot.return_value = report
        engine_mock.rule_exclusions = {}

        with patch("src.parsers.salesforce_parser.SalesforceMetadataParser") as MockParser, \
             patch("src.analyzer.engine.AnalyzerEngine") as MockEngine:
            MockParser.return_value.parse.return_value = snap
            MockEngine.return_value = engine_mock
            orch = _make_orchestrator(scope=scope)
            return orch.run()

    def _scope_attr(self, rule_scope: str) -> str:
        if rule_scope.startswith("apex"):
            return "apex"
        if rule_scope.startswith("flow"):
            return "flows"
        if rule_scope.startswith("security") or rule_scope.startswith("profile"):
            return "security"
        return "objects"

    def test_scope_all_keeps_all_findings(self):
        findings = [
            _make_finding("R1", "apex_class"),
            _make_finding("R2", "flow"),
            _make_finding("R3", "security"),
        ]
        result = self._run_scoped("all", findings)
        found = result.report.all_findings()
        assert len(found) == 3

    def test_scope_apex_keeps_only_apex_findings(self):
        findings = [
            _make_finding("R1", "apex_class", "ClassA"),
            _make_finding("R2", "apex_trigger", "TriggerA"),
            _make_finding("R3", "flow", "MyFlow"),
            _make_finding("R4", "security", "ProfileX"),
        ]
        result = self._run_scoped("apex", findings)
        kept = result.report.all_findings()
        assert all(f.rule.scope.startswith("apex") for f in kept)
        assert len(kept) == 2

    def test_scope_flows_keeps_only_flow_findings(self):
        findings = [
            _make_finding("R1", "flow", "MyFlow"),
            _make_finding("R2", "apex_class", "ClassA"),
        ]
        result = self._run_scoped("flows", findings)
        kept = result.report.all_findings()
        assert all(f.rule.scope.startswith("flow") for f in kept)

    def test_scope_all_does_not_filter_anything(self):
        findings = [_make_finding(f"R{i}", s) for i, s in
                    enumerate(["apex_class", "flow", "security", "omni_script", "object"])]
        result = self._run_scoped("all", findings)
        assert len(result.report.all_findings()) == 5
