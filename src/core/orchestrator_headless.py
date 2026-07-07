"""
HeadlessOrchestrator — Mode B
Wraps SalesforceMetadataParser + AnalyzerEngine without any UI callback.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Scope → rule scope prefixes used to filter findings
_SCOPE_PREFIXES: dict[str, list[str]] = {
    "apex":     ["apex"],
    "flows":    ["flow"],
    "security": ["security", "profile", "permission"],
    "omni":     ["omni", "data_transform"],
    "all":      [],  # empty = no filter
}


@dataclass
class AssessmentResult:
    snapshot: object   # MetadataSnapshot
    report: object     # AnalyzerReport
    scope: str


class HeadlessOrchestrator:
    """
    Runs a full Dewey assessment without any UI.

    Parameters
    ----------
    source_path : Path
        Root of the Salesforce DX project to analyse.
    rule_catalog : RuleCatalog
        Preloaded catalog (from SF or rules.xml fallback).
    exclusions : dict[str, set[str]]
        Mapping rule_id → set of component names to exclude.
    scope : str
        One of "all", "apex", "flows", "security", "omni".
    config : SfConfig
        Unused in v1 — reserved for weight/threshold overrides.
    """

    def __init__(
        self,
        source_path: Path,
        rule_catalog,
        exclusions: dict[str, set[str]],
        scope: str = "all",
        config=None,
        pmd_ruleset_path: str | Path | None = None,
        pmd_ref_map: dict[str, str] | None = None,
        analyzer: str = "none",
        sfca_ref_map: dict[str, str] | None = None,
    ) -> None:
        self.source_path = Path(source_path)
        self.rule_catalog = rule_catalog
        self.exclusions = exclusions
        self.scope = scope
        self.config = config
        self.pmd_ruleset_path = Path(pmd_ruleset_path) if pmd_ruleset_path else None
        self.pmd_ref_map = pmd_ref_map or {}
        self.analyzer = analyzer  # "pmd" | "sfca" | "none"
        self.sfca_ref_map = sfca_ref_map or {}

    def run(self) -> AssessmentResult:
        from src.parsers.salesforce_parser import SalesforceMetadataParser
        from src.analyzer.engine import AnalyzerEngine

        # ── Parse ──────────────────────────────────────────────────────────────
        parser = SalesforceMetadataParser(
            source_dir=self.source_path,
            log_callback=self._log,
        )
        snapshot = parser.parse()

        # ── Adoption posture ───────────────────────────────────────────────────
        from src.core.customization_metrics import compute_adoption_stats
        snapshot.adoption_stats = compute_adoption_stats(snapshot)

        # ── Analyse ────────────────────────────────────────────────────────────
        engine = AnalyzerEngine(catalog=self.rule_catalog)
        engine.rule_exclusions = self.exclusions
        report = engine.analyze_snapshot(snapshot)

        # ── Static analysis (PMD or SFCA) ─────────────────────────────────────
        if self.analyzer == "pmd":
            if self.pmd_ruleset_path and self.pmd_ref_map and snapshot.apex_artifacts:
                self._run_pmd(snapshot, report)
        elif self.analyzer == "sfca":
            self._run_sfca(snapshot, report)

        # ── Scope filter ───────────────────────────────────────────────────────
        if self.scope != "all":
            report = self._filter_report(report, self.scope)

        return AssessmentResult(snapshot=snapshot, report=report, scope=self.scope)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _log(self, message: str) -> None:
        if message:
            tag = "sfca" if self.analyzer == "sfca" else "pmd"
            print(f"      [{tag}] {message}")

    def _ensure_java_in_path(self) -> None:
        """Prepend Homebrew OpenJDK to PATH if a real JVM is not available."""
        import os, shutil, subprocess
        java = shutil.which("java")
        if java:
            # Verify it's a real JVM (not a stub like the SF /usr/local/bin/java wrapper)
            r = subprocess.run([java, "-version"], capture_output=True, text=True)
            if "version" in r.stderr.lower() or "version" in r.stdout.lower():
                return  # real JVM found
        for candidate in (
            "/opt/homebrew/opt/openjdk/bin",
            "/usr/local/opt/openjdk/bin",
        ):
            if Path(candidate).is_dir():
                os.environ["PATH"] = candidate + os.pathsep + os.environ.get("PATH", "")
                return

    def _run_pmd(self, snapshot, report) -> None:
        from src.core.pmd_service import PmdService
        from src.analyzer.models import Finding, Rule

        self._ensure_java_in_path()
        pmd_svc = PmdService(self.source_path, log_callback=self._log)
        pmd_result = pmd_svc.analyze_apex(
            snapshot.apex_artifacts,
            ruleset_path=self.pmd_ruleset_path,
        )
        if not pmd_result.violations:
            return

        catalog_by_id: dict[str, Rule] = {r.id: r for r in self.rule_catalog.all}
        injected = 0
        for violation in pmd_result.violations:
            rule_id = self.pmd_ref_map.get(violation.rule)
            if not rule_id:
                continue
            rule = catalog_by_id.get(rule_id)
            if not rule:
                continue
            artifact_name = violation.file_path.stem
            finding = Finding(
                rule=rule,
                target_kind="apex_class",
                target_name=artifact_name,
                message=violation.message or rule.description,
                source_path=violation.file_path,
                line=violation.begin_line or None,
            )
            report.apex.setdefault(artifact_name, []).append(finding)
            injected += 1

        if injected:
            print(f"      [pmd] {injected} finding(s) injected from {len(pmd_result.violations)} violation(s)")

    def _run_sfca(self, snapshot, report) -> None:
        from src.core.sfca_service import SfcaService
        from src.analyzer.models import Finding

        sfca_svc = SfcaService(self.source_path, log_callback=self._log)
        violations = sfca_svc.analyze()
        if not violations:
            return

        catalog_by_id: dict[str, object] = {r.id: r for r in self.rule_catalog.all}
        injected = 0
        for violation in violations:
            rule_id = self.sfca_ref_map.get(violation.rule)
            if not rule_id:
                continue
            rule = catalog_by_id.get(rule_id)
            if not rule:
                continue

            file_path = violation.file_path
            suffix = file_path.suffix.lower()
            if suffix == ".cls":
                target_kind = "apex_class"
                section = report.apex
            elif suffix in (".js", ".html"):
                target_kind = "lwc"
                section = report.lwc
            elif file_path.parent.parent.name == "aura":
                target_kind = "aura"
                section = report.aura
            else:
                target_kind = "apex_class"
                section = report.apex

            artifact_name = file_path.stem
            finding = Finding(
                rule=rule,
                target_kind=target_kind,
                target_name=artifact_name,
                message=violation.message or rule.description,
                source_path=file_path,
                line=violation.begin_line or None,
            )
            section.setdefault(artifact_name, []).append(finding)
            injected += 1

        if injected:
            print(f"      [sfca] {injected} finding(s) injected from {len(violations)} violation(s)")

    def _filter_report(self, report, scope: str):
        """
        Returns a shallow copy of AnalyzerReport with only findings whose
        rule.scope starts with one of the scope prefixes.
        """
        from src.analyzer.engine import AnalyzerReport

        prefixes = _SCOPE_PREFIXES.get(scope, [])
        if not prefixes:
            return report

        def _keep(rule_scope: str) -> bool:
            return any(rule_scope.startswith(p) for p in prefixes)

        def _filter_dict(d: dict) -> dict:
            return {
                name: [f for f in findings if _keep(f.rule.scope)]
                for name, findings in d.items()
            }

        return AnalyzerReport(
            apex=_filter_dict(report.apex),
            flows=_filter_dict(report.flows),
            objects=_filter_dict(report.objects),
            validation_rules=_filter_dict(report.validation_rules),
            duplicate_rules=_filter_dict(report.duplicate_rules),
            data_transforms=_filter_dict(report.data_transforms),
            agents=_filter_dict(report.agents),
            prompts=_filter_dict(report.prompts),
            lwc=_filter_dict(report.lwc),
            aura=_filter_dict(report.aura),
            security=_filter_dict(report.security),
            rules_used=report.rules_used,
        )
