"""Export action behind the technical debt management screen.

Kept apart from :mod:`src.ui.debt_screen` so the screen stays about widgets
while the output-folder validation and the background task wiring live here.
The workbook is the same one a full documentation run writes, so the
TechLead can refresh it after editing the debt without re-analysing the org.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Mapping, Sequence

from src.core.models import DeviationItem, TechnicalDebtItem
from src.reporting.excel_writer import ExcelReportWriter
from src.reporting.excel_writer_debt import DEBT_WORKBOOK_NAME

if TYPE_CHECKING:
    from src.ui.application import Application


def export_debt_workbook(
    app: "Application",
    technical_debt: Sequence[tuple[str, Mapping[str, str]]],
    deviations: Sequence[tuple[str, Mapping[str, str]]],
) -> Path | None:
    """Start the background export and return the target path.

    ``None`` means the run was refused because the output folder is not
    usable; the folder validation already told the user about it.

    The screen hands over the rows it displays, as the raw dictionaries read
    from the JSON file; they are converted here to the same items a run
    builds from that file.
    """
    output = app._validate_output_dir()
    if output is None:
        return None

    target = Path(output) / "excel" / DEBT_WORKBOOK_NAME
    debt_items = [
        (
            alias,
            TechnicalDebtItem(
                label=item.get("label", ""),
                date_creation=item.get("date_creation", ""),
                date_resolution=item.get("date_resolution", ""),
                accepted_solution=item.get("accepted_solution", ""),
                target_solution=item.get("target_solution", ""),
            ),
        )
        for alias, item in technical_debt
    ]
    deviation_items = [
        (
            alias,
            DeviationItem(
                label=item.get("label", ""),
                date_creation=item.get("date_creation", ""),
                explanation=item.get("explanation", ""),
            ),
        )
        for alias, item in deviations
    ]

    def task() -> Path:
        writer = ExcelReportWriter(log_callback=app.task_manager.queue_log)
        return writer.write_debt_workbook(
            debt_items,
            deviation_items,
            target,
            include_alias=True,
        )

    app.task_manager.start_task(
        status_text=app._t("debt_excel_in_progress"),
        task=task,
        success_message=app._t("debt_excel_success", path=target),
    )
    return target
