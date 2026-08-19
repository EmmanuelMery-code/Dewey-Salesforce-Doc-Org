"""Mixin — path/folder/file picker widgets for :class:`~src.ui.app_ui_mixin.AppUiMixin`.

Extracted from ``app_ui_mixin.py`` to keep files under the project's
500-line convention.
"""

from __future__ import annotations

import os
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

import tkinter as tk

from src.ui import theme


class _AppUiPickersMixin:
    """Build and interact with path/folder/file picker widgets."""

    # ================================================================== path/file pickers

    def _folder_picker(
        self,
        parent: tk.Widget,
        variable: tk.StringVar,
        browse_command: Callable[[], None],
        open_command: Callable[[], None],
        clear_command: Callable[[], None] | None = None,
    ) -> dict[str, ttk.Widget]:
        return self._path_picker(parent, variable, browse_command, open_command, clear_command)

    def _file_picker(
        self,
        parent: tk.Widget,
        variable: tk.StringVar,
        browse_command: Callable[[], None],
        open_command: Callable[[], None],
    ) -> dict[str, ttk.Widget]:
        return self._path_picker(parent, variable, browse_command, open_command)

    def _path_picker(
        self,
        parent: tk.Widget,
        variable: tk.StringVar,
        browse_command: Callable[[], None],
        open_command: Callable[[], None],
        clear_command: Callable[[], None] | None = None,
    ) -> dict[str, ttk.Widget]:
        wrapper = ttk.Frame(parent)
        wrapper.pack(fill="x", pady=theme.SPACE_SM)
        label = ttk.Label(wrapper, width=18)
        label.pack(side="left")
        entry = ttk.Entry(wrapper, textvariable=variable)
        entry.pack(side="left", fill="x", expand=True, padx=(0, theme.SPACE_SM))
        browse_button = self._track_button(ttk.Button(wrapper, command=browse_command))
        browse_button.pack(side="left", padx=(0, theme.SPACE_SM))
        open_button = self._track_button(ttk.Button(wrapper, command=open_command))
        open_button.pack(side="left")
        widgets: dict[str, ttk.Widget] = {
            "label": label,
            "browse_button": browse_button,
            "open_button": open_button,
        }
        if clear_command is not None:
            # Destructive action (empties the folder) — flagged with the
            # shared "danger" style instead of a plain button.
            clear_button = self._track_button(
                ttk.Button(wrapper, style=theme.DANGER_BUTTON, command=clear_command)
            )
            clear_button.pack(side="left", padx=(theme.SPACE_SM, 0))
            widgets["clear_button"] = clear_button
        return widgets

    # ================================================================== file browse/open

    def _choose_source(self) -> None:
        folder = filedialog.askdirectory(title=self._t("choose_source_folder"))
        if folder:
            self.source_var.set(folder)

    def _choose_output(self) -> None:
        folder = filedialog.askdirectory(title=self._t("choose_output_folder"))
        if folder:
            self.output_var.set(folder)

    def _choose_exclusion_file(self) -> None:
        path = filedialog.askopenfilename(
            title=self._t("choose_exclusion_file"),
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.exclusion_file_var.set(path)
            self._save_settings()

    def _choose_pmd_ruleset_file(self) -> None:
        path = filedialog.askopenfilename(
            title=self._t("choose_pmd_ruleset_file"),
            filetypes=[("XML", "*.xml"), ("All files", "*.*")],
        )
        if path:
            self.pmd_ruleset_var.set(path)
            self._save_settings()

    def _choose_analyzer_rules_file(self) -> None:
        path = filedialog.askopenfilename(
            title=self._t("choose_analyzer_rules_file"),
            filetypes=[("XML", "*.xml"), ("All files", "*.*")],
        )
        if path:
            self.analyzer_rules_file_var.set(path)
            self._analyzer_rules_file = Path(path)
            self._save_settings()

    def _open_folder(self, variable: tk.StringVar) -> None:
        folder = variable.get().strip()
        if not folder or not Path(folder).exists():
            messagebox.showerror(
                self._t("error_title"), self._t("directory_missing_to_open")
            )
            return
        os.startfile(folder)  # type: ignore[attr-defined]

    def _open_source_folder(self) -> None:
        self._open_folder(self.source_var)

    def _open_output_folder(self) -> None:
        self._open_folder(self.output_var)

    def _open_exclusion_file(self) -> None:
        file_path = self.exclusion_file_var.get().strip()
        if not file_path or not Path(file_path).exists():
            messagebox.showerror(
                self._t("error_title"), self._t("directory_missing_to_open")
            )
            return
        os.startfile(file_path)  # type: ignore[attr-defined]

    def _open_pmd_ruleset_file(self) -> None:
        file_path = self.pmd_ruleset_var.get().strip()
        if not file_path or not Path(file_path).exists():
            messagebox.showerror(
                self._t("error_title"), self._t("directory_missing_to_open")
            )
            return
        os.startfile(file_path)  # type: ignore[attr-defined]

    def _open_analyzer_rules_file(self) -> None:
        file_path = self.analyzer_rules_file_var.get().strip()
        if not file_path or not Path(file_path).exists():
            messagebox.showerror(
                self._t("error_title"), self._t("directory_missing_to_open")
            )
            return
        os.startfile(file_path)  # type: ignore[attr-defined]

    def _on_login_target_changed(self, _event=None) -> None:
        selected_target = self._login_target_key_from_display(self.login_target_var.get())
        self.login_target_key = selected_target
        if selected_target == "custom":
            self.instance_url_entry.configure(state="normal")
            if self.instance_url_var.get().strip() in (
                self.LOGIN_TARGETS["production"],
                self.LOGIN_TARGETS["sandbox"],
                "",
            ):
                self.instance_url_var.set("")
        else:
            self.instance_url_var.set(self.LOGIN_TARGETS[selected_target])
            self.instance_url_entry.configure(state="readonly")
        self._save_settings()
