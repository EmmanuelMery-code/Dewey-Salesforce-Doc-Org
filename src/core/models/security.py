"""Security-related metadata dataclasses (profiles, permission sets, accesses)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ObjectPermission:
    object_name: str
    allow_read: bool = False
    allow_create: bool = False
    allow_edit: bool = False
    allow_delete: bool = False
    view_all_records: bool = False
    modify_all_records: bool = False


@dataclass(slots=True)
class FieldPermission:
    field_name: str
    readable: bool = False
    editable: bool = False


@dataclass(slots=True)
class UserPermission:
    name: str
    enabled: bool = False


@dataclass(slots=True)
class VisibilityItem:
    name: str
    visible: str = ""
    default: str = ""


@dataclass(slots=True)
class NamedAccess:
    name: str
    enabled: bool = False


@dataclass(slots=True)
class RecordTypeVisibility:
    record_type: str
    visible: bool = False
    default: bool = False


@dataclass(slots=True)
class SecurityArtifact:
    name: str
    kind: str
    label: str = ""
    description: str = ""
    is_custom: bool = False
    source_path: Path | None = None
    object_permissions: list[ObjectPermission] = field(default_factory=list)
    field_permissions: list[FieldPermission] = field(default_factory=list)
    user_permissions: list[UserPermission] = field(default_factory=list)
    application_visibilities: list[VisibilityItem] = field(default_factory=list)
    tab_visibilities: list[VisibilityItem] = field(default_factory=list)
    class_accesses: list[NamedAccess] = field(default_factory=list)
    flow_accesses: list[NamedAccess] = field(default_factory=list)
    page_accesses: list[NamedAccess] = field(default_factory=list)
    custom_permissions: list[NamedAccess] = field(default_factory=list)
    record_type_visibilities: list[RecordTypeVisibility] = field(default_factory=list)


@dataclass(slots=True)
class PermissionSetGroupInfo:
    name: str
    label: str = ""
    description: str = ""
    status: str = ""
    permission_sets: list[str] = field(default_factory=list)
    source_path: Path | None = None
