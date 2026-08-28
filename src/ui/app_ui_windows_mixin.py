"""Mixin — secondary-window navigation for :class:`~src.ui.app_ui_mixin.AppUiMixin`.

Extracted from ``app_ui_mixin.py`` to keep files under the project's
500-line convention.
"""

from __future__ import annotations

import webbrowser

import tkinter as tk

from src.ui.config_window import show_configuration_screen
from src.ui.dashboard_designer_screen import show_dashboard_designer_screen
from src.ui.data_dictionary_screen import show_data_dictionary_screen
from src.ui.exclusion_screen import show_exclusion_screen
from src.ui.findings_screen import show_findings_screen
from src.ui.flow_coverage_exclusion_screen import show_flow_coverage_exclusion_screen
from src.ui.history_screen import show_history_screen
from src.ui.picklist_csv_export import export_picklist_csvs
from src.ui.scoring_screens import show_adopt_adapt_screen, show_scoring_screen
from src.ui.threshold_screen import show_threshold_screen


class _AppUiWindowsMixin:
    """Open secondary windows (configuration, exclusions, scoring, history …)."""

    def _open_external_url(self, url: str) -> None:
        webbrowser.open_new_tab(url)

    def _configure_secondary_window(self, window: tk.Toplevel) -> None:
        window.resizable(True, True)
        try:
            window.wm_attributes("-toolwindow", False)
        except tk.TclError:
            pass
        if self.icon_image is not None:
            try:
                window.iconphoto(False, self.icon_image)
            except tk.TclError:
                pass

    def _show_configuration_screen(self) -> None:
        show_configuration_screen(self)

    def _show_exclusion_screen(self) -> None:
        show_exclusion_screen(self)

    def _show_flow_coverage_exclusion_screen(self) -> None:
        show_flow_coverage_exclusion_screen(self)

    def _show_debt_screen(self) -> None:
        from src.ui.debt_screen import show_debt_screen
        show_debt_screen(self)

    def _show_innovation_screen(self) -> None:
        from src.ui.innovation_screen import show_innovation_screen
        show_innovation_screen(self)

    def _show_data_dictionary_screen(self) -> None:
        show_data_dictionary_screen(self)

    def _show_findings_screen(self) -> None:
        show_findings_screen(self)

    def _menu_export_picklist_csvs(self) -> None:
        export_picklist_csvs(self)

    def _show_dashboard_designer_screen(self) -> None:
        show_dashboard_designer_screen(self)

    def _show_scoring_screen(self) -> None:
        show_scoring_screen(self)

    def _show_adopt_adapt_screen(self) -> None:
        show_adopt_adapt_screen(self)

    def _show_threshold_screen(self) -> None:
        show_threshold_screen(self)

    def _show_history_screen(self) -> None:
        show_history_screen(self)
