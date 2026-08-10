"""Mixin — folder clearing, folder policies and PMD/index helpers for
:class:`~src.ui.app_ui_mixin.AppUiMixin`.

Extracted from ``app_ui_mixin.py`` to keep files under the project's
500-line convention.
"""

from __future__ import annotations

import re
import shutil
import webbrowser
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable


class _AppUiFolderPolicyMixin:
    """Clear source/output folders and apply folder policies before generation."""

    # ================================================================== folder clearing

    def _empty_folder_contents(self, path: Path) -> list[str]:
        """Delete everything under ``path`` (not ``path`` itself). Returns errors."""
        errors: list[str] = []
        for item in path.iterdir():
            try:
                if item.is_dir() and not item.is_symlink():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except OSError as exc:
                errors.append(f"{item.name}: {exc}")
        return errors

    def _clear_folder(self, variable) -> None:
        folder = variable.get().strip()
        if not folder or not Path(folder).is_dir():
            messagebox.showerror(
                self._t("error_title"), self._t("directory_missing_to_open")
            )
            return
        path = Path(folder)
        if not messagebox.askyesno(
            self._t("confirmation_delete"),
            self._t("confirm_clear_folder_message", path=str(path)),
        ):
            return
        errors = self._empty_folder_contents(path)
        if errors:
            messagebox.showerror(
                self._t("error_title"),
                self._t("clear_folder_error") + "\n" + "\n".join(errors),
            )
        else:
            messagebox.showinfo(self._t("info_title"), self._t("folder_cleared"))

    def _clear_source_folder(self) -> None:
        self._clear_folder(self.source_var)

    def _clear_output_folder(self) -> None:
        self._clear_folder(self.output_var)

    # ================================================================== folder policy (source/output)

    _DATE_SEGMENT_RE = re.compile(r"^\d{8}$")

    def _resolve_dated_root(self, path: Path) -> Path:
        """Find the root directory preceding an existing ``YYYYMMDD`` segment.

        Walks ``path`` and its parents looking for a segment made of exactly
        8 digits and returns its parent directory. Falls back to ``path``
        itself when no such segment is found.
        """
        for candidate in (path, *path.parents):
            if self._DATE_SEGMENT_RE.match(candidate.name):
                return candidate.parent
        return path

    def _apply_folder_policy(
        self,
        variable,
        policy_var,
        dated_subfolder_name: str,
        report_error: Callable[[str], None] | None = None,
    ) -> bool:
        """Apply the selected folder policy to ``variable`` before it is used.

        Returns ``False`` (after reporting an error) if the policy could not
        be applied, in which case the caller should abort the action. By
        default errors are shown via a message box; pass ``report_error`` to
        redirect them elsewhere (e.g. console/log output for headless runs).
        """
        if report_error is None:
            report_error = lambda msg: messagebox.showerror(self._t("error_title"), msg)

        policy = policy_var.get().strip()
        current = variable.get().strip()
        if not current or policy == self.FOLDER_DIR_POLICIES[0]:
            return True

        path = Path(current)
        if policy == "empty_and_use":
            if path.is_dir():
                errors = self._empty_folder_contents(path)
                if errors:
                    report_error(self._t("clear_folder_error") + "\n" + "\n".join(errors))
                    return False
            return True

        if policy == "dated_subfolder":
            root = self._resolve_dated_root(path)
            today_folder = date.today().strftime("%Y%m%d")
            target = root / today_folder / dated_subfolder_name
            try:
                target.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                report_error(str(exc))
                return False
            variable.set(str(target))
            return True

        return True

    def _apply_source_dir_policy(
        self, report_error: Callable[[str], None] | None = None
    ) -> bool:
        return self._apply_folder_policy(
            self.source_var, self.source_dir_policy_var, "retrieve", report_error
        )

    def _apply_output_dir_policy(
        self, report_error: Callable[[str], None] | None = None
    ) -> bool:
        return self._apply_folder_policy(
            self.output_var, self.output_dir_policy_var, "documentation", report_error
        )

    def _update_folder_widget_state(
        self, widgets: dict[str, ttk.Widget], policy: str
    ) -> None:
        if "clear_button" in widgets:
            widgets["clear_button"].configure(
                state="disabled" if policy == "empty_and_use" else "normal"
            )
        widgets["browse_button"].configure(
            state="disabled" if policy == "dated_subfolder" else "normal"
        )

    def _apply_folder_policy_button_states(self) -> None:
        self._update_folder_widget_state(
            self.source_folder_widgets, self.source_dir_policy_var.get()
        )
        self._update_folder_widget_state(
            self.output_folder_widgets, self.output_dir_policy_var.get()
        )

    # ================================================================== PMD / index

    def _on_pmd_toggle(self) -> None:
        self._apply_pmd_state()
        self._save_settings()

    def _apply_pmd_state(self) -> None:
        state = "normal" if self.pmd_enabled_var.get() else "disabled"
        for key in ("label", "browse_button", "open_button"):
            self.pmd_file_widgets[key].configure(state=state)

    def _selected_pmd_ruleset_file(
        self, report_error: Callable[[str], None] | None = None
    ) -> Path | None:
        if report_error is None:
            report_error = lambda msg: messagebox.showerror(self._t("error_title"), msg)
        value = self.pmd_ruleset_var.get().strip()
        if not value:
            return None
        path = Path(value)
        if not path.exists() or path.is_dir():
            report_error(self._t("directory_missing_to_open"))
            return None
        return path

    def _selected_exclusion_file(
        self, report_error: Callable[[str], None] | None = None
    ) -> Path | None:
        if report_error is None:
            report_error = lambda msg: messagebox.showerror(self._t("error_title"), msg)
        value = self.exclusion_file_var.get().strip()
        if not value:
            return None
        path = Path(value)
        if not path.exists() or path.is_dir():
            report_error(self._t("directory_missing_to_open"))
            return None
        return path

    def _open_index(self) -> None:
        output = self._validate_output_dir()
        if output is None:
            return
        index_path = output / "html" / "index.html"
        if not index_path.exists():
            messagebox.showerror(self._t("error_title"), self._t("index_not_found"))
            return
        webbrowser.open_new_tab(index_path.as_uri())
