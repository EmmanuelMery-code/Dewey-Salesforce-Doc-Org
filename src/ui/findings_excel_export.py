"""Export action behind the findings qualification screen.

Kept apart from :mod:`src.ui.findings_screen` so the screen stays about
widgets while the output-folder validation and the background task wiring
live here.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Collection, Mapping, Sequence

from src.analyzer.models import Finding
from src.core.findings_qualification import FindingQualification, QualificationKey
from src.reporting.excel_writer_findings import (
    FindingsExcelWriter,
    findings_workbook_path,
)

if TYPE_CHECKING:
    from src.ui.application import Application


def export_findings_workbook(
    app: "Application",
    findings: Sequence[Finding],
    *,
    alias: str,
    run_date: date | None = None,
    qualifications: Mapping[QualificationKey, FindingQualification] | None = None,
    resolved_keys: Collection[QualificationKey] = (),
) -> Path | None:
    """Start the background export and return the target path.

    ``None`` means the run was refused because the output folder is not
    usable; the folder validation already told the user about it.
    """
    output = app._validate_output_dir()
    if output is None:
        return None

    # The path is stamped with "now"; ``run_date`` only labels the sheet
    # title with the date of the analysed run.
    target = findings_workbook_path(Path(output) / "excel", alias)
    stored = dict(qualifications or {})
    resolved = set(resolved_keys)

    def task() -> Path:
        writer = FindingsExcelWriter(log_callback=app.task_manager.queue_log)
        return writer.write_findings_workbook(
            findings,
            target,
            alias=alias,
            run_date=run_date,
            qualifications=stored,
            resolved_keys=resolved,
        )

    app.task_manager.start_task(
        status_text=app._t("findings_excel_in_progress"),
        task=task,
        success_message=app._t("findings_excel_success", path=target),
    )
    return target
