"""Object selection and Dewey-authored extra info for the Data Dictionary.

Two entry points produce the same "Data Dictionnary" workbook: the Data
Dictionary screen (immediate generation) and the full documentation run
(``Rapports a generer > Generer le Data Dictionnary pour les objets
selectionnes``). Both need to restrict a snapshot to the objects picked by
the user and attach the free text entered in that screen (Commentaire
Dewey, Pilote par, Status, Squads) before handing the objects to the Excel
writer, hence this shared description of a selection.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Mapping, Sequence

from src.core.models import FieldInfo, ObjectInfo

DEFAULT_STATUS = "-"
#: Status forced on objects/fields the user declared but that the org
#: metadata does not contain (yet).
IN_DESIGN_STATUS = "En conception"
#: Status a virtual entry is promoted to once the metadata contains it.
DELIVERED_STATUS = "Livré"


def data_dictionary_filename_base(run_date: date | None = None) -> str:
    """Stem shared by the Data Dictionary Excel/Word/HTML outputs of a run."""
    return f"dataDictionnary_{(run_date or date.today()).strftime('%Y%m%d')}"


@dataclass(slots=True)
class DataDictionarySelection:
    """Objects picked in the Data Dictionary screen plus their extra info."""

    objects: set[str] = field(default_factory=set)
    object_comments: dict[str, str] = field(default_factory=dict)
    object_piloted_by: dict[str, str] = field(default_factory=dict)
    object_status: dict[str, str] = field(default_factory=dict)
    object_squad: dict[str, str] = field(default_factory=dict)
    object_squad_consumer: dict[str, str] = field(default_factory=dict)
    field_comments: dict[str, dict[str, str]] = field(default_factory=dict)
    field_piloted_by: dict[str, dict[str, str]] = field(default_factory=dict)
    field_status: dict[str, dict[str, str]] = field(default_factory=dict)
    #: ``{object_api_name: {"label": str}}`` for objects declared in the
    #: screen but absent from the parsed metadata.
    virtual_objects: dict[str, dict[str, str]] = field(default_factory=dict)
    #: ``{object_api_name: {field_api_name: {"label": str, "type": str}}}``
    virtual_fields: dict[str, dict[str, dict[str, str]]] = field(default_factory=dict)
    include_comment: bool = True
    include_piloted_by: bool = True
    include_status: bool = True
    include_squad: bool = True
    include_squad_consumer: bool = True
    include_field_comment: bool = True
    include_field_piloted_by: bool = True
    include_field_status: bool = True
    include_field_automation: bool = True
    concat_description: bool = True

    @classmethod
    def from_settings(cls, settings: Mapping[str, Any]) -> DataDictionarySelection:
        """Rebuild the selection last saved by the Data Dictionary screen."""
        return cls(
            objects={
                str(name) for name in settings.get("dd_selected_objects", []) or []
            },
            object_comments=_str_map(settings.get("dd_object_comments")),
            object_piloted_by=_str_map(settings.get("dd_object_piloted_by")),
            object_status=_str_map(settings.get("dd_object_status")),
            object_squad=_str_map(settings.get("dd_object_squad")),
            object_squad_consumer=_str_map(settings.get("dd_object_squad_consumer")),
            field_comments=_nested_str_map(settings.get("dd_field_comments")),
            field_piloted_by=_nested_str_map(settings.get("dd_field_piloted_by")),
            field_status=_nested_str_map(settings.get("dd_field_status")),
            virtual_objects=_virtual_object_map(settings.get("dd_virtual_objects")),
            virtual_fields=_virtual_field_map(settings.get("dd_virtual_fields")),
            include_comment=_flag(settings, "dd_include_comment"),
            include_piloted_by=_flag(settings, "dd_include_piloted_by"),
            include_status=_flag(settings, "dd_include_status"),
            include_squad=_flag(settings, "dd_include_squad"),
            include_squad_consumer=_flag(settings, "dd_include_squad_consumer"),
            include_field_comment=_flag(settings, "dd_include_field_comment"),
            include_field_piloted_by=_flag(settings, "dd_include_field_piloted_by"),
            include_field_status=_flag(settings, "dd_include_field_status"),
            include_field_automation=_flag(settings, "dd_include_field_automation"),
            concat_description=_flag(settings, "dd_concat_description_in_comment"),
        )

    def apply(self, objects: Sequence[ObjectInfo]) -> list[ObjectInfo]:
        """Return copies of the selected objects carrying the extra info.

        Copies rather than in-place mutation: the same snapshot also feeds
        the HTML pages and the full ``data_dictionary.xlsx``, which must
        keep showing the raw parsed metadata.

        Objects and fields the user declared as "En conception" are absent
        from the parsed snapshot, so they are synthesized here: this is the
        single choke point both the screen and the full documentation run go
        through before handing the objects to the writers.
        """
        selected = []
        for obj in objects:
            if obj.api_name not in self.objects:
                continue
            comments = self.field_comments.get(obj.api_name, {})
            piloted_by = self.field_piloted_by.get(obj.api_name, {})
            status = self.field_status.get(obj.api_name, {})
            known_fields = {field_info.api_name for field_info in obj.fields}
            selected.append(
                replace(
                    obj,
                    fields=[
                        replace(
                            field_info,
                            dewey_comment=comments.get(field_info.api_name, ""),
                            dewey_piloted_by=piloted_by.get(field_info.api_name, ""),
                            dewey_status=status.get(field_info.api_name, ""),
                        )
                        for field_info in obj.fields
                    ]
                    + self._virtual_field_infos(obj.api_name, exclude=known_fields),
                    dewey_comment=self.object_comments.get(obj.api_name, ""),
                    dewey_piloted_by=self.object_piloted_by.get(obj.api_name, ""),
                    dewey_status=self.object_status.get(obj.api_name, DEFAULT_STATUS),
                    dewey_squad=self.object_squad.get(obj.api_name, ""),
                    dewey_squad_consumer=self.object_squad_consumer.get(
                        obj.api_name, ""
                    ),
                )
            )

        parsed_names = {obj.api_name for obj in objects}
        for api_name, info in sorted(self.virtual_objects.items()):
            if api_name not in self.objects or api_name in parsed_names:
                continue
            selected.append(
                ObjectInfo(
                    api_name=api_name,
                    label=info.get("label") or api_name,
                    custom=api_name.endswith("__c"),
                    fields=self._virtual_field_infos(api_name),
                    dewey_comment=self.object_comments.get(api_name, ""),
                    dewey_piloted_by=self.object_piloted_by.get(api_name, ""),
                    dewey_status=self.object_status.get(api_name, IN_DESIGN_STATUS),
                    dewey_squad=self.object_squad.get(api_name, ""),
                    dewey_squad_consumer=self.object_squad_consumer.get(api_name, ""),
                    is_virtual=True,
                )
            )
        return selected

    def _virtual_field_infos(
        self, object_api_name: str, exclude: set[str] | None = None
    ) -> list[FieldInfo]:
        exclude = exclude or set()
        comments = self.field_comments.get(object_api_name, {})
        piloted_by = self.field_piloted_by.get(object_api_name, {})
        status = self.field_status.get(object_api_name, {})
        return [
            FieldInfo(
                api_name=api_name,
                label=info.get("label") or api_name,
                data_type=info.get("type", ""),
                custom=api_name.endswith("__c"),
                dewey_comment=comments.get(api_name, ""),
                dewey_piloted_by=piloted_by.get(api_name, ""),
                dewey_status=status.get(api_name, IN_DESIGN_STATUS),
                is_virtual=True,
            )
            for api_name, info in sorted(
                self.virtual_fields.get(object_api_name, {}).items()
            )
            if api_name not in exclude
        ]

    def workbook_options(self) -> dict[str, bool]:
        """Column toggles accepted by ``write_data_dictionary_workbooks``."""
        return {
            "include_comment": self.include_comment,
            "include_piloted_by": self.include_piloted_by,
            "include_status": self.include_status,
            "include_squad": self.include_squad,
            "include_squad_consumer": self.include_squad_consumer,
            "include_field_comment": self.include_field_comment,
            "include_field_piloted_by": self.include_field_piloted_by,
            "include_field_status": self.include_field_status,
            "include_field_automation": self.include_field_automation,
            "concat_description": self.concat_description,
        }


def _flag(settings: Mapping[str, Any], key: str) -> bool:
    return bool(settings.get(key, True))


def _str_map(raw: Any) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): str(value) for key, value in raw.items() if value is not None}


def _nested_str_map(raw: Any) -> dict[str, dict[str, str]]:
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): _str_map(value) for key, value in raw.items()}


def _virtual_object_map(raw: Any) -> dict[str, dict[str, str]]:
    return _nested_str_map(raw)


def _virtual_field_map(raw: Any) -> dict[str, dict[str, dict[str, str]]]:
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): _nested_str_map(value) for key, value in raw.items()}
