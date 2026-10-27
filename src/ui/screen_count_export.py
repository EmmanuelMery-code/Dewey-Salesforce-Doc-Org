"""Menu action — Documentation > Compter les écrans.

Relit le dossier source et écrit le classeur des écrans par type et par
squad. Les squads du second tableau sont celles enregistrées par l'écran
Data Dictionary (Squad responsable, Piloté par, Squad consommatrice).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from tkinter import messagebox
from typing import TYPE_CHECKING

from src.core.data_dictionary_selection import DataDictionarySelection
from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.reporting.excel_writer_screens import write_screen_count_workbook
from src.reporting.screen_count_collect import collect_screens, grants_from_permission_sets

if TYPE_CHECKING:
    from src.ui.application import Application


def export_screen_count(app: Application) -> None:
    """Parse le dossier source et écrit ``excel/ecrans_YYYYMMDD.xlsx``."""
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

    selection = DataDictionarySelection.from_settings(app.settings)
    target = output / "excel" / f"ecrans_{date.today():%Y%m%d}.xlsx"

    def task() -> Path:
        parser = SalesforceMetadataParser(
            source,
            exclusion_config_path=exclusion_file,
            log_callback=app.task_manager.queue_log,
        )
        snapshot = parser.parse()
        result = collect_screens(
            snapshot.package_roots,
            squad_grants=grants_from_permission_sets(snapshot.permission_sets),
            known_objects={obj.api_name for obj in snapshot.objects},
            object_squad=selection.object_squad,
            object_piloted_by=selection.object_piloted_by,
            object_squad_consumer=selection.object_squad_consumer,
            is_excluded=parser._is_excluded,
        )
        return write_screen_count_workbook(
            result, target, log_callback=app.task_manager.queue_log
        )

    app.task_manager.start_task(
        status_text=app._t("screen_count_in_progress"),
        task=task,
        success_message=app._t("screen_count_success", path=target),
    )
