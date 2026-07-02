"""Dependency (impact) analysis and orphan detection."""

from __future__ import annotations

from src.core.models import Dependency, MetadataSnapshot, OrphanInfo
from src.parsers.salesforce_parser.base import _ParserState


class _DependenciesMixin(_ParserState):
    """Scan metadata for cross-references and flag orphaned components."""

    def _analyze_dependencies(self, snapshot: MetadataSnapshot) -> None:
        """Perform a basic dependency analysis by scanning metadata for references."""
        self.log("Analyse des dependances (Impact Analysis)...")

        object_names = {obj.api_name for obj in snapshot.objects}
        apex_names = {art.name for art in snapshot.apex_artifacts}

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

        # 2. Scan Flows for Object dependencies
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

            # Simple text scan of Flow XML for Apex class names
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
            except Exception:
                pass

        # 3. Scan LWC for Apex dependencies
        for lwc in snapshot.lwc:
            js_file = lwc.source_path / f"{lwc.name}.js"
            if js_file.exists():
                try:
                    content = js_file.read_text(encoding="utf-8")
                    for apex_name in apex_names:
                        if f"@{apex_name}" in content or f"'{apex_name}'" in content or f'"{apex_name}"' in content:
                            snapshot.dependencies.append(Dependency(
                                source_name=lwc.name,
                                source_kind="LWC",
                                target_name=apex_name,
                                target_kind="Apex"
                            ))
                except OSError:
                    pass

        # 4. Scan Aura for Apex dependencies
        for aura in snapshot.aura:
            for js_suffix in ("Controller.js", "Helper.js"):
                js_file = aura.source_path / f"{aura.name}{js_suffix}"
                if js_file.exists():
                    try:
                        content = js_file.read_text(encoding="utf-8")
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

        # 5. Scan Reports for Object dependencies
        for row in snapshot.inventory.get("reports", []):
            source = str(row.get("Source") or "")
            if not source:
                continue
            candidate = self.source_dir / source
            if not candidate.exists():
                continue
            try:
                content = candidate.read_text(encoding="utf-8", errors="ignore")
                for obj_name in object_names:
                    if f"<reportType>{obj_name}</reportType>" in content or f"<reportType>{obj_name}_" in content:
                        snapshot.dependencies.append(Dependency(
                            source_name=str(row.get("Nom")),
                            source_kind="Report",
                            target_name=obj_name,
                            target_kind="Object"
                        ))
            except OSError:
                continue

        # 4. Orphan detection
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
