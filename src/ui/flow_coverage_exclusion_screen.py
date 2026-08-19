"""Flow coverage exclusion screen (Mode A).

Lets the user pick which Flow ``processType`` values (screen flow,
autolaunched flow, workflow, ...) are left out of the test coverage
calculation. Screen flows are excluded by default (see
:mod:`src.core.flow_coverage_exclusions`) since they are typically
validated through manual UI testing rather than an Apex/Flow test class.

Settings are stored as a new ``flow_coverage_exclusions`` key inside the
same JSON file already used by :mod:`src.ui.exclusion_screen`
(``app.exclusion_file_var``), so there is a single exclusion file to manage.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

from src.core.flow_coverage_exclusions import (
    DEFAULT_EXCLUDED_FLOW_PROCESS_TYPES,
    FLOW_PROCESS_TYPE_OPTIONS,
    load_flow_coverage_exclusions,
    save_flow_coverage_exclusions,
)
from src.ui import theme

if TYPE_CHECKING:
    from src.ui.application import Application


def show_flow_coverage_exclusion_screen(app: Application) -> None:
    """Create and show the flow coverage exclusion window (or focus it)."""
    existing = getattr(app, "flow_coverage_exclusion_window", None)
    if existing is not None and existing.winfo_exists():
        existing.deiconify()
        existing.lift()
        existing.focus_set()
        return
    FlowCoverageExclusionScreen(app)


class FlowCoverageExclusionScreen:
    def __init__(self, app: Application) -> None:
        self.app = app
        self.window = tk.Toplevel(app)
        self.window.title(app._t("flow_coverage_exclusions_title"))
        self.window.geometry("640x600")
        app._configure_secondary_window(self.window)
        app.flow_coverage_exclusion_window = self.window

        self.check_vars: dict[str, tk.BooleanVar] = {}

        self._build_ui()
        self._load_data()

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.window, padding=theme.SPACE_LG)
        main_frame.pack(fill="both", expand=True)

        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, theme.SPACE_MD))

        ttk.Label(
            header_frame,
            text=self.app._t("flow_coverage_exclusions_title"),
            style=theme.TITLE_LABEL,
        ).pack(anchor="w")

        ttk.Label(
            header_frame,
            text=self.app._t("flow_coverage_exclusions_description"),
            wraplength=580,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        # File selection — shares the same JSON file as the exclusion screen.
        file_frame = ttk.LabelFrame(
            main_frame, text=self.app._t("exclusions_file_label"), padding=theme.SPACE_MD
        )
        file_frame.pack(fill="x", pady=(0, theme.SPACE_MD))

        file_row = ttk.Frame(file_frame)
        file_row.pack(fill="x")

        ttk.Entry(file_row, textvariable=self.app.exclusion_file_var).pack(
            side="left", fill="x", expand=True, padx=(0, theme.SPACE_SM)
        )
        ttk.Button(
            file_row, text=self.app._t("exclusions_browse"), command=self._browse_file
        ).pack(side="left")

        # Flow process type checkboxes.
        types_frame = ttk.LabelFrame(
            main_frame,
            text=self.app._t("flow_coverage_exclusions_types_section"),
            padding=theme.SPACE_MD,
        )
        types_frame.pack(fill="both", expand=True)

        for raw_value, label_key in FLOW_PROCESS_TYPE_OPTIONS:
            var = tk.BooleanVar(value=raw_value in DEFAULT_EXCLUDED_FLOW_PROCESS_TYPES)
            self.check_vars[raw_value] = var
            row = ttk.Frame(types_frame)
            row.pack(fill="x", pady=2)
            ttk.Checkbutton(row, text=self.app._t(label_key), variable=var).pack(side="left")
            ttk.Label(
                row,
                text=f"({raw_value})",
                style=theme.MUTED_LABEL,
            ).pack(side="left", padx=(theme.SPACE_SM, 0))

        # Footer buttons.
        footer_frame = ttk.Frame(main_frame, padding=(0, theme.SPACE_MD, 0, 0))
        footer_frame.pack(fill="x")

        ttk.Button(
            footer_frame,
            text=self.app._t("configuration_close"),
            command=self.window.destroy,
        ).pack(side="right")

        ttk.Button(
            footer_frame,
            text=self.app._t("exclusions_save"),
            command=self._save_data,
            style=theme.PRIMARY_BUTTON,
        ).pack(side="right", padx=(0, theme.SPACE_SM))

        ttk.Button(
            footer_frame,
            text=self.app._t("flow_coverage_exclusions_reset_defaults"),
            command=self._reset_defaults,
        ).pack(side="left")

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title=self.app._t("choose_exclusion_file"),
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.app.exclusion_file_var.set(path)
            self._load_data()

    def _config_path(self) -> Path | None:
        value = self.app.exclusion_file_var.get().strip()
        return Path(value) if value else None

    def _load_data(self) -> None:
        excluded = load_flow_coverage_exclusions(self._config_path())
        for raw_value, var in self.check_vars.items():
            var.set(raw_value in excluded)

    def _reset_defaults(self) -> None:
        for raw_value, var in self.check_vars.items():
            var.set(raw_value in DEFAULT_EXCLUDED_FLOW_PROCESS_TYPES)

    def _save_data(self) -> None:
        path = self._config_path()
        if path is None:
            chosen = filedialog.asksaveasfilename(
                title=self.app._t("choose_exclusion_file"),
                defaultextension=".json",
                filetypes=[("JSON", "*.json")],
            )
            if not chosen:
                return
            path = Path(chosen)
            self.app.exclusion_file_var.set(str(path))

        try:
            excluded = {raw for raw, var in self.check_vars.items() if var.get()}
            save_flow_coverage_exclusions(path, excluded)
            self.app._save_settings()
            messagebox.showinfo(self.app._t("info_title"), self.app._t("exclusions_saved"))
        except Exception as e:
            messagebox.showerror(
                self.app._t("error_title"), f"{self.app._t('exclusions_save_error')}\n{e}"
            )
