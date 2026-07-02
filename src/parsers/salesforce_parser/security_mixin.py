"""Parsing of profiles, permission sets and permission set groups."""

from __future__ import annotations

from pathlib import Path

from src.core.models import (
    FieldPermission,
    NamedAccess,
    ObjectPermission,
    PermissionSetGroupInfo,
    RecordTypeVisibility,
    SecurityArtifact,
    UserPermission,
    VisibilityItem,
)
from src.core.utils import SF_NS, child_text, parse_xml, to_bool
from src.parsers.salesforce_parser.base import _ParserState


class _SecurityMixin(_ParserState):
    """Parse profile / permission-set metadata into :class:`SecurityArtifact`."""

    def _parse_security_folder(self, folder: Path, kind: str) -> list[SecurityArtifact]:
        artifacts: list[SecurityArtifact] = []
        if not folder.exists():
            return artifacts

        for meta_file in sorted(folder.glob("*.xml")):
            root = parse_xml(meta_file)
            artifact = SecurityArtifact(
                name=meta_file.name.split(".")[0],
                label=child_text(root, "label") or child_text(root, "fullName"),
                kind=kind,
                is_custom=to_bool(child_text(root, "custom") or "false"),
                description=child_text(root, "description"),
                source_path=meta_file,
            )

            for node in root.findall("sf:objectPermissions", SF_NS):
                artifact.object_permissions.append(
                    ObjectPermission(
                        object_name=child_text(node, "object"),
                        allow_read=to_bool(child_text(node, "allowRead")),
                        allow_create=to_bool(child_text(node, "allowCreate")),
                        allow_edit=to_bool(child_text(node, "allowEdit")),
                        allow_delete=to_bool(child_text(node, "allowDelete")),
                        view_all_records=to_bool(child_text(node, "viewAllRecords")),
                        modify_all_records=to_bool(child_text(node, "modifyAllRecords")),
                    )
                )

            for node in root.findall("sf:fieldPermissions", SF_NS):
                artifact.field_permissions.append(
                    FieldPermission(
                        field_name=child_text(node, "field"),
                        readable=to_bool(child_text(node, "readable")),
                        editable=to_bool(child_text(node, "editable")),
                    )
                )

            for node in root.findall("sf:userPermissions", SF_NS):
                artifact.user_permissions.append(
                    UserPermission(
                        name=child_text(node, "name"),
                        enabled=to_bool(child_text(node, "enabled")),
                    )
                )

            for node in root.findall("sf:applicationVisibilities", SF_NS):
                artifact.application_visibilities.append(
                    VisibilityItem(
                        name=child_text(node, "application"),
                        visible=child_text(node, "visible"),
                        default=child_text(node, "default"),
                    )
                )

            for node in root.findall("sf:tabVisibilities", SF_NS) + root.findall("sf:tabSettings", SF_NS):
                artifact.tab_visibilities.append(
                    VisibilityItem(
                        name=child_text(node, "tab"),
                        visible=child_text(node, "visibility"),
                        default=child_text(node, "default"),
                    )
                )

            for node in root.findall("sf:classAccesses", SF_NS):
                artifact.class_accesses.append(
                    NamedAccess(
                        name=child_text(node, "apexClass"),
                        enabled=to_bool(child_text(node, "enabled")),
                    )
                )

            for node in root.findall("sf:flowAccesses", SF_NS):
                artifact.flow_accesses.append(
                    NamedAccess(
                        name=child_text(node, "flow"),
                        enabled=to_bool(child_text(node, "enabled")),
                    )
                )

            for node in root.findall("sf:pageAccesses", SF_NS):
                artifact.page_accesses.append(
                    NamedAccess(
                        name=child_text(node, "apexPage"),
                        enabled=to_bool(child_text(node, "enabled")),
                    )
                )

            for node in root.findall("sf:customPermissions", SF_NS):
                artifact.custom_permissions.append(
                    NamedAccess(
                        name=child_text(node, "name"),
                        enabled=to_bool(child_text(node, "enabled")),
                    )
                )

            for node in root.findall("sf:recordTypeVisibilities", SF_NS):
                artifact.record_type_visibilities.append(
                    RecordTypeVisibility(
                        record_type=child_text(node, "recordType"),
                        visible=to_bool(child_text(node, "visible")),
                        default=to_bool(child_text(node, "default")),
                    )
                )

            artifacts.append(artifact)

        return artifacts

    def _parse_permission_set_groups(self, folder: Path) -> list[PermissionSetGroupInfo]:
        groups: list[PermissionSetGroupInfo] = []
        if not folder.exists():
            return groups

        for meta_file in sorted(folder.glob("*.permissionsetgroup-meta.xml")):
            root = parse_xml(meta_file)
            if root is None:
                continue

            ps_list = []
            for node in root.findall("sf:permissionSets", SF_NS):
                ps_list.append(node.text)

            groups.append(PermissionSetGroupInfo(
                name=meta_file.name.split(".")[0],
                label=child_text(root, "label") or meta_file.name.split(".")[0],
                description=child_text(root, "description"),
                status=child_text(root, "status"),
                permission_sets=ps_list,
                source_path=meta_file,
            ))
        return groups
