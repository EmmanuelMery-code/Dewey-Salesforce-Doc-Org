"""Orphan component detection, run after dependency scanning.

Flags Apex classes, custom objects, custom fields and Flows that are never
referenced by anything else in the org, based on the ``used_targets`` set
built by :class:`~src.parsers.salesforce_parser.dependencies_mixin._DependenciesMixin`.
"""

from __future__ import annotations

from src.core.models import MetadataSnapshot, OrphanInfo
from src.parsers.salesforce_parser.base import _ParserState


class _OrphanDetectionMixin(_ParserState):
    """Detect Apex/Object/Field/Flow components with no incoming dependency."""

    def _detect_orphans(
        self, snapshot: MetadataSnapshot, used_targets: set[tuple[str, str]]
    ) -> None:
        self.log("Detection des composants orphelins...")

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
