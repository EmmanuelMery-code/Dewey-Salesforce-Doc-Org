"""Findings qualification screen — "Documentation > Creer le document des findings".

Unlike the other Documentation entries this one never re-analyses the source
folder: it lists the findings of an already analysed org, read from the
per-alias caches written at the end of each documentation run.

Qualification values can be entered two ways, both landing in the same
per-org store (see :mod:`src.core.findings_qualification`) and both
pre-filling the columns of every later export: directly in the table (double
click a row) or through the Excel round trip — export the workbook, fill the
Qualification and US columns, import the file back.
"""

from __future__ import annotations

import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

from src.analyzer.models import Finding
from src.core.findings_cache import CachedFindings, load_all_findings_caches
from src.core.findings_qualification import (
    STORE_FILENAME,
    UNNAMED_ALIAS,
    FindingQualification,
    QualificationKey,
    finding_keys,
    load_qualifications,
    save_qualifications,
    store_alias,
)
from src.reporting.excel_reader_findings import (
    FindingsWorkbookError,
    read_findings_qualifications,
)
from src.reporting.excel_writer_findings import severity_label, sort_findings
from src.ui import theme
from src.ui.findings_edit_dialog import edit_finding_qualification
from src.ui.findings_excel_export import export_findings_workbook

if TYPE_CHECKING:
    from src.ui.application import Application

_SEVERITY_TAGS = {
    "Critique": "#f8d7d7",
    "Majeur": "#fde3cf",
    "Mineur": "#fdf3cf",
    "Info": "#dce9f5",
}


def show_findings_screen(app: "Application") -> None:
    """Create and show the findings qualification window."""
    FindingsScreen(app)


class FindingsScreen:
    # The four Dewey columns first, then the seven editable ones in workbook
    # order so the table reads like the M..S block of the exported sheet.
    _COLUMNS = (
        ("severity", "findings_screen_column_severity", 90),
        ("rule", "findings_screen_column_rule", 130),
        ("component", "findings_screen_column_component", 180),
        ("title", "findings_screen_column_title", 240),
        ("status", "findings_screen_column_status", 100),
        ("team", "findings_screen_column_team", 110),
        ("sprint", "findings_screen_column_sprint", 100),
        ("us_number", "findings_screen_column_us", 100),
        ("us_title", "findings_edit_us_title", 180),
        ("us_description", "findings_edit_us_description", 200),
        ("acceptance_criteria", "findings_edit_acceptance_criteria", 200),
    )

    def __init__(self, app: "Application") -> None:
        self.app = app
        self.store_path = app.app_dir / STORE_FILENAME
        self.caches = self._collect_caches()
        self.qualifications = load_qualifications(self.store_path)

        if not self.caches:
            messagebox.showinfo(
                app._t("findings_excel_none_title"), app._t("findings_excel_none")
            )
            return

        self.window = tk.Toplevel(app)
        self.window.title(app._t("findings_screen_title"))
        self.window.geometry("1250x720")
        app._configure_secondary_window(self.window)

        self.alias_var = tk.StringVar()
        self.count_var = tk.StringVar()
        self._build_ui()

        self.alias_combo["values"] = sorted(self.caches)
        self.alias_var.set(self._initial_alias())
        self._refresh_table()

    # ------------------------------------------------------------------ data

    def _collect_caches(self) -> dict[str, CachedFindings]:
        """Cached findings per alias, the in-memory run taking precedence.

        The report still in memory belongs to the org currently configured
        and is at least as recent as its cache, so it wins for that alias.
        """
        caches = {
            store_alias(alias): cached
            for alias, cached in load_all_findings_caches(self.app.app_dir).items()
        }

        report = getattr(self.app, "latest_analyzer_report", None)
        findings = report.all_findings() if report is not None else []
        if findings:
            alias = store_alias(self.app.alias_var.get())
            caches[alias] = CachedFindings(
                findings=findings, alias=alias, generated_at=date.today()
            )
        return caches

    def _initial_alias(self) -> str:
        current = store_alias(self.app.alias_var.get())
        if current in self.caches:
            return current
        return sorted(self.caches)[0]

    def _current_alias(self) -> str:
        return self.alias_var.get() or self._initial_alias()

    def _current_findings(self) -> list[Finding]:
        cached = self.caches.get(self._current_alias())
        if cached is None:
            return []
        return sort_findings(cached.findings)

    def _current_qualifications(self) -> dict[QualificationKey, FindingQualification]:
        return self.qualifications.get(self._current_alias(), {})

    # ------------------------------------------------------------------ ui

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.window, padding=theme.SPACE_LG)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(
            main_frame,
            text=self.app._t("findings_screen_title"),
            style=theme.TITLE_LABEL,
        ).pack(anchor="w")
        ttk.Label(
            main_frame,
            text=self.app._t("findings_screen_description"),
            wraplength=1000,
            justify="left",
        ).pack(anchor="w", pady=(4, theme.SPACE_MD))

        alias_row = ttk.Frame(main_frame)
        alias_row.pack(fill="x", pady=(0, theme.SPACE_MD))
        ttk.Label(alias_row, text=self.app._t("findings_screen_alias_label")).pack(
            side="left", padx=(0, theme.SPACE_SM)
        )
        self.alias_combo = ttk.Combobox(
            alias_row, textvariable=self.alias_var, state="readonly", width=40
        )
        self.alias_combo.pack(side="left")
        self.alias_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_table())
        ttk.Label(
            alias_row, textvariable=self.count_var, font=theme.FONT_SMALL_ITALIC
        ).pack(side="left", padx=(theme.SPACE_MD, 0))

        table_container = ttk.Frame(main_frame)
        table_container.pack(fill="both", expand=True)
        table_container.rowconfigure(0, weight=1)
        table_container.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_container,
            columns=tuple(name for name, _label, _width in self._COLUMNS),
            show="headings",
            selectmode="browse",
        )
        last_column = self._COLUMNS[-1][0]
        for name, label_key, width in self._COLUMNS:
            self.tree.heading(name, text=self.app._t(label_key))
            # Locked widths (see the Data Dictionary screen) so the columns
            # keep their size and the horizontal scrollbar stays useful.
            self.tree.column(
                name,
                width=width,
                minwidth=width,
                stretch=(name == last_column),
                anchor="w",
            )
        for label, color in _SEVERITY_TAGS.items():
            self.tree.tag_configure(label, background=color)

        vertical = ttk.Scrollbar(
            table_container, orient="vertical", command=self.tree.yview
        )
        horizontal = ttk.Scrollbar(
            table_container, orient="horizontal", command=self.tree.xview
        )
        self.tree.configure(
            yscrollcommand=vertical.set, xscrollcommand=horizontal.set
        )
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())
        self.tree.bind("<Return>", lambda _e: self._edit_selected())

        footer = ttk.Frame(main_frame, padding=(0, theme.SPACE_MD, 0, 0))
        footer.pack(fill="x")
        ttk.Label(
            footer,
            text=self.app._t("findings_screen_edit_hint"),
            font=theme.FONT_SMALL_ITALIC,
        ).pack(side="left")
        ttk.Button(
            footer,
            text=self.app._t("configuration_close"),
            command=self.window.destroy,
        ).pack(side="right")
        ttk.Button(
            footer,
            text=self.app._t("findings_screen_export"),
            command=self._export,
            style=theme.PRIMARY_BUTTON,
        ).pack(side="right", padx=(0, theme.SPACE_SM))
        ttk.Button(
            footer,
            text=self.app._t("findings_screen_import"),
            command=self._import,
        ).pack(side="right", padx=(0, theme.SPACE_SM))
        ttk.Button(
            footer,
            text=self.app._t("findings_screen_edit"),
            command=self._edit_selected,
        ).pack(side="right", padx=(0, theme.SPACE_SM))

    def _refresh_table(self, *, keep_selection: str | None = None) -> None:
        findings = self._current_findings()
        stored = self._current_qualifications()

        self.tree.delete(*self.tree.get_children())
        qualified = 0
        for index, (finding, key) in enumerate(
            zip(findings, finding_keys(findings))
        ):
            qualification = stored.get(key) or FindingQualification()
            if not qualification.is_empty():
                qualified += 1
            severity = severity_label(finding)
            self.tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    severity,
                    finding.rule.id,
                    finding.target_name,
                    finding.rule.title,
                    # Newlines would be rendered as boxes in a Treeview cell.
                    *(value.replace("\n", " ") for value in qualification.as_row()),
                ),
                tags=(severity,),
            )

        if keep_selection is not None and self.tree.exists(keep_selection):
            self.tree.selection_set(keep_selection)
            self.tree.focus(keep_selection)
            self.tree.see(keep_selection)

        self.count_var.set(
            self.app._t(
                "findings_screen_count", total=len(findings), qualified=qualified
            )
        )

    # ------------------------------------------------------------------ actions

    def _edit_selected(self) -> None:
        """Qualify the selected finding through the modal editor."""
        findings = self._current_findings()
        selection = self.tree.selection()
        if not selection or not findings:
            messagebox.showinfo(
                self.app._t("info_title"), self.app._t("findings_screen_select_row")
            )
            return

        # Row ids are the index in the sorted list the table was built from.
        index = int(selection[0])
        key = finding_keys(findings)[index]
        current = self._current_qualifications().get(key) or FindingQualification()

        updated = edit_finding_qualification(
            self.window, self.app, findings[index], current
        )
        if updated is None or updated == current:
            return

        alias = self._current_alias()
        bucket = self.qualifications.setdefault(alias, {})
        if updated.is_empty():
            bucket.pop(key, None)
        else:
            bucket[key] = updated
        if self._save_store():
            self._refresh_table(keep_selection=selection[0])

    def _save_store(self) -> bool:
        """Persist the whole store, reporting a write failure to the user."""
        try:
            save_qualifications(self.store_path, self.qualifications)
        except OSError as exc:
            messagebox.showerror(
                self.app._t("error_title"),
                self.app._t("findings_import_error", error=str(exc)),
            )
            return False
        return True

    def _export(self) -> None:
        findings = self._current_findings()
        if not findings:
            messagebox.showinfo(
                self.app._t("findings_excel_none_title"),
                self.app._t("findings_excel_none"),
            )
            return

        alias = self._current_alias()
        cached = self.caches[alias]
        export_findings_workbook(
            self.app,
            findings,
            alias="" if alias == UNNAMED_ALIAS else alias,
            run_date=cached.generated_at,
            qualifications=self._current_qualifications(),
        )

    def _import(self) -> None:
        findings = self._current_findings()
        if not findings:
            return

        file_path = filedialog.askopenfilename(
            title=self.app._t("findings_import_title"),
            filetypes=[("Excel", "*.xlsx"), ("All files", "*.*")],
        )
        if not file_path:
            return

        try:
            imported = read_findings_qualifications(file_path)
        except FindingsWorkbookError as exc:
            messagebox.showerror(
                self.app._t("error_title"),
                self.app._t("findings_import_error", error=str(exc)),
            )
            return

        if not imported:
            messagebox.showinfo(
                self.app._t("info_title"), self.app._t("findings_import_none")
            )
            return

        # Only keep rows that match a finding of this org: a stale workbook
        # would otherwise silently accumulate qualifications pointing at
        # findings that no longer exist.
        known = set(finding_keys(findings))
        matched = {key: value for key, value in imported.items() if key in known}
        unmatched = len(imported) - len(matched)

        alias = self._current_alias()
        if matched:
            self.qualifications.setdefault(alias, {}).update(matched)
            if not self._save_store():
                return
            self._refresh_table()

        message = self.app._t(
            "findings_import_success",
            count=len(matched),
            alias=alias,
            path=Path(file_path).name,
        )
        if unmatched:
            message += "\n\n" + self.app._t(
                "findings_import_unmatched", count=unmatched
            )
        messagebox.showinfo(self.app._t("success_title"), message)
