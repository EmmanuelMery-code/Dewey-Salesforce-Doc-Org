"""Parsing of custom/standard objects and their fields, record types and rules."""

from __future__ import annotations

from pathlib import Path

from src.core.models import (
    FieldInfo,
    ObjectInfo,
    RecordTypeInfo,
    RelationshipInfo,
    ValidationRuleInfo,
)
from src.core.utils import child_text, child_texts, parse_xml, to_bool
from src.parsers.salesforce_parser.base import _ParserState


class _ObjectsMixin(_ParserState):
    """Parse the ``objects/`` folder into :class:`ObjectInfo` instances."""

    def _parse_objects(self, package_root: Path) -> dict[str, ObjectInfo]:
        objects_dir = package_root / "objects"
        parsed: dict[str, ObjectInfo] = {}
        if not objects_dir.exists():
            return parsed

        for object_dir in sorted(path for path in objects_dir.iterdir() if path.is_dir()):
            api_name = object_dir.name
            object_file = object_dir / f"{api_name}.object-meta.xml"
            info = ObjectInfo(api_name=api_name, custom="__" in api_name, source_path=object_file if object_file.exists() else object_dir)

            if object_file.exists():
                root = parse_xml(object_file)
                info.label = child_text(root, "label")
                info.plural_label = child_text(root, "pluralLabel")
                info.description = child_text(root, "description")
                info.deployment_status = child_text(root, "deploymentStatus")
                info.sharing_model = child_text(root, "sharingModel") or child_text(root, "externalSharingModel")
                info.visibility = child_text(root, "visibility")
                # Sometimes apiVersion is in the object file (though rare)
                info.api_version = child_text(root, "apiVersion")

            fields_dir = object_dir / "fields"
            if fields_dir.exists():
                for field_file in sorted(fields_dir.glob("*.field-meta.xml")):
                    field_info = self._parse_field(field_file)
                    if not self._is_excluded("field", f"{api_name}.{field_info.api_name}", field_info.api_name):
                        info.fields.append(field_info)

            record_types_dir = object_dir / "recordTypes"
            if record_types_dir.exists():
                for record_type_file in sorted(record_types_dir.glob("*.recordType-meta.xml")):
                    rt_info = self._parse_record_type(record_type_file)
                    if not self._is_excluded("record_type", f"{api_name}.{rt_info.full_name}", rt_info.full_name):
                        info.record_types.append(rt_info)

            validation_rules_dir = object_dir / "validationRules"
            if validation_rules_dir.exists():
                for validation_rule_file in sorted(validation_rules_dir.glob("*.validationRule-meta.xml")):
                    vr = self._parse_validation_rule(validation_rule_file)
                    if not self._is_excluded("validation_rule", f"{api_name}.{vr.full_name}", vr.full_name):
                        info.validation_rules.append(vr)

            info.relationships = [
                RelationshipInfo(
                    field_name=field.api_name,
                    relationship_type=field.data_type,
                    targets=field.reference_to,
                )
                for field in info.fields
                if field.reference_to
            ]
            parsed[api_name] = info

        return parsed

    def _parse_field(self, field_file: Path) -> FieldInfo:
        root = parse_xml(field_file)
        api_name = child_text(root, "fullName") or field_file.stem.replace(".field-meta", "")
        return FieldInfo(
            api_name=api_name,
            label=child_text(root, "label"),
            data_type=child_text(root, "type"),
            description=child_text(root, "description"),
            required=to_bool(child_text(root, "required")),
            custom="__" in api_name,
            reference_to=child_texts(root, "referenceTo"),
            relationship_name=child_text(root, "relationshipName"),
        )

    def _parse_record_type(self, record_type_file: Path) -> RecordTypeInfo:
        root = parse_xml(record_type_file)
        return RecordTypeInfo(
            full_name=child_text(root, "fullName") or record_type_file.stem.replace(".recordType-meta", ""),
            label=child_text(root, "label"),
            description=child_text(root, "description"),
            active=to_bool(child_text(root, "active")),
        )

    def _parse_validation_rule(self, validation_rule_file: Path) -> ValidationRuleInfo:
        root = parse_xml(validation_rule_file)
        return ValidationRuleInfo(
            full_name=child_text(root, "fullName")
            or validation_rule_file.stem.replace(".validationRule-meta", ""),
            active=to_bool(child_text(root, "active")),
            description=child_text(root, "description"),
            error_display_field=child_text(root, "errorDisplayField"),
            error_message=child_text(root, "errorMessage"),
            error_condition_formula=child_text(root, "errorConditionFormula"),
            api_version=child_text(root, "apiVersion"),
        )
