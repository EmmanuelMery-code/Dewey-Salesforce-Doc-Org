"""The Data Dictionary Custom column names the four object kinds.

Column D of the Synthese sheet (header "Custom") and the matching row of
the Word data dictionary share one label: standard, custom object, custom
metadata or custom settings. A custom setting is a ``__c`` object whose
metadata carries ``customSettingsType`` List or Hierarchy; the suffix alone
does not decide.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.reporting.excel_writer import ExcelReportWriter
from src.reporting.word_writer import WordReportWriter

_OBJECT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <label>{label}</label>
    {extra}
</CustomObject>
"""

_FIELD_XML = """<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>{api_name}</fullName>
    <label>{api_name}</label>
    <type>Text</type>
</CustomField>
"""


def _write_object(
    source: Path,
    api_name: str,
    *,
    custom_settings_type: str = "",
    field_name: str = "Name",
) -> None:
    folder = source / "objects" / api_name
    fields = folder / "fields"
    fields.mkdir(parents=True)
    extra = (
        f"<customSettingsType>{custom_settings_type}</customSettingsType>"
        if custom_settings_type
        else ""
    )
    (folder / f"{api_name}.object-meta.xml").write_text(
        _OBJECT_XML.format(label=api_name, extra=extra),
        encoding="utf-8",
    )
    (fields / f"{field_name}.field-meta.xml").write_text(
        _FIELD_XML.format(api_name=field_name),
        encoding="utf-8",
    )


def _rows(sheet) -> dict[str, dict]:
    headers = [cell.value for cell in sheet[1]]
    return {
        row[0]: dict(zip(headers, row))
        for row in sheet.iter_rows(min_row=2, values_only=True)
        if row[0]
    }


def test_column_d_labels_the_four_kinds_from_parsed_metadata(tmp_path: Path) -> None:
    _write_object(tmp_path, "Account")
    _write_object(tmp_path, "pkg__Contrat__c", field_name="Nom__c")
    _write_object(tmp_path, "pkg__Config__mdt", field_name="Cle__c")
    _write_object(tmp_path, "pkg__Reglages__c", custom_settings_type="List", field_name="Valeur__c")
    _write_object(tmp_path, "pkg__Niveaux__c", custom_settings_type="Hierarchy", field_name="Valeur__c")

    snapshot = SalesforceMetadataParser(tmp_path).parse()
    by_name = {obj.api_name: obj for obj in snapshot.objects}

    assert by_name["Account"].custom_settings_type == ""
    assert by_name["pkg__Contrat__c"].custom_settings_type == ""
    assert by_name["pkg__Config__mdt"].custom_settings_type == ""
    assert by_name["pkg__Reglages__c"].custom_settings_type == "List"
    assert by_name["pkg__Niveaux__c"].custom_settings_type == "Hierarchy"

    paths = ExcelReportWriter().write_data_dictionary_workbooks(
        snapshot.objects, tmp_path / "excel"
    )
    summary = load_workbook(paths[0])["Synthese"]
    headers = [cell.value for cell in summary[1]]
    assert headers[3] == "Custom"
    assert summary["D1"].value == "Custom"

    kinds = {api_name: row["Custom"] for api_name, row in _rows(summary).items()}
    assert kinds == {
        "Account": "standard",
        "pkg__Contrat__c": "custom object",
        "pkg__Config__mdt": "custom metadata",
        "pkg__Reglages__c": "custom settings",
        "pkg__Niveaux__c": "custom settings",
    }

    # The field-level Custom column stays a yes/no. Only the object column
    # (Synthese, column D) carries the four labels.
    contrat = load_workbook(paths[0])["pkg__Contrat__c"]
    field_headers = [cell.value for cell in contrat[1]]
    assert field_headers[4] == "Custom"
    assert contrat["E2"].value == "Oui"

    output = WordReportWriter().write_data_dictionary_document(
        snapshot, tmp_path / "word" / "data_dictionary.docx"
    )
    from docx import Document

    document = Document(output)
    word_kinds = {}
    for table in document.tables:
        pairs = {
            row.cells[0].text: row.cells[1].text
            for row in table.rows
            if len(row.cells) >= 2
        }
        if "API Name" in pairs and "Objet personnalise" in pairs:
            word_kinds[pairs["API Name"]] = pairs["Objet personnalise"]
    assert word_kinds == kinds
