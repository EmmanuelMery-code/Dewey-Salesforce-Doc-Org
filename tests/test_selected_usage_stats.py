"""Tests for the *Ce qui est utilise* section of ``customisation.html``."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.customization_metrics import compute_selected_usage_stats
from src.core.models import FieldInfo, MetadataSnapshot, ObjectInfo
from src.reporting.html.renderers.customisation import write_customisation_page


def _object(api_name: str, *fields: tuple[str, bool]) -> ObjectInfo:
    return ObjectInfo(
        api_name=api_name,
        label=api_name,
        custom="__" in api_name,
        fields=[
            FieldInfo(api_name=name, label=name, custom=custom)
            for name, custom in fields
        ],
    )


def _snapshot() -> MetadataSnapshot:
    return MetadataSnapshot(
        source_dir=Path("."),
        package_roots=[],
        objects=[
            # Selected below.
            _object("Account", ("Name", False), ("Segment__c", True)),
            _object("Contract__c", ("Name", False), ("Amount__c", True)),
            _object("Routing__mdt", ("Rule__c", True)),
            _object("Case", ("Subject", False), ("Reason__c", True)),
            # Left out of the selection.
            _object("Lead", ("Name", False), ("Score__c", True), ("Origin__c", True)),
            _object("Audit__c", ("Name", False)),
            _object("Feature__mdt", ("Flag__c", True), ("Owner__c", True)),
        ]
    )


class TestComputeSelectedUsageStats:
    def test_no_selection_yields_no_section(self) -> None:
        assert compute_selected_usage_stats(_snapshot(), None) is None
        assert compute_selected_usage_stats(_snapshot(), set()) is None

    def test_objects_are_split_between_mdt_custom_and_standard(self) -> None:
        stats = compute_selected_usage_stats(
            _snapshot(), {"Account", "Contract__c", "Routing__mdt"}
        )
        assert stats is not None and stats.objects is not None

        custom, standard, metadata = stats.objects.buckets
        assert (custom.used, custom.total) == (1, 2)  # Contract__c of 2 custom objects
        assert (standard.used, standard.total) == (1, 3)  # Account of 3 standard
        assert (metadata.used, metadata.total) == (1, 2)

    def test_object_percentages_split_the_used_objects(self) -> None:
        """Not a coverage of the org: a share of what the selection holds."""
        stats = compute_selected_usage_stats(
            _snapshot(), {"Account", "Case", "Contract__c", "Routing__mdt"}
        )
        assert stats is not None and stats.objects is not None

        custom, standard, metadata = stats.objects.buckets
        # 1 custom + 2 standard used, so the split is 1/3 and 2/3.
        assert stats.objects.percent(custom) == pytest.approx(33.3, abs=0.1)
        assert stats.objects.percent(standard) == pytest.approx(66.7, abs=0.1)
        assert stats.objects.percent(metadata) is None
        assert stats.objects.total.used == 3

    def test_fields_list_custom_objects_then_the_standard_split(self) -> None:
        stats = compute_selected_usage_stats(
            _snapshot(), {"Account", "Contract__c", "Routing__mdt"}
        )
        assert stats is not None and stats.fields is not None

        on_custom, custom_on_standard, standard_on_standard, metadata = (
            stats.fields.buckets
        )
        # Every field of a custom object counts, custom or not.
        assert (on_custom.used, on_custom.total) == (2, 3)
        # Account contributes Segment__c as custom and Name as standard.
        assert (custom_on_standard.used, custom_on_standard.total) == (1, 4)
        assert (standard_on_standard.used, standard_on_standard.total) == (1, 3)
        assert (metadata.used, metadata.total) == (1, 3)

    def test_field_percentages_only_split_the_standard_objects(self) -> None:
        stats = compute_selected_usage_stats(
            _snapshot(), {"Account", "Contract__c", "Routing__mdt"}
        )
        assert stats is not None and stats.fields is not None

        on_custom, custom_on_standard, standard_on_standard, metadata = (
            stats.fields.buckets
        )
        assert stats.fields.percent(on_custom) is None
        assert stats.fields.percent(metadata) is None
        # Account is the only standard object used: 1 custom + 1 standard field.
        assert stats.fields.percent(custom_on_standard) == 50.0
        assert stats.fields.percent(standard_on_standard) == 50.0
        assert stats.fields.total.used == 2

    def test_selection_entries_absent_from_the_snapshot_are_ignored(self) -> None:
        stats = compute_selected_usage_stats(_snapshot(), {"Account", "Ghost__c"})
        assert stats is not None and stats.objects is not None

        assert stats.matched_count == 1
        assert stats.objects.total.used == 1

    def test_a_selection_of_custom_objects_only_leaves_no_field_split(self) -> None:
        stats = compute_selected_usage_stats(_snapshot(), {"Contract__c"})
        assert stats is not None and stats.fields is not None

        assert stats.fields.base == 0
        assert all(
            stats.fields.percent(bucket) is None for bucket in stats.fields.buckets
        )


class TestRenderedPage:
    def test_section_sits_above_the_per_object_detail(self, tmp_path: Path) -> None:
        stats = compute_selected_usage_stats(_snapshot(), {"Account"})

        page = write_customisation_page(
            _snapshot(),
            None,
            tmp_path,
            tmp_path / "assets",
            lambda _message: None,
            usage_stats=stats,
        )
        html = page.read_text(encoding="utf-8")

        assert html.index("Ce qui est utilise") < html.index("Detail par objet")

    def test_section_is_absent_without_a_selection(self, tmp_path: Path) -> None:
        page = write_customisation_page(
            _snapshot(),
            None,
            tmp_path,
            tmp_path / "assets",
            lambda _message: None,
        )

        assert "Ce qui est utilise" not in page.read_text(encoding="utf-8")
