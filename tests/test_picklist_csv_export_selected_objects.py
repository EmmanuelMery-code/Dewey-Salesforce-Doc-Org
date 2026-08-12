"""Tests: picklist CSV export restricted to a set of selected objects.

Contract tested:
  export_picklist_csvs(app, selected_objects={...}) only exports picklists
  for the given object API names, used by the "PickList CSV" button on the
  Data Dictionary screen (src/ui/data_dictionary_screen.py).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.ui.picklist_csv_export import export_picklist_csvs

ACCOUNT_OBJECT_META = """<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <label>Account</label>
</CustomObject>
"""

CONTACT_OBJECT_META = """<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <label>Contact</label>
</CustomObject>
"""

PICKLIST_FIELD_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>{field_name}</fullName>
    <label>{field_label}</label>
    <type>Picklist</type>
    <valueSet>
        <valueSetDefinition>
            <value>
                <fullName>A</fullName>
                <label>Valeur A</label>
            </value>
        </valueSetDefinition>
    </valueSet>
</CustomField>
"""


def _build_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"

    account_fields = source / "objects" / "Account" / "fields"
    account_fields.mkdir(parents=True, exist_ok=True)
    (source / "objects" / "Account" / "Account.object-meta.xml").write_text(
        ACCOUNT_OBJECT_META, encoding="utf-8"
    )
    (account_fields / "Status__c.field-meta.xml").write_text(
        PICKLIST_FIELD_TEMPLATE.format(field_name="Status__c", field_label="Status"),
        encoding="utf-8",
    )

    contact_fields = source / "objects" / "Contact" / "fields"
    contact_fields.mkdir(parents=True, exist_ok=True)
    (source / "objects" / "Contact" / "Contact.object-meta.xml").write_text(
        CONTACT_OBJECT_META, encoding="utf-8"
    )
    (contact_fields / "Level__c.field-meta.xml").write_text(
        PICKLIST_FIELD_TEMPLATE.format(field_name="Level__c", field_label="Level"),
        encoding="utf-8",
    )

    return source


class _FakeVar:
    def __init__(self, value: str) -> None:
        self._value = value

    def get(self) -> str:
        return self._value


class _FakeTaskManager:
    def __init__(self) -> None:
        self.result = None

    def queue_log(self, message: str) -> None:
        pass

    def start_task(self, *, status_text, task, success_message, on_success=None, notify=True):
        self.result = task()


def _build_fake_app(source: Path, output: Path) -> SimpleNamespace:
    task_manager = _FakeTaskManager()
    return SimpleNamespace(
        source_var=_FakeVar(str(source)),
        output_var=_FakeVar(str(output)),
        exclusion_file_var=_FakeVar(""),
        task_manager=task_manager,
        _t=lambda key, **kwargs: key,
        _validate_output_dir=lambda: output,
        _selected_exclusion_file=lambda: None,
    )


class TestPicklistCsvExportSelectedObjects:
    def test_only_selected_object_picklists_are_exported(self, tmp_path: Path) -> None:
        source = _build_source(tmp_path)
        output = tmp_path / "output"
        app = _build_fake_app(source, output)

        export_picklist_csvs(app, selected_objects={"Account"})

        assert (output / "picklist" / "fields" / "Account_Status__c.csv").exists()
        assert not (output / "picklist" / "fields" / "Contact_Level__c.csv").exists()

    def test_no_filter_exports_every_object(self, tmp_path: Path) -> None:
        source = _build_source(tmp_path)
        output = tmp_path / "output"
        app = _build_fake_app(source, output)

        export_picklist_csvs(app)

        assert (output / "picklist" / "fields" / "Account_Status__c.csv").exists()
        assert (output / "picklist" / "fields" / "Contact_Level__c.csv").exists()
