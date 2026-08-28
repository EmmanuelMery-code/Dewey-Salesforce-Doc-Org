"""Tests for the Data Dictionary object selection shared by both entry points."""

from __future__ import annotations

from datetime import date

from src.core.data_dictionary_selection import (
    DataDictionarySelection,
    data_dictionary_filename_base,
)
from src.core.models import FieldInfo, ObjectInfo


def _object(api_name: str, *field_names: str) -> ObjectInfo:
    return ObjectInfo(
        api_name=api_name,
        label=api_name,
        description=f"Description de {api_name}",
        fields=[FieldInfo(api_name=name, label=name) for name in field_names],
    )


class TestApply:
    def test_only_the_selected_objects_are_kept(self) -> None:
        selection = DataDictionarySelection(objects={"Account", "Contract__c"})

        kept = selection.apply(
            [_object("Account"), _object("Lead"), _object("Contract__c")]
        )

        assert [obj.api_name for obj in kept] == ["Account", "Contract__c"]

    def test_extra_info_is_attached_to_objects_and_fields(self) -> None:
        selection = DataDictionarySelection(
            objects={"Account"},
            object_comments={"Account": "Objet pivot"},
            object_piloted_by={"Account": "Squad CRM"},
            object_status={"Account": "Livré"},
            object_squad={"Account": "Alpha"},
            object_squad_consumer={"Account": "Beta"},
            field_comments={"Account": {"Name": "Raison sociale"}},
            field_piloted_by={"Account": {"Name": "Squad CRM"}},
        )

        account = selection.apply([_object("Account", "Name", "Industry")])[0]

        assert account.dewey_comment == "Objet pivot"
        assert account.dewey_piloted_by == "Squad CRM"
        assert account.dewey_status == "Livré"
        assert account.dewey_squad == "Alpha"
        assert account.dewey_squad_consumer == "Beta"
        assert account.dewey_comment_combined == "Description de Account Objet pivot"
        name, industry = account.fields
        assert (name.dewey_comment, name.dewey_piloted_by) == (
            "Raison sociale",
            "Squad CRM",
        )
        assert (industry.dewey_comment, industry.dewey_piloted_by) == ("", "")

    def test_source_objects_are_left_untouched(self) -> None:
        """The same snapshot also feeds the HTML pages and the full
        ``data_dictionary.xlsx``, which must keep the raw metadata."""
        selection = DataDictionarySelection(
            objects={"Account"},
            object_comments={"Account": "Objet pivot"},
            field_comments={"Account": {"Name": "Raison sociale"}},
        )
        source = _object("Account", "Name")

        selection.apply([source])

        assert source.dewey_comment == ""
        assert source.fields[0].dewey_comment == ""

    def test_parsed_automation_usages_survive_the_copy(self) -> None:
        """The usages are computed by the parser, before the selection copies
        the fields to attach the free text."""
        source = _object("Account", "Name")
        source.fields[0].automation_usages = ["Flow", "Apex"]

        account = DataDictionarySelection(objects={"Account"}).apply([source])[0]

        assert account.fields[0].automation_usage_label == "Flow, Apex"

    def test_objects_without_extra_info_fall_back_to_defaults(self) -> None:
        account = DataDictionarySelection(objects={"Account"}).apply(
            [_object("Account", "Name")]
        )[0]

        assert account.dewey_comment == ""
        assert account.dewey_status == "-"


class TestFromSettings:
    def test_reads_the_data_dictionary_screen_settings(self) -> None:
        selection = DataDictionarySelection.from_settings(
            {
                "dd_selected_objects": ["Account", "Lead"],
                "dd_object_comments": {"Account": "Objet pivot"},
                "dd_field_piloted_by": {"Account": {"Name": "Squad CRM"}},
                "dd_include_status": False,
                "dd_include_field_automation": False,
                "dd_concat_description_in_comment": False,
            }
        )

        assert selection.objects == {"Account", "Lead"}
        assert selection.object_comments == {"Account": "Objet pivot"}
        assert selection.field_piloted_by == {"Account": {"Name": "Squad CRM"}}
        assert selection.include_status is False
        assert selection.include_field_automation is False
        assert selection.concat_description is False
        # Unset toggles keep the screen's own defaults.
        assert selection.include_comment is True

    def test_empty_settings_yield_an_empty_selection(self) -> None:
        selection = DataDictionarySelection.from_settings({})

        assert selection.objects == set()
        assert selection.object_comments == {}
        assert selection.field_comments == {}

    def test_corrupt_settings_are_ignored(self) -> None:
        selection = DataDictionarySelection.from_settings(
            {"dd_object_comments": "not-a-mapping", "dd_field_comments": []}
        )

        assert selection.object_comments == {}
        assert selection.field_comments == {}


class TestWorkbookOptions:
    def test_exposes_the_nine_writer_toggles(self) -> None:
        options = DataDictionarySelection(
            include_squad=False, include_field_automation=False
        ).workbook_options()

        assert options["include_squad"] is False
        assert options["include_field_automation"] is False
        assert options["include_comment"] is True
        assert len(options) == 9


def test_filename_base_is_dated() -> None:
    assert (
        data_dictionary_filename_base(date(2026, 7, 10)) == "dataDictionnary_20260710"
    )
