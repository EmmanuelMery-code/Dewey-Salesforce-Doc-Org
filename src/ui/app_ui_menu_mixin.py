"""Mixin — menu bar construction for :class:`~src.ui.app_ui_mixin.AppUiMixin`.

Extracted from ``app_ui_mixin.py`` to keep files under the project's
500-line convention.
"""

from __future__ import annotations

import tkinter as tk


class _AppUiMenuMixin:
    """Build the application menu bar."""

    def _build_menu_bar(self) -> None:
        menu_bar = tk.Menu(self)

        documentation_menu = tk.Menu(menu_bar, tearoff=False)
        documentation_menu.add_command(
            label=self._t("menu_generate_documentation"),
            command=self._menu_generate_documentation,
        )
        documentation_menu.add_separator()
        documentation_menu.add_command(
            label=self._t("menu_generate_excels"),
            command=self._menu_generate_excels,
        )
        documentation_menu.add_command(
            label=self._t("menu_generate_html"),
            command=self._menu_generate_html,
        )
        documentation_menu.add_command(
            label=self._t("menu_generate_word"),
            command=self._menu_generate_word,
        )
        documentation_menu.add_separator()
        documentation_menu.add_command(
            label=self._t("menu_create_data_dictionary"),
            command=self._show_data_dictionary_screen,
        )
        documentation_menu.add_command(
            label=self._t("menu_export_picklist_csvs"),
            command=self._menu_export_picklist_csvs,
        )
        documentation_menu.add_command(
            label=self._t("menu_calculate_coverage"),
            command=self._menu_calculate_coverage,
        )
        documentation_menu.add_command(
            label=self._t("menu_design_dashboard"),
            command=self._show_dashboard_designer_screen,
        )
        menu_bar.add_cascade(label=self._t("documentation_menu"), menu=documentation_menu)

        download_menu = tk.Menu(menu_bar, tearoff=False)
        download_menu.add_command(
            label=self._t("download_sf_cli"),
            command=lambda: self._open_external_url(self.SF_CLI_DOWNLOAD_URL),
        )
        download_menu.add_command(
            label=self._t("download_pmd"),
            command=lambda: self._open_external_url(self.PMD_DOWNLOAD_URL),
        )
        download_menu.add_command(
            label=self._t("ORG CHECK app exchange"),
            command=lambda: self._open_external_url(self.ORG_CHECK_APP_URL),
        )
        download_menu.add_command(
            label=self._t("ORG CHECK github"),
            command=lambda: self._open_external_url(self.ORG_CHECK_GITHUB_URL),
        )
        menu_bar.add_cascade(label=self._t("download_menu"), menu=download_menu)

        configuration_menu = tk.Menu(menu_bar, tearoff=False)
        configuration_menu.add_command(
            label=self._t("show_configuration_screen"),
            command=self._show_configuration_screen,
        )
        configuration_menu.add_command(
            label=self._t("manage_exclusions_menu_item"),
            command=self._show_exclusion_screen,
        )
        configuration_menu.add_command(
            label=self._t("manage_debt_menu_item"),
            command=self._show_debt_screen,
        )
        configuration_menu.add_command(
            label=self._t("manage_innovation_menu_item"),
            command=self._show_innovation_screen,
        )
        configuration_menu.add_command(
            label=self._t("view_scoring_menu_item"),
            command=self._show_scoring_screen,
        )
        configuration_menu.add_command(
            label=self._t("view_adopt_adapt_menu_item"),
            command=self._show_adopt_adapt_screen,
        )
        configuration_menu.add_command(
            label=self._t("view_thresholds_menu_item"),
            command=self._show_threshold_screen,
        )
        menu_bar.add_cascade(label=self._t("configuration_menu"), menu=configuration_menu)

        dashboard_menu = tk.Menu(menu_bar, tearoff=False)
        dashboard_menu.add_command(
            label=self._t("history_menu_item"),
            command=self._show_history_screen,
        )
        menu_bar.add_cascade(label=self._t("dashboard_menu"), menu=dashboard_menu)

        self.config(menu=menu_bar)
        self.menu_bar = menu_bar
