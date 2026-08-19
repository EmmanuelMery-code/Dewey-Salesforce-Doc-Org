"""Tests: a custom field referenced only inside a SOQL query (in an Apex
class or trigger) must not be flagged as an orphan field.

Contract tested:
  src.parsers.salesforce_parser.dependencies_mixin
    _extract_soql_field_usages(body, objects_by_name, relationship_owners)
      -> list[(ObjectApiName, FieldApiName)] referenced by any SOQL query
      (bracket literal syntax or static string literal) found in ``body``.

  SalesforceMetadataParser(...).parse() -> MetadataSnapshot
    snapshot.orphans does not contain a Custom Field that is only ever
    referenced inside a SOQL projection (direct field, parent-relationship
    traversal, or child-relationship subquery), but still contains a
    genuinely unreferenced field.
"""

from __future__ import annotations

from pathlib import Path

from src.core.models import FieldInfo, ObjectInfo
from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.parsers.salesforce_parser.dependencies_mixin import _extract_soql_field_usages


OBJECT_META = """<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <label>{label}</label>
</CustomObject>
"""

TEXT_FIELD_META = """<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>{api_name}</fullName>
    <label>{label}</label>
    <type>Text</type>
</CustomField>
"""

LOOKUP_FIELD_META = """<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>{api_name}</fullName>
    <label>{label}</label>
    <type>Lookup</type>
    <referenceTo>{reference_to}</referenceTo>
    <relationshipName>{relationship_name}</relationshipName>
</CustomField>
"""


def _write_object(source: Path, api_name: str, fields: list[str]) -> None:
    fields_dir = source / "objects" / api_name / "fields"
    fields_dir.mkdir(parents=True, exist_ok=True)
    (source / "objects" / api_name / f"{api_name}.object-meta.xml").write_text(
        OBJECT_META.format(label=api_name), encoding="utf-8"
    )
    for field_xml, field_api_name in fields:
        (fields_dir / f"{field_api_name}.field-meta.xml").write_text(field_xml, encoding="utf-8")


def _text_field(api_name: str) -> tuple[str, str]:
    return TEXT_FIELD_META.format(api_name=api_name, label=api_name), api_name


def _lookup_field(api_name: str, reference_to: str, relationship_name: str) -> tuple[str, str]:
    return (
        LOOKUP_FIELD_META.format(
            api_name=api_name, label=api_name, reference_to=reference_to, relationship_name=relationship_name
        ),
        api_name,
    )


def _write_class(source: Path, class_name: str, body: str) -> None:
    classes_dir = source / "classes"
    classes_dir.mkdir(parents=True, exist_ok=True)
    (classes_dir / f"{class_name}.cls").write_text(body, encoding="utf-8")


def _build_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"

    _write_object(
        source,
        "Compte__c",
        [
            _text_field("Statut__c"),
            _text_field("Nom_Client__c"),
            _text_field("Solde__c"),
            _text_field("Description_Interne__c"),
        ],
    )
    _write_object(
        source,
        "Contact__c",
        [
            _lookup_field("Compte__c", "Compte__c", "Contacts__r"),
            _text_field("Email__c"),
        ],
    )

    _write_class(
        source,
        "CompteService",
        """public class CompteService {
    public static void run() {
        List<Compte__c> comptes = [SELECT Id, Statut__c FROM Compte__c WHERE Statut__c = 'Actif'];
        List<Contact__c> contacts = [SELECT Id, Compte__r.Nom_Client__c FROM Contact__c];
        List<Compte__c> comptesWithContacts = [SELECT Id, (SELECT Email__c FROM Contacts__r) FROM Compte__c];
    }
}
""",
    )
    _write_class(
        source,
        "DynamicQueryService",
        """public class DynamicQueryService {
    public static void run() {
        String q = 'SELECT Id, Solde__c FROM Compte__c';
        List<Compte__c> results = Database.query(q);
    }
}
""",
    )

    return source


class TestSoqlFieldUsageExtraction:
    """Unit tests for the module-level SOQL parsing helper (no disk I/O)."""

    def _objects_by_name(self) -> dict[str, ObjectInfo]:
        compte = ObjectInfo(
            api_name="Compte__c",
            custom=True,
            fields=[
                FieldInfo(api_name="Statut__c", custom=True),
                FieldInfo(api_name="Nom_Client__c", custom=True),
            ],
        )
        contact = ObjectInfo(
            api_name="Contact__c",
            custom=True,
            fields=[
                FieldInfo(
                    api_name="Compte__c",
                    custom=True,
                    reference_to=["Compte__c"],
                    relationship_name="Contacts__r",
                ),
                FieldInfo(api_name="Email__c", custom=True),
            ],
        )
        return {"compte__c": compte, "contact__c": contact}

    def _relationship_owners(self, objects_by_name: dict[str, ObjectInfo]) -> dict[str, ObjectInfo]:
        owners: dict[str, ObjectInfo] = {}
        for obj in objects_by_name.values():
            for field in obj.fields:
                if field.relationship_name:
                    owners[field.relationship_name.lower()] = obj
        return owners

    def test_direct_field_without_object_prefix_is_detected(self) -> None:
        objects_by_name = self._objects_by_name()
        relationship_owners = self._relationship_owners(objects_by_name)
        body = "List<Compte__c> c = [SELECT Id, Statut__c FROM Compte__c WHERE Statut__c = 'Actif'];"

        usages = _extract_soql_field_usages(body, objects_by_name, relationship_owners)

        assert ("Compte__c", "Statut__c") in usages

    def test_parent_relationship_traversal_field_is_detected(self) -> None:
        objects_by_name = self._objects_by_name()
        relationship_owners = self._relationship_owners(objects_by_name)
        body = "List<Contact__c> c = [SELECT Id, Compte__r.Nom_Client__c FROM Contact__c];"

        usages = _extract_soql_field_usages(body, objects_by_name, relationship_owners)

        assert ("Compte__c", "Nom_Client__c") in usages

    def test_child_relationship_subquery_field_is_detected(self) -> None:
        objects_by_name = self._objects_by_name()
        relationship_owners = self._relationship_owners(objects_by_name)
        body = "List<Compte__c> c = [SELECT Id, (SELECT Email__c FROM Contacts__r) FROM Compte__c];"

        usages = _extract_soql_field_usages(body, objects_by_name, relationship_owners)

        assert ("Contact__c", "Email__c") in usages

    def test_static_string_literal_query_is_detected(self) -> None:
        objects_by_name = self._objects_by_name()
        relationship_owners = self._relationship_owners(objects_by_name)
        body = "String q = 'SELECT Id, Statut__c FROM Compte__c'; List<Compte__c> r = Database.query(q);"

        usages = _extract_soql_field_usages(body, objects_by_name, relationship_owners)

        assert ("Compte__c", "Statut__c") in usages

    def test_unrelated_code_does_not_produce_usages(self) -> None:
        objects_by_name = self._objects_by_name()
        relationship_owners = self._relationship_owners(objects_by_name)
        body = "public class Foo { public void bar() { Integer x = 1 + 2; } }"

        usages = _extract_soql_field_usages(body, objects_by_name, relationship_owners)

        assert usages == []


class TestSoqlFieldIsNotAnOrphan:
    """Integration test through the full parser pipeline."""

    def test_field_used_only_in_soql_is_excluded_from_orphans(self, tmp_path: Path) -> None:
        source = _build_source(tmp_path)
        parser = SalesforceMetadataParser(source)
        snapshot = parser.parse()

        orphan_field_names = {o.name for o in snapshot.orphans if o.kind == "Custom Field"}

        assert "Compte__c.Statut__c" not in orphan_field_names
        assert "Compte__c.Nom_Client__c" not in orphan_field_names
        assert "Contact__c.Email__c" not in orphan_field_names
        assert "Compte__c.Solde__c" not in orphan_field_names, (
            "A field referenced only inside a static SOQL string literal "
            "(e.g. passed to Database.query) must not be an orphan"
        )

    def test_genuinely_unreferenced_field_is_still_an_orphan(self, tmp_path: Path) -> None:
        source = _build_source(tmp_path)
        parser = SalesforceMetadataParser(source)
        snapshot = parser.parse()

        orphan_field_names = {o.name for o in snapshot.orphans if o.kind == "Custom Field"}

        assert "Compte__c.Description_Interne__c" in orphan_field_names

    def test_soql_field_dependency_is_recorded(self, tmp_path: Path) -> None:
        source = _build_source(tmp_path)
        parser = SalesforceMetadataParser(source)
        snapshot = parser.parse()

        matches = [
            dep
            for dep in snapshot.dependencies
            if dep.source_name == "CompteService"
            and dep.target_name == "Compte__c.Statut__c"
            and dep.target_kind == "Field"
        ]
        assert len(matches) == 1
