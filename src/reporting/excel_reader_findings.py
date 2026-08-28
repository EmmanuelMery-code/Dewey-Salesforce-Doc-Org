"""Read the TechLead columns back from a reviewed findings workbook.

Counterpart of :mod:`src.reporting.excel_writer_findings`: only the ``M..S``
columns are read, keyed on the component (``E``) and the rule (``C``) as
described in :mod:`src.core.findings_qualification`. The Dewey-owned ``A..L``
columns are ignored — the findings themselves always come from the analyzer,
never from the reviewed file.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from src.core.findings_qualification import (
    QUALIFICATION_FIELD_COUNT,
    FindingQualification,
    QualificationKey,
    assign_keys,
)
from src.reporting.excel_writer_findings import (
    COMPONENT_COLUMN,
    FINDINGS_SHEET,
    FIRST_DATA_ROW,
    QUALIFICATION_FIRST_COLUMN,
    RULE_COLUMN,
)


class FindingsWorkbookError(Exception):
    """Raised when a file cannot be read as a Dewey findings workbook."""


def read_findings_qualifications(
    workbook_path: str | Path,
) -> dict[QualificationKey, FindingQualification]:
    """Qualifications found in ``workbook_path``, keyed per finding.

    Rows whose component and rule are both blank are skipped (trailing
    formatting leftovers), as are rows where the seven TechLead columns are
    all empty. Occurrence indexes follow the row order of the file, so an
    untouched Dewey export re-imports onto the exact same findings.
    """
    path = Path(workbook_path)
    try:
        workbook = load_workbook(path, data_only=True, read_only=True)
    except OSError as exc:
        raise FindingsWorkbookError(str(exc)) from exc
    except Exception as exc:  # openpyxl raises assorted types on bad files
        raise FindingsWorkbookError(str(exc)) from exc

    try:
        if FINDINGS_SHEET not in workbook.sheetnames:
            raise FindingsWorkbookError(
                f"Feuille « {FINDINGS_SHEET} » absente du fichier."
            )
        sheet = workbook[FINDINGS_SHEET]

        pairs: list[tuple[str, str]] = []
        rows: list[FindingQualification] = []
        last_column = QUALIFICATION_FIRST_COLUMN + QUALIFICATION_FIELD_COUNT - 1
        for row in sheet.iter_rows(
            min_row=FIRST_DATA_ROW, max_col=last_column, values_only=True
        ):
            component = _text(row, COMPONENT_COLUMN)
            rule_id = _text(row, RULE_COLUMN)
            if not component and not rule_id:
                continue
            pairs.append((component, rule_id))
            rows.append(
                FindingQualification.from_row(
                    row[QUALIFICATION_FIRST_COLUMN - 1 : last_column]
                )
            )
    finally:
        workbook.close()

    return {
        key: qualification
        for key, qualification in zip(assign_keys(pairs), rows)
        if not qualification.is_empty()
    }


def _text(row: tuple, column: int) -> str:
    """1-based column lookup on a ``values_only`` row, tolerant to short rows."""
    if column > len(row):
        return ""
    value = row[column - 1]
    return "" if value is None else str(value).strip()
