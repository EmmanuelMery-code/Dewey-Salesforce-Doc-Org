"""Modal editor for the TechLead columns of a single finding.

Lets the qualification be filled straight from the application, as an
alternative to the Excel round trip. The seven fields map one-to-one onto
the ``M..S`` columns of the workbook, and "Statut" offers exactly the values
the workbook's own dropdown accepts so both routes stay interchangeable.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from src.analyzer.models import Finding
from src.core.findings_qualification import FindingQualification
from src.reporting.excel_writer_findings import STATUSES, severity_label
from src.ui import theme

if TYPE_CHECKING:
    from src.ui.application import Application

# (attribute, translation key, number of text lines — 1 renders an Entry)
_FIELDS: tuple[tuple[str, str, int], ...] = (
    ("team", "findings_screen_column_team", 1),
    ("target_sprint", "findings_screen_column_sprint", 1),
    ("us_number", "findings_screen_column_us", 1),
    ("us_title", "findings_edit_us_title", 1),
    ("us_description", "findings_edit_us_description", 4),
    ("acceptance_criteria", "findings_edit_acceptance_criteria", 4),
)


def edit_finding_qualification(
    parent: tk.Misc,
    app: "Application",
    finding: Finding,
    qualification: FindingQualification,
) -> FindingQualification | None:
    """Show the editor and return the new value, or ``None`` if cancelled.

    Blocks until the dialog closes, so the caller can persist the result
    right away.
    """
    dialog = _QualificationDialog(parent, app, finding, qualification)
    parent.wait_window(dialog.window)
    return dialog.result


class _QualificationDialog:
    def __init__(
        self,
        parent: tk.Misc,
        app: "Application",
        finding: Finding,
        qualification: FindingQualification,
    ) -> None:
        self.app = app
        self.result: FindingQualification | None = None

        self.window = tk.Toplevel(parent)
        self.window.title(app._t("findings_edit_title"))
        self.window.transient(parent)
        self.window.resizable(True, False)

        frame = ttk.Frame(self.window, padding=theme.SPACE_LG)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(
            frame,
            text=f"{severity_label(finding)} · {finding.rule.id} · {finding.target_name}",
            style=theme.TITLE_LABEL,
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            frame,
            text=finding.rule.title,
            font=theme.FONT_SMALL_ITALIC,
            wraplength=520,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, theme.SPACE_MD))

        # Status is a closed list: an empty choice clears the qualification.
        self.status_var = tk.StringVar(value=qualification.status)
        ttk.Label(frame, text=app._t("findings_screen_column_status")).grid(
            row=2, column=0, sticky="w", padx=(0, theme.SPACE_MD), pady=theme.SPACE_XS
        )
        ttk.Combobox(
            frame,
            textvariable=self.status_var,
            values=("", *STATUSES),
            state="readonly",
        ).grid(row=2, column=1, sticky="ew", pady=theme.SPACE_XS)

        self._entries: dict[str, tk.StringVar] = {}
        self._texts: dict[str, tk.Text] = {}
        for offset, (attribute, label_key, lines) in enumerate(_FIELDS, start=3):
            value = getattr(qualification, attribute)
            ttk.Label(frame, text=app._t(label_key)).grid(
                row=offset,
                column=0,
                sticky="nw" if lines > 1 else "w",
                padx=(0, theme.SPACE_MD),
                pady=theme.SPACE_XS,
            )
            if lines == 1:
                variable = tk.StringVar(value=value)
                self._entries[attribute] = variable
                ttk.Entry(frame, textvariable=variable).grid(
                    row=offset, column=1, sticky="ew", pady=theme.SPACE_XS
                )
                continue
            widget = tk.Text(frame, height=lines, width=20, wrap="word")
            widget.insert("1.0", value)
            widget.grid(row=offset, column=1, sticky="ew", pady=theme.SPACE_XS)
            self._texts[attribute] = widget

        buttons = ttk.Frame(frame)
        buttons.grid(
            row=3 + len(_FIELDS),
            column=0,
            columnspan=2,
            sticky="e",
            pady=(theme.SPACE_MD, 0),
        )
        ttk.Button(
            buttons, text=app._t("configuration_cancel"), command=self.window.destroy
        ).pack(side="right")
        ttk.Button(
            buttons,
            text=app._t("data_dictionary_comment_save"),
            command=self._save,
            style=theme.PRIMARY_BUTTON,
        ).pack(side="right", padx=(0, theme.SPACE_SM))

        self.window.bind("<Escape>", lambda _e: self.window.destroy())
        self.window.update_idletasks()
        self.window.grab_set()

    def _save(self) -> None:
        values = {"status": self.status_var.get().strip()}
        values.update(
            {name: variable.get().strip() for name, variable in self._entries.items()}
        )
        values.update(
            {
                name: widget.get("1.0", tk.END).strip()
                for name, widget in self._texts.items()
            }
        )
        self.result = FindingQualification(**values)
        self.window.destroy()
