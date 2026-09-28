"""Apex coverage must not flag test classes nor classes without coverable lines."""

from __future__ import annotations

from pathlib import Path

from src.core.models import ApexArtifact, MetadataSnapshot
from src.core.orchestrator.data_loading_mixin import apply_test_coverage
from src.reporting.html.coverage_alert import coverage_alert_marker


def _artifact(name: str, is_test: bool = False) -> ApexArtifact:
    artifact = ApexArtifact(name=name, kind="class", body="", source_path=Path(f"{name}.cls"))
    artifact.is_test = is_test
    return artifact


def _lines(covered: int, uncovered: int) -> dict:
    total = covered + uncovered
    return {
        "percentage": (covered / total * 100) if total else 0.0,
        "lines_covered": covered,
        "lines_uncovered": uncovered,
        "lines_total": total,
    }


def test_test_class_gets_no_coverage():
    test_class = _artifact("AccountServiceTest", is_test=True)
    snapshot = MetadataSnapshot(source_dir=Path("."), package_roots=[], apex_artifacts=[test_class])

    apply_test_coverage(snapshot, {"AccountServiceTest": _lines(0, 12)})

    assert test_class.test_coverage is None


def test_zero_coverable_lines_is_unknown_and_not_averaged():
    empty = _artifact("Constants")
    covered = _artifact("AccountService")
    snapshot = MetadataSnapshot(
        source_dir=Path("."), package_roots=[], apex_artifacts=[empty, covered]
    )

    apply_test_coverage(snapshot, {"Constants": _lines(0, 0), "AccountService": _lines(9, 1)})

    assert empty.test_coverage is None
    assert covered.test_coverage == 90.0
    assert snapshot.metrics.test_coverage == 90.0


def test_marker_ignores_test_classes():
    assert coverage_alert_marker(0.0, is_test=True) == ""
    assert "coverage-alert" in coverage_alert_marker(0.0)
