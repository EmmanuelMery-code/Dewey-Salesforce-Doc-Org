"""Tests for the flow coverage exclusion feature (Mode A only).

Covers:
- src.core.flow_coverage_exclusions (load/save round trip, defaults)
- src.core.orchestrator.data_loading_mixin.apply_test_coverage honouring
  excluded_flow_process_types.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.flow_coverage_exclusions import (
    DEFAULT_EXCLUDED_FLOW_PROCESS_TYPES,
    load_flow_coverage_exclusions,
    save_flow_coverage_exclusions,
)
from src.core.models import FlowInfo, MetadataSnapshot
from src.core.orchestrator.data_loading_mixin import apply_test_coverage


# ══════════════════════════════════════════════════════════════════════════
# load_flow_coverage_exclusions / save_flow_coverage_exclusions
# ══════════════════════════════════════════════════════════════════════════


class TestLoadFlowCoverageExclusions:
    def test_no_config_path_returns_default(self):
        assert load_flow_coverage_exclusions(None) == set(DEFAULT_EXCLUDED_FLOW_PROCESS_TYPES)

    def test_missing_file_returns_default(self, tmp_path: Path):
        missing = tmp_path / "does_not_exist.json"
        assert load_flow_coverage_exclusions(missing) == set(DEFAULT_EXCLUDED_FLOW_PROCESS_TYPES)

    def test_file_without_key_returns_default(self, tmp_path: Path):
        config = tmp_path / "exclusions.json"
        config.write_text(json.dumps({"metadata_exclusions": []}), encoding="utf-8")
        assert load_flow_coverage_exclusions(config) == set(DEFAULT_EXCLUDED_FLOW_PROCESS_TYPES)

    def test_explicit_empty_list_disables_default(self, tmp_path: Path):
        """An explicitly saved empty list means the user opted out of any exclusion."""
        config = tmp_path / "exclusions.json"
        config.write_text(json.dumps({"flow_coverage_exclusions": []}), encoding="utf-8")
        assert load_flow_coverage_exclusions(config) == set()

    def test_custom_list_is_respected(self, tmp_path: Path):
        config = tmp_path / "exclusions.json"
        config.write_text(
            json.dumps({"flow_coverage_exclusions": ["Flow", "Workflow"]}), encoding="utf-8"
        )
        assert load_flow_coverage_exclusions(config) == {"Flow", "Workflow"}


class TestSaveFlowCoverageExclusions:
    def test_creates_file_when_missing(self, tmp_path: Path):
        config = tmp_path / "sub" / "exclusions.json"
        save_flow_coverage_exclusions(config, {"Flow"})
        assert config.exists()
        data = json.loads(config.read_text(encoding="utf-8"))
        assert data["flow_coverage_exclusions"] == ["Flow"]

    def test_preserves_other_keys(self, tmp_path: Path):
        config = tmp_path / "exclusions.json"
        config.write_text(
            json.dumps(
                {
                    "metadata_exclusions": [{"type": "flow", "element": "Foo"}],
                    "rule_exclusions": [{"type": "apex", "metadata_name": "Bar", "rule_id": "R1"}],
                }
            ),
            encoding="utf-8",
        )

        save_flow_coverage_exclusions(config, {"Flow", "AutoLaunchedFlow"})

        data = json.loads(config.read_text(encoding="utf-8"))
        assert data["metadata_exclusions"] == [{"type": "flow", "element": "Foo"}]
        assert data["rule_exclusions"] == [
            {"type": "apex", "metadata_name": "Bar", "rule_id": "R1"}
        ]
        assert sorted(data["flow_coverage_exclusions"]) == ["AutoLaunchedFlow", "Flow"]

    def test_round_trip(self, tmp_path: Path):
        config = tmp_path / "exclusions.json"
        save_flow_coverage_exclusions(config, {"Flow", "Workflow"})
        assert load_flow_coverage_exclusions(config) == {"Flow", "Workflow"}


# ══════════════════════════════════════════════════════════════════════════
# apply_test_coverage — excluded_flow_process_types
# ══════════════════════════════════════════════════════════════════════════


def _make_snapshot(flows: list[FlowInfo]) -> MetadataSnapshot:
    return MetadataSnapshot(source_dir=Path("."), package_roots=[], flows=flows)


class TestApplyTestCoverageFlowExclusion:
    def test_excluded_flow_not_counted_in_average(self):
        screen_flow = FlowInfo(name="MyScreenFlow", process_type="Flow")
        auto_flow = FlowInfo(name="MyAutoFlow", process_type="AutoLaunchedFlow")
        snapshot = _make_snapshot([screen_flow, auto_flow])
        coverage_data = {
            "MyScreenFlow": {"percentage": 0.0},
            "MyAutoFlow": {"percentage": 100.0},
        }

        apply_test_coverage(
            snapshot, coverage_data, excluded_flow_process_types={"Flow"}
        )

        # Only the autolaunched flow counts towards the org-level average.
        assert snapshot.metrics.test_coverage == 100.0

    def test_excluded_flow_still_gets_its_own_coverage_populated(self):
        screen_flow = FlowInfo(name="MyScreenFlow", process_type="Flow")
        snapshot = _make_snapshot([screen_flow])
        coverage_data = {"MyScreenFlow": {"percentage": 42.0}}

        apply_test_coverage(
            snapshot, coverage_data, excluded_flow_process_types={"Flow"}
        )

        # Excluded from the aggregate...
        assert snapshot.metrics.test_coverage == 0.0
        # ...but still informationally populated on the flow itself.
        assert screen_flow.test_coverage == 42.0

    def test_no_exclusion_by_default(self):
        """Without an explicit exclusion set, apply_test_coverage behaves as before
        (Mode B / historical callers keep their unfiltered behaviour)."""
        screen_flow = FlowInfo(name="MyScreenFlow", process_type="Flow")
        snapshot = _make_snapshot([screen_flow])
        coverage_data = {"MyScreenFlow": {"percentage": 42.0}}

        apply_test_coverage(snapshot, coverage_data)

        assert snapshot.metrics.test_coverage == 42.0
