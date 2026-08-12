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
from src.core.utils import SF_NS, child_text, child_texts, parse_xml, to_bool
from src.parsers.salesforce_parser.base import _ParserState

_PICKLIST_TYPES = ("Picklist", "MultiselectPicklist")


class _ObjectsMixin(_ParserState):
    """Parse the ``objects/`` folder into :class:`ObjectInfo` instances."""

    def _parse_objects(self, package_root: Path) -> dict[str, ObjectInfo]:
        objects_dir = package_root / "objects"
        parsed: dict[str, ObjectInfo] = {}
        if not objects_dir.exists():
            return parsed

        global_value_sets = self._load_global_value_sets(package_root)

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
                    field_info = self._parse_field(field_file, global_value_sets)
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

    def _parse_field(
        self, field_file: Path, global_value_sets: dict[str, list[tuple[str, str]]] | None = None
    ) -> FieldInfo:
        root = parse_xml(field_file)
        api_name = child_text(root, "fullName") or field_file.stem.replace(".field-meta", "")
        field_info = FieldInfo(
            api_name=api_name,
            label=child_text(root, "label"),
            data_type=child_text(root, "type"),
            description=child_text(root, "description"),
            required=to_bool(child_text(root, "required")),
            custom="__" in api_name,
            reference_to=child_texts(root, "referenceTo"),
            relationship_name=child_text(root, "relationshipName"),
        )
        if field_info.data_type in _PICKLIST_TYPES:
            self._parse_picklist_values(root, field_info, global_value_sets or {})
        return field_info

    def _parse_picklist_values(
        self,
        root,
        field_info: FieldInfo,
        global_value_sets: dict[str, list[tuple[str, str]]],
    ) -> None:
        """Populate ``field_info`` picklist attributes from its ``valueSet`` node."""
        value_set = root.find("sf:valueSet", SF_NS)
        if value_set is None:
            return

        global_name = child_text(value_set, "valueSetName")
        if global_name:
            field_info.picklist_is_global = True
            field_info.picklist_global_name = global_name
            pairs = global_value_sets.get(global_name, [])
            field_info.picklist_values = [label for label, _api_name in pairs]
            field_info.picklist_api_names = [api_name for _label, api_name in pairs]
            return

        value_def = value_set.find("sf:valueSetDefinition", SF_NS)
        if value_def is None:
            value_def = value_set

        values: list[str] = []
        api_names: list[str] = []
        for value_node in value_def.findall("sf:value", SF_NS):
            api_name = child_text(value_node, "fullName")
            label = child_text(value_node, "label") or api_name
            if label and label not in values:
                values.append(label)
                api_names.append(api_name or label)
        field_info.picklist_values = values
        field_info.picklist_api_names = api_names

    def _load_global_value_sets(self, package_root: Path) -> dict[str, list[tuple[str, str]]]:
        """Parse ``globalValueSets/*.globalValueSet-meta.xml`` into a name -> [(label, api_name)] map."""
        global_value_sets: dict[str, list[tuple[str, str]]] = {}
        gvs_dir = package_root / "globalValueSets"
        if not gvs_dir.exists():
            return global_value_sets

        for gvs_file in sorted(gvs_dir.glob("*.globalValueSet-meta.xml")):
            gvs_name = gvs_file.stem.replace(".globalValueSet-meta", "")
            if self._is_excluded("global_value_set", gvs_name):
                continue
            try:
                root = parse_xml(gvs_file)
            except Exception:
                continue

            values: list[tuple[str, str]] = []
            seen_labels: set[str] = set()
            for value_node in root.findall("sf:customValue", SF_NS):
                api_name = child_text(value_node, "fullName")
                label = child_text(value_node, "label") or api_name
                if label and label not in seen_labels:
                    seen_labels.add(label)
                    values.append((label, api_name or label))
            global_value_sets[gvs_name] = values

        return global_value_sets

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
