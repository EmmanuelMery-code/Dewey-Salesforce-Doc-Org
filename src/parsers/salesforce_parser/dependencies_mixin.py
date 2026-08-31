"""Dependency (impact) analysis.

Cross-reference scanning lives here; orphan detection (which consumes the
resulting ``used_targets`` set) is a separate sibling mixin — see
:mod:`src.parsers.salesforce_parser.orphan_detection_mixin`. The SOQL-in-Apex
field usage extraction helpers used below live in
:mod:`src.parsers.salesforce_parser.dependency_soql_helpers`.
"""

from __future__ import annotations

from src.core.field_automation_usage import assign_field_automation_usages
from src.core.models import Dependency, MetadataSnapshot, ObjectInfo
from src.core.utils import child_text, parse_xml
from src.parsers.salesforce_parser.base import _ParserState
from src.parsers.salesforce_parser.dependency_soql_helpers import _extract_soql_field_usages
from src.parsers.salesforce_parser.orphan_detection_mixin import _OrphanDetectionMixin


class _DependenciesMixin(_OrphanDetectionMixin, _ParserState):
    """Scan metadata for cross-references and flag orphaned components."""

    def _analyze_dependencies(self, snapshot: MetadataSnapshot) -> None:
        """Perform a basic dependency analysis by scanning metadata for references."""
        self.log("Analyse des dependances (Impact Analysis)...")

        object_names = {obj.api_name for obj in snapshot.objects}
        apex_names = {art.name for art in snapshot.apex_artifacts}
        objects_by_name = {obj.api_name.lower(): obj for obj in snapshot.objects}

        # Pre-calculate field names for scanning
        all_fields = []
        for obj in snapshot.objects:
            for field in obj.fields:
                all_fields.append((obj.api_name, field.api_name))

        # Global map of child-relationship name -> owning (child) object, used
        # to resolve SOQL child subqueries (``(SELECT ... FROM ChildRel__r)``)
        # and parent-relationship traversal in SOQL projections.
        relationship_owners: dict[str, ObjectInfo] = {}
        for obj in snapshot.objects:
            for field in obj.fields:
                if field.relationship_name:
                    relationship_owners[field.relationship_name.lower()] = obj

        # 1. Scan Apex for Object, Class and Field dependencies
        for artifact in snapshot.apex_artifacts:
            body_lower = artifact.body.lower()

            # SOQL-aware field usage: parses the queries embedded in the Apex
            # source (bracket literal syntax and static string literals) so a
            # field referenced only in a SOQL projection (``[SELECT
            # Field__c FROM Object__c]``) is correctly counted as used and
            # not flagged as orphan.
            for obj_name, field_name in _extract_soql_field_usages(
                artifact.body, objects_by_name, relationship_owners
            ):
                snapshot.dependencies.append(Dependency(
                    source_name=artifact.name,
                    source_kind=artifact.kind,
                    target_name=f"{obj_name}.{field_name}",
                    target_kind="Field"
                ))
            for obj_name in object_names:
                if obj_name.lower() in body_lower:
                    snapshot.dependencies.append(Dependency(
                        source_name=artifact.name,
                        source_kind=artifact.kind,
                        target_name=obj_name,
                        target_kind="Object"
                    ))
            for other_apex in apex_names:
                if other_apex != artifact.name and other_apex.lower() in body_lower:
                    snapshot.dependencies.append(Dependency(
                        source_name=artifact.name,
                        source_kind=artifact.kind,
                        target_name=other_apex,
                        target_kind="Apex"
                    ))

            # Field scanning (substring match on the literal "Obj.Field" pattern,
            # e.g. explicit references outside of SOQL; SOQL projections are
            # already covered by the SOQL-aware extraction above).
            for obj_name, field_name in all_fields:
                pattern = f"{obj_name}.{field_name}".lower()
                if pattern in body_lower:
                    snapshot.dependencies.append(Dependency(
                        source_name=artifact.name,
                        source_kind=artifact.kind,
                        target_name=f"{obj_name}.{field_name}",
                        target_kind="Field"
                    ))

        # 1b. Object -> Object relationships (Lookup / Master-Detail)
        for obj in snapshot.objects:
            for rel in obj.relationships:
                for target in rel.targets:
                    target_name = (target or "").strip()
                    if not target_name or target_name == obj.api_name:
                        continue
                    snapshot.dependencies.append(Dependency(
                        source_name=obj.api_name,
                        source_kind="Object",
                        target_name=target_name,
                        target_kind="Object"
                    ))

        # 1c. Validation rule formulas -> Field dependencies (same object as the rule)
        for obj in snapshot.objects:
            custom_fields = [f for f in obj.fields if f.custom]
            if not custom_fields:
                continue
            for vr in obj.validation_rules:
                formula_lower = (vr.error_condition_formula or "").lower()
                if not formula_lower:
                    continue
                for f in custom_fields:
                    if f.api_name.lower() in formula_lower:
                        snapshot.dependencies.append(Dependency(
                            source_name=f"{obj.api_name}.{vr.full_name}",
                            source_kind="ValidationRule",
                            target_name=f"{obj.api_name}.{f.api_name}",
                            target_kind="Field"
                        ))

        # 1d. Formula fields -> Field dependencies. A formula reads fields by
        # bare API name, so the scan is scoped to the formula's own object;
        # cross-object references (``Parent__r.Field__c``) resolve to the
        # parent's field only when that name also exists on this object, which
        # is the same trade-off the validation rule scan above makes.
        for obj in snapshot.objects:
            custom_fields = [f for f in obj.fields if f.custom]
            if not custom_fields:
                continue
            for formula_field in obj.fields:
                formula_lower = (formula_field.formula or "").lower()
                if not formula_lower:
                    continue
                for f in custom_fields:
                    if f.api_name == formula_field.api_name:
                        continue
                    if f.api_name.lower() in formula_lower:
                        snapshot.dependencies.append(Dependency(
                            source_name=f"{obj.api_name}.{formula_field.api_name}",
                            source_kind="Formula",
                            target_name=f"{obj.api_name}.{f.api_name}",
                            target_kind="Field"
                        ))

        # 2. Scan Flows for Object dependencies, and (when bound to a known
        # object via start_object) for that object's custom Field dependencies
        for flow in snapshot.flows:
            if flow.start_object:
                snapshot.dependencies.append(Dependency(
                    source_name=flow.name,
                    source_kind="Flow",
                    target_name=flow.start_object,
                    target_kind="Object"
                ))

            # A Flow called as a "Subflow" element by another Flow is a
            # dependency target, not an orphan, even when it has no
            # trigger/screen of its own (see orphan detection in section 9).
            for called_flow_name in flow.called_flow_names:
                snapshot.dependencies.append(Dependency(
                    source_name=flow.name,
                    source_kind="Flow",
                    target_name=called_flow_name,
                    target_kind="Flow"
                ))

            # Scan elements for object references
            for element in flow.elements:
                if element.element_type in ("recordLookups", "recordCreates", "recordUpdates", "recordDeletes"):
                    # We don't store the object name in FlowElementInfo yet, but we could parse it
                    pass

                if element.element_type == "actionCalls":
                    # Check for Apex actions
                    # The Apex class name is often in the 'actionName' attribute or child node
                    pass

            # Simple text scan of Flow XML for Apex class names, and (when the
            # flow is bound to a known object) for that object's custom field
            # API names: recordFilters, field assignments, merge fields such
            # as {!Record.Field__c}, screen component default values, ...
            try:
                flow_xml = flow.source_path.read_text(encoding="utf-8", errors="ignore")
                for apex_name in apex_names:
                    if f">{apex_name}<" in flow_xml or f"/{apex_name}<" in flow_xml:
                        snapshot.dependencies.append(Dependency(
                            source_name=flow.name,
                            source_kind="Flow",
                            target_name=apex_name,
                            target_kind="Apex"
                        ))
                bound_object = objects_by_name.get((flow.start_object or "").lower())
                if bound_object is not None:
                    flow_xml_lower = flow_xml.lower()
                    for f in bound_object.fields:
                        if not f.custom:
                            continue
                        needle = f.api_name.lower()
                        if f">{needle}<" in flow_xml_lower or f".{needle}" in flow_xml_lower:
                            snapshot.dependencies.append(Dependency(
                                source_name=flow.name,
                                source_kind="Flow",
                                target_name=f"{bound_object.api_name}.{f.api_name}",
                                target_kind="Field"
                            ))
            except Exception:
                pass

        # 3. Scan LWC for Apex dependencies, and (via @salesforce/schema field
        # imports) for Field dependencies
        for lwc in snapshot.lwc:
            js_file = lwc.source_path / f"{lwc.name}.js"
            if js_file.exists():
                try:
                    content = js_file.read_text(encoding="utf-8")
                    content_lower = content.lower()
                    for apex_name in apex_names:
                        if f"@{apex_name}" in content or f"'{apex_name}'" in content or f'"{apex_name}"' in content:
                            snapshot.dependencies.append(Dependency(
                                source_name=lwc.name,
                                source_kind="LWC",
                                target_name=apex_name,
                                target_kind="Apex"
                            ))
                    # import FIELD from '@salesforce/schema/Object__c.Field__c';
                    if "@salesforce/schema" in content_lower:
                        for obj_name, field_name in all_fields:
                            if f"{obj_name}.{field_name}".lower() in content_lower:
                                snapshot.dependencies.append(Dependency(
                                    source_name=lwc.name,
                                    source_kind="LWC",
                                    target_name=f"{obj_name}.{field_name}",
                                    target_kind="Field"
                                ))
                except OSError:
                    pass

        # 4. Scan Aura for Apex dependencies, and (JS controllers/helpers plus
        # the component markup) for Field dependencies
        for aura in snapshot.aura:
            aura_texts: list[str] = []
            for js_suffix in ("Controller.js", "Helper.js"):
                js_file = aura.source_path / f"{aura.name}{js_suffix}"
                if js_file.exists():
                    try:
                        content = js_file.read_text(encoding="utf-8")
                        aura_texts.append(content)
                        for apex_name in apex_names:
                            if f"c.{apex_name}" in content or f"'{apex_name}'" in content or f'"{apex_name}"' in content:
                                snapshot.dependencies.append(Dependency(
                                    source_name=aura.name,
                                    source_kind="Aura",
                                    target_name=apex_name,
                                    target_kind="Apex"
                                ))
                    except OSError:
                        pass
            cmp_file = aura.source_path / f"{aura.name}.cmp"
            if cmp_file.exists():
                try:
                    aura_texts.append(cmp_file.read_text(encoding="utf-8"))
                except OSError:
                    pass
            if aura_texts:
                combined_lower = "\n".join(aura_texts).lower()
                # Only walk the (potentially large) field list when the markup/JS
                # actually contains a custom-field-looking token, to keep this cheap.
                if "__c" in combined_lower:
                    for obj_name, field_name in all_fields:
                        field_lower = field_name.lower()
                        if (
                            f"{obj_name}.{field_name}".lower() in combined_lower
                            or f".fields.{field_lower}" in combined_lower
                        ):
                            snapshot.dependencies.append(Dependency(
                                source_name=aura.name,
                                source_kind="Aura",
                                target_name=f"{obj_name}.{field_name}",
                                target_kind="Field"
                            ))

        # 5. Scan Reports for Object dependencies, and (for the report's
        # resolved object) for Field dependencies (column/filter references)
        for row in snapshot.inventory.get("reports", []):
            source = str(row.get("Source") or "")
            if not source:
                continue
            candidate = self.source_dir / source
            if not candidate.exists():
                continue
            try:
                content = candidate.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            matched_object = None
            for obj_name in object_names:
                if f"<reportType>{obj_name}</reportType>" in content or f"<reportType>{obj_name}_" in content:
                    snapshot.dependencies.append(Dependency(
                        source_name=str(row.get("Nom")),
                        source_kind="Report",
                        target_name=obj_name,
                        target_kind="Object"
                    ))
                    matched_object = objects_by_name.get(obj_name.lower())

            if matched_object is not None:
                content_lower = content.lower()
                for f in matched_object.fields:
                    if not f.custom:
                        continue
                    if f">{f.api_name.lower()}<" in content_lower:
                        snapshot.dependencies.append(Dependency(
                            source_name=str(row.get("Nom")),
                            source_kind="Report",
                            target_name=f"{matched_object.api_name}.{f.api_name}",
                            target_kind="Field"
                        ))

        # 6. Scan Layouts for Field dependencies. Layout filenames follow the
        # "ObjectApiName-Layout Label.layout-meta.xml" convention, which gives
        # us a reliable, low-noise way to scope the scan to that object's
        # own custom fields (layoutItems store the bare field API name).
        for package_root in snapshot.package_roots:
            layouts_dir = package_root / "layouts"
            if not layouts_dir.exists():
                continue
            for layout_file in layouts_dir.glob("*.layout-meta.xml"):
                object_prefix = layout_file.stem.split("-", 1)[0].strip().lower()
                bound_object = objects_by_name.get(object_prefix)
                if bound_object is None:
                    continue
                custom_fields = [f for f in bound_object.fields if f.custom]
                if not custom_fields:
                    continue
                try:
                    content_lower = layout_file.read_text(encoding="utf-8", errors="ignore").lower()
                except OSError:
                    continue
                for f in custom_fields:
                    if f">{f.api_name.lower()}<" in content_lower:
                        snapshot.dependencies.append(Dependency(
                            source_name=layout_file.stem,
                            source_kind="Layout",
                            target_name=f"{bound_object.api_name}.{f.api_name}",
                            target_kind="Field"
                        ))

        # 7. Scan FlexiPages (Lightning record/app/home pages) for Field
        # dependencies. Record Pages declare their bound object via the
        # <sobjectType> root element; pages without it (App/Home pages) are
        # skipped rather than scanned unscoped to avoid cross-object noise.
        for package_root in snapshot.package_roots:
            flexipages_dir = package_root / "flexipages"
            if not flexipages_dir.exists():
                continue
            for flexipage_file in flexipages_dir.glob("*.flexipage-meta.xml"):
                try:
                    content = flexipage_file.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                sobject_type = ""
                try:
                    sobject_type = child_text(parse_xml(flexipage_file), "sobjectType")
                except Exception:
                    sobject_type = ""
                bound_object = objects_by_name.get(sobject_type.lower()) if sobject_type else None
                if bound_object is None:
                    continue
                custom_fields = [f for f in bound_object.fields if f.custom]
                if not custom_fields:
                    continue
                content_lower = content.lower()
                for f in custom_fields:
                    needle = f.api_name.lower()
                    if f">{needle}<" in content_lower or f".{needle}<" in content_lower:
                        snapshot.dependencies.append(Dependency(
                            source_name=flexipage_file.stem,
                            source_kind="FlexiPage",
                            target_name=f"{bound_object.api_name}.{f.api_name}",
                            target_kind="Field"
                        ))

        # 8. Scan OmniStudio components (OmniScripts, Integration Procedures,
        # DataMappers/DataTransforms, FlexCards/OmniUiCards) for Object, Field
        # and Apex dependencies. These are stored as XML wrapping a JSON
        # payload (element/action configuration), so rather than modelling
        # every possible JSON shape we do the same lightweight text scan
        # already used for Apex/Flow/LWC/Aura above: bare object/class name
        # for Object/Apex references, and the qualified "Object.Field"
        # pattern (used by DataMapper field mappings, Integration Procedure
        # response actions, FlexCard field bindings, ...) for Field references.
        omni_glob_patterns = (
            ("omniScripts", "*.os-meta.xml"),
            ("omniIntegrationProcedures", "*.oip-meta.xml"),
            ("omniIntegrationProcedures", "*.ip-meta.xml"),
            ("omniDataTransforms", "*.rpt-meta.xml"),
            ("omniUiCard", "*.ouc-meta.xml"),
            ("omniUiCard", "*.card-meta.xml"),
            ("omniUiCards", "*.ouc-meta.xml"),
            ("omniUiCards", "*.card-meta.xml"),
            ("vlocityCards", "*.ouc-meta.xml"),
            ("omniProcesses", "*.omniProcess-meta.xml"),
        )
        for package_root in snapshot.package_roots:
            for folder_name, glob_pattern in omni_glob_patterns:
                omni_dir = package_root / folder_name
                if not omni_dir.exists():
                    continue
                for omni_file in omni_dir.glob(glob_pattern):
                    try:
                        content_lower = omni_file.read_text(encoding="utf-8", errors="ignore").lower()
                    except OSError:
                        continue
                    omni_name = omni_file.stem.split(".", 1)[0]

                    for obj_name in object_names:
                        if obj_name.lower() in content_lower:
                            snapshot.dependencies.append(Dependency(
                                source_name=omni_name,
                                source_kind="Omni",
                                target_name=obj_name,
                                target_kind="Object"
                            ))
                    for apex_name in apex_names:
                        if apex_name.lower() in content_lower:
                            snapshot.dependencies.append(Dependency(
                                source_name=omni_name,
                                source_kind="Omni",
                                target_name=apex_name,
                                target_kind="Apex"
                            ))
                    if "__c" in content_lower:
                        for obj_name, field_name in all_fields:
                            if f"{obj_name}.{field_name}".lower() in content_lower:
                                snapshot.dependencies.append(Dependency(
                                    source_name=omni_name,
                                    source_kind="Omni",
                                    target_name=f"{obj_name}.{field_name}",
                                    target_kind="Field"
                                ))

        # 9. Orphan detection (Apex/Object/Field/Flow) — see _OrphanDetectionMixin
        used_targets = {(d.target_name, d.target_kind) for d in snapshot.dependencies}
        self._detect_orphans(snapshot, used_targets)

        # 10. Roll the Field dependencies up onto the fields themselves, so the
        # Data Dictionary can warn that changing a field may break an automation.
        assign_field_automation_usages(snapshot)
