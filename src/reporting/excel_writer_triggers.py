"""Classeur Excel ``trigger.xlsx``.

Une ligne par objet portant au moins un trigger Apex ou un flow
record-triggered, une colonne par couple (moment, evenement). Chaque cellule
liste les noms des triggers / flows concernes ; ceux qui ne sont pas actifs
sont suffixes par ``(inactif)``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

from openpyxl import Workbook
from openpyxl.styles import Alignment

from src.core.models import ApexArtifact, FlowInfo, ObjectInfo
from src.parsers.salesforce_parser.apex_helpers import _strip_apex_comments

TRIGGER_WORKBOOK_NAME = "trigger.xlsx"
TRIGGER_SHEET = "Triggers"

INACTIVE_SUFFIX = " (inactif)"

#: (colonne, cle interne) dans l'ordre d'affichage.
_EVENT_COLUMNS: list[tuple[str, str]] = [
    ("Apex Before Insert", "apex:before insert"),
    ("Apex Before Update", "apex:before update"),
    ("Apex Before Delete", "apex:before delete"),
    ("Apex After Insert", "apex:after insert"),
    ("Apex After Update", "apex:after update"),
    ("Apex After Delete", "apex:after delete"),
    ("Apex After Undelete", "apex:after undelete"),
    ("Flow Before Create", "flow:before create"),
    ("Flow Before Update", "flow:before update"),
    ("Flow Before Delete", "flow:before delete"),
    ("Flow After Create", "flow:after create"),
    ("Flow After Update", "flow:after update"),
]

_HEADERS = ["Objet (API Name)", "Label", *(header for header, _ in _EVENT_COLUMNS)]

_TRIGGER_HEADER_RE = re.compile(
    r"\btrigger\s+\w+\s+on\s+([\w.]+)\s*\(([^)]*)\)", re.IGNORECASE
)

_FLOW_SAVE_TIMING = {"RecordBeforeSave": "before", "RecordAfterSave": "after"}
_FLOW_SAVE_EVENTS = {
    "Create": ("create",),
    "Update": ("update",),
    "CreateAndUpdate": ("create", "update"),
}


def apex_trigger_events(body: str) -> tuple[str, list[str]]:
    """Return ``(objet, ["before insert", ...])`` read from a trigger header."""

    match = _TRIGGER_HEADER_RE.search(_strip_apex_comments(body))
    if match is None:
        return "", []
    events = [" ".join(event.lower().split()) for event in match.group(2).split(",")]
    return match.group(1), [event for event in events if event]


def flow_trigger_events(flow: FlowInfo) -> list[str]:
    """Return ``["before create", ...]`` for a record-triggered flow."""

    if flow.trigger_type == "RecordBeforeDelete":
        return ["before delete"]
    timing = _FLOW_SAVE_TIMING.get(flow.trigger_type)
    if timing is None:
        return []
    return [f"{timing} {event}" for event in _FLOW_SAVE_EVENTS.get(flow.record_trigger_type, ())]


def _display_name(name: str, status: str, active_status: str) -> str:
    return name if status in ("", active_status) else f"{name}{INACTIVE_SUFFIX}"


class _ExcelTriggersMixin:
    """Ajoute ``write_triggers_workbook`` a :class:`ExcelReportWriter`."""

    def write_triggers_workbook(
        self,
        apex_artifacts: Sequence[ApexArtifact],
        flows: Sequence[FlowInfo],
        objects: Sequence[ObjectInfo],
        output_path: str | Path,
    ) -> Path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        matrix: dict[str, dict[str, list[str]]] = {}

        def register(object_name: str, key: str, name: str) -> None:
            names = matrix.setdefault(object_name, {}).setdefault(key, [])
            if name not in names:
                names.append(name)

        for artifact in apex_artifacts:
            if artifact.kind != "trigger":
                continue
            object_name, events = apex_trigger_events(artifact.body)
            name = _display_name(artifact.name, artifact.status, "Active")
            for event in events:
                register(object_name, f"apex:{event}", name)

        for flow in flows:
            if not flow.start_object:
                continue
            name = _display_name(flow.name, flow.status, "Active")
            for event in flow_trigger_events(flow):
                register(flow.start_object, f"flow:{event}", name)

        labels = {obj.api_name: obj.label for obj in objects}
        rows = [
            [
                object_name,
                labels.get(object_name, ""),
                *("\n".join(sorted(matrix[object_name].get(key, []), key=str.lower)) for _, key in _EVENT_COLUMNS),
            ]
            for object_name in sorted(matrix, key=str.lower)
        ]

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = TRIGGER_SHEET
        self._write_sheet(sheet, _HEADERS, rows)
        for row in sheet.iter_rows(min_row=2, min_col=3):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")

        workbook.save(output)
        self.log(f"Classeur triggers genere ({len(rows)} objet(s)): {output}")
        return output
