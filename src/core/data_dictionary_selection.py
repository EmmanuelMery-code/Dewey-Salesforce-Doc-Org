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

from src.core.models import ObjectInfo

DEFAULT_STATUS = "-"


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
    include_comment: bool = True
    include_piloted_by: bool = True
    include_status: bool = True
    include_squad: bool = True
    include_squad_consumer: bool = True
    include_field_comment: bool = True
    include_field_piloted_by: bool = True
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
            include_comment=_flag(settings, "dd_include_comment"),
            include_piloted_by=_flag(settings, "dd_include_piloted_by"),
            include_status=_flag(settings, "dd_include_status"),
            include_squad=_flag(settings, "dd_include_squad"),
            include_squad_consumer=_flag(settings, "dd_include_squad_consumer"),
            include_field_comment=_flag(settings, "dd_include_field_comment"),
            include_field_piloted_by=_flag(settings, "dd_include_field_piloted_by"),
            include_field_automation=_flag(settings, "dd_include_field_automation"),
            concat_description=_flag(settings, "dd_concat_description_in_comment"),
        )

    def apply(self, objects: Sequence[ObjectInfo]) -> list[ObjectInfo]:
        """Return copies of the selected objects carrying the extra info.

        Copies rather than in-place mutation: the same snapshot also feeds
        the HTML pages and the full ``data_dictionary.xlsx``, which must
        keep showing the raw parsed metadata.
        """
        selected = []
        for obj in objects:
            if obj.api_name not in self.objects:
                continue
            comments = self.field_comments.get(obj.api_name, {})
            piloted_by = self.field_piloted_by.get(obj.api_name, {})
            selected.append(
                replace(
                    obj,
                    fields=[
                        replace(
                            field_info,
                            dewey_comment=comments.get(field_info.api_name, ""),
                            dewey_piloted_by=piloted_by.get(field_info.api_name, ""),
                        )
                        for field_info in obj.fields
                    ],
                    dewey_comment=self.object_comments.get(obj.api_name, ""),
                    dewey_piloted_by=self.object_piloted_by.get(obj.api_name, ""),
                    dewey_status=self.object_status.get(obj.api_name, DEFAULT_STATUS),
                    dewey_squad=self.object_squad.get(obj.api_name, ""),
                    dewey_squad_consumer=self.object_squad_consumer.get(
                        obj.api_name, ""
                    ),
                )
            )
        return selected

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
