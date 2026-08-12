"""Menu action — "Documentation > Creer les CSV des picklists".

A lightweight, standalone export (re-parses the source folder, no full
generation pipeline): mirrors the pattern used by
:mod:`src.ui.data_dictionary_screen`, but runs directly (no picker window)
since there is nothing to configure beyond source/output/exclusion, which
are already set on the main screen.
"""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox
from typing import TYPE_CHECKING

from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.reporting.picklist_csv_writer import PicklistCsvWriter

if TYPE_CHECKING:
    from src.ui.application import Application


def export_picklist_csvs(
    app: Application, *, selected_objects: set[str] | None = None
) -> None:
    """Parse the source folder and write the ``picklist/`` CSV export.

    ``selected_objects`` restricts the export to those object API names
    (used by the "PickList CSV" button on the Data Dictionary screen); when
    ``None`` (Documentation menu entry), every object is exported.
    """
    output = app._validate_output_dir()
    if output is None:
        return

    source_value = app.source_var.get().strip()
    if not source_value:
        messagebox.showerror(app._t("error_title"), app._t("source_folder_required"))
        return
    source = Path(source_value)
    if not source.exists():
        messagebox.showerror(app._t("error_title"), app._t("source_folder_missing"))
        return

    exclusion_file = app._selected_exclusion_file()
    if app.exclusion_file_var.get().strip() and exclusion_file is None:
        return

    def task() -> Path:
        parser = SalesforceMetadataParser(
            source,
            exclusion_config_path=exclusion_file,
            log_callback=app.task_manager.queue_log,
        )
        snapshot = parser.parse()
        if selected_objects is not None:
            snapshot.objects = [
                obj for obj in snapshot.objects if obj.api_name in selected_objects
            ]
        writer = PicklistCsvWriter(log_callback=app.task_manager.queue_log)
        return writer.write_picklist_csv_export(snapshot.objects, output)

    app.task_manager.start_task(
        status_text=app._t("picklist_csv_export_in_progress"),
        task=task,
        success_message=app._t("picklist_csv_export_success"),
    )
