"""Dependency (impact) analysis and orphan detection."""

from __future__ import annotations

from src.core.models import Dependency, MetadataSnapshot, OrphanInfo
from src.core.utils import child_text, parse_xml
from src.parsers.salesforce_parser.base import _ParserState


class _DependenciesMixin(_ParserState):
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

        # 1. Scan Apex for Object, Class and Field dependencies
        for artifact in snapshot.apex_artifacts:
            body_lower = artifact.body.lower()
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

            # Field scanning (limited to common patterns: Obj.Field or [SELECT ... Field ...])
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
            ("omniIntegrationProcedures", "*.ip-meta.xml"),
            ("omniDataTransforms", "*.rpt-meta.xml"),
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

        # 9. Orphan detection
        self.log("Detection des composants orphelins...")
        used_targets = {(d.target_name, d.target_kind) for d in snapshot.dependencies}

        # Apex orphans
        for artifact in snapshot.apex_artifacts:
            if artifact.is_test:
                continue
            if (artifact.name, "Apex") not in used_targets:
                # Check if it's a trigger (triggers are entry points)
                if artifact.kind == "trigger":
                    continue
                snapshot.orphans.append(OrphanInfo(
                    name=artifact.name,
                    kind="Apex Class",
                    source_path=artifact.source_path
                ))

        # Object orphans (standard objects are never orphans)
        for obj in snapshot.objects:
            if not obj.custom:
                continue
            if (obj.api_name, "Object") not in used_targets:
                snapshot.orphans.append(OrphanInfo(
                    name=obj.api_name,
                    kind="Custom Object",
                    source_path=obj.source_path
                ))

        # Field orphans
        for obj in snapshot.objects:
            for field in obj.fields:
                if not field.custom:
                    continue
                field_full_name = f"{obj.api_name}.{field.api_name}"
                if (field_full_name, "Field") not in used_targets:
                    snapshot.orphans.append(OrphanInfo(
                        name=field_full_name,
                        kind="Custom Field",
                        source_path=obj.source_path
                    ))

        # Flow orphans
        for flow in snapshot.flows:
            if (flow.name, "Flow") not in used_targets:
                # Flows can be entry points (Screen flows, scheduled flows)
                if flow.process_type in ("Flow", "AutoLaunchedFlow") and not flow.trigger_type:
                    # Potential orphan if not called by anything
                    snapshot.orphans.append(OrphanInfo(
                        name=flow.name,
                        kind="Flow",
                        source_path=flow.source_path
                    ))
