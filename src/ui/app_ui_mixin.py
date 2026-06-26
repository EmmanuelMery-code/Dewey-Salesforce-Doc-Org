"""Mixin — UI construction, menus and interaction helpers for :class:`Application`.

Covers:
* main window layout and the Documentation / discussion tabs;
* menu bar construction;
* path/folder/file picker widgets;
* secondary-window navigation (scoring, history, thresholds …);
* branding, macOS style fixes;
* log helpers and button-state management.
"""

from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Callable

import tkinter as tk

from src.ui import (
    cli_panel,
    discussion_panel,
)
from src.ui.config_window import show_configuration_screen
from src.ui.dashboard_designer_screen import show_dashboard_designer_screen
from src.ui.data_dictionary_screen import show_data_dictionary_screen
from src.ui.exclusion_screen import show_exclusion_screen
from src.ui.history_screen import show_history_screen
from src.ui.scoring_screens import show_adopt_adapt_screen, show_scoring_screen
from src.ui.threshold_screen import show_threshold_screen


class AppUiMixin:
    """Build and interact with all UI components."""

    # ================================================================== styles / branding

    def _setup_styles(self) -> None:
        style = ttk.Style(self)
        if sys.platform == "darwin":
            if "aqua" in style.theme_names():
                style.theme_use("aqua")
            style.configure("TCombobox", padding=2, borderwidth=1)
            style.map(
                "TCombobox",
                fieldbackground=[("readonly", "white"), ("!disabled", "white")],
                foreground=[("readonly", "black"), ("!disabled", "black")],
                background=[("readonly", "white")],
                selectbackground=[("readonly", "#007aff")],
                selectforeground=[("readonly", "white")],
            )
            style.configure("TEntry", padding=1)
            style.map(
                "TEntry",
                fieldbackground=[("!disabled", "white")],
                foreground=[("!disabled", "black")],
            )

    def _load_branding(self) -> None:
        image_path = self.app_dir / "image" / "Dewey.png"
        if not image_path.exists():
            return
        try:
            self.icon_image = tk.PhotoImage(file=str(image_path))
            self.iconphoto(True, self.icon_image)
            self.hero_image = tk.PhotoImage(file=str(image_path))
            width = max(1, self.hero_image.width() // 90)
            height = max(1, self.hero_image.height() // 90)
            factor = max(width, height)
            if factor > 1:
                self.hero_image = self.hero_image.subsample(factor, factor)
            self.hero_label.configure(image=self.hero_image)
        except tk.TclError:
            self._append_log(self._t("branding_error"))

    # ================================================================== main layout

    def _build_ui(self) -> None:
        self._build_menu_bar()
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        self.main_canvas = tk.Canvas(container, highlightthickness=0)
        self.main_scrollbar = ttk.Scrollbar(
            container, orient="vertical", command=self.main_canvas.yview
        )
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)
        self.main_scrollbar.pack(side="right", fill="y")
        self.main_canvas.pack(side="left", fill="both", expand=True)

        frame = ttk.Frame(self.main_canvas, padding=16)
        canvas_window = self.main_canvas.create_window((0, 0), window=frame, anchor="nw")

        def _on_frame_configure(_event) -> None:
            self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

        def _on_canvas_configure(event) -> None:
            self.main_canvas.itemconfigure(canvas_window, width=event.width)

        def _on_mousewheel(event) -> None:
            self.main_canvas.yview_scroll(int(-event.delta / 120), "units")

        frame.bind("<Configure>", _on_frame_configure)
        self.main_canvas.bind("<Configure>", _on_canvas_configure)
        self.main_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        header_frame = ttk.Frame(frame)
        header_frame.pack(fill="x")
        header_left = ttk.Frame(header_frame)
        header_left.pack(side="left", fill="x", expand=True)
        header_top = ttk.Frame(header_left)
        header_top.pack(fill="x")

        self.title_label = ttk.Label(header_top, font=("Segoe UI", 16, "bold"))
        self.title_label.pack(side="left", anchor="w")

        language_frame = ttk.Frame(header_top)
        language_frame.pack(side="right")
        self.language_title_label = ttk.Label(language_frame)
        self.language_title_label.pack(side="left", padx=(0, 8))
        self.language_combo = ttk.Combobox(
            language_frame,
            textvariable=self.language_label_var,
            state="readonly",
            width=12,
        )
        self.language_combo.pack(side="left")
        self.language_combo.bind("<<ComboboxSelected>>", self._on_language_changed)

        self.description_label = ttk.Label(header_left, wraplength=620, justify="left")
        self.description_label.pack(anchor="w", pady=(6, 8))
        self.hero_label = ttk.Label(header_frame)
        self.hero_label.pack(side="right", anchor="ne", padx=(16, 0))

        self.main_notebook = ttk.Notebook(frame)
        self.main_notebook.pack(fill="both", expand=True, pady=(12, 0))

        self.documentation_tab = ttk.Frame(self.main_notebook, padding=(0, 8))
        self.discussion_tab = ttk.Frame(self.main_notebook, padding=(0, 8))
        self.main_notebook.add(self.documentation_tab, text=self._t("tab_documentation"))
        self.main_notebook.add(self.discussion_tab, text=self._t("tab_discussion"))

        cli_panel.build_panel(self, self.documentation_tab)

        self.org_check_frame = ttk.LabelFrame(self.documentation_tab, padding=12)
        self.org_check_frame.pack(fill="x", pady=(0, 12))
        org_check_row = ttk.Frame(self.org_check_frame)
        org_check_row.pack(fill="x")
        self.org_check_type_label = ttk.Label(org_check_row, width=18)
        self.org_check_type_label.pack(side="left")
        self.org_check_combo = ttk.Combobox(
            org_check_row,
            textvariable=self.org_check_choice_var,
            values=self.ORG_CHECK_CHOICES,
            state="readonly",
            width=24,
        )
        self.org_check_combo.pack(side="left", padx=(0, 8))
        self.org_check_button = self._track_button(
            ttk.Button(org_check_row, command=self._run_org_check_excel)
        )
        self.org_check_button.pack(side="left")

        self.doc_frame = ttk.LabelFrame(self.documentation_tab, padding=12)
        self.doc_frame.pack(fill="x", pady=(0, 12))

        self.source_folder_widgets = self._folder_picker(
            self.doc_frame, self.source_var, self._choose_source, self._open_source_folder
        )
        self.output_folder_widgets = self._folder_picker(
            self.doc_frame, self.output_var, self._choose_output, self._open_output_folder
        )
        self.exclusion_file_widgets = self._file_picker(
            self.doc_frame,
            self.exclusion_file_var,
            self._choose_exclusion_file,
            self._open_exclusion_file,
        )

        self.pmd_frame = ttk.LabelFrame(self.doc_frame, padding=8)
        self.pmd_frame.pack(fill="x", pady=(2, 0))
        pmd_toggle_row = ttk.Frame(self.pmd_frame)
        pmd_toggle_row.pack(fill="x", pady=(0, 4))
        self.pmd_enabled_check = ttk.Checkbutton(
            pmd_toggle_row,
            variable=self.pmd_enabled_var,
            command=self._on_pmd_toggle,
        )
        self.pmd_enabled_check.pack(side="left")
        self.pmd_file_widgets = self._file_picker(
            self.pmd_frame,
            self.pmd_ruleset_var,
            self._choose_pmd_ruleset_file,
            self._open_pmd_ruleset_file,
        )
        self.analyzer_rules_file_widgets = self._file_picker(
            self.doc_frame,
            self.analyzer_rules_file_var,
            self._choose_analyzer_rules_file,
            self._open_analyzer_rules_file,
        )

        button_row = ttk.Frame(self.doc_frame)
        button_row.pack(fill="x", pady=(8, 0))
        self.generate_button = self._track_button(
            ttk.Button(button_row, command=self._start_generation)
        )
        self.generate_button.pack(side="left")
        self.open_index_button = self._track_button(
            ttk.Button(button_row, command=self._open_index)
        )
        self.open_index_button.pack(side="right")
        self.status_label = ttk.Label(button_row, textvariable=self.status_var)
        self.status_label.pack(side="left", padx=(16, 0))

        self.log_widget = scrolledtext.ScrolledText(
            self.documentation_tab, wrap="word", height=20
        )
        self.log_widget.pack(fill="both", expand=True)
        self.log_widget.configure(state="disabled")
        self.log_widget.configure(state="normal")
        self.log_widget.delete("1.0", "end")
        self.log_widget.configure(state="disabled")

        log_actions_row = ttk.Frame(self.documentation_tab)
        log_actions_row.pack(fill="x", pady=(4, 0))
        self.log_clear_button = ttk.Button(log_actions_row, command=self._clear_log)
        self.log_clear_button.pack(side="right")

        self._build_discussion_tab(self.discussion_tab)

    # ================================================================== discussion tab

    def _build_discussion_tab(self, parent: ttk.Frame) -> None:
        discussion_panel.build_panel(self, parent)

    def _append_discussion_line(self, text: str, tag: str = "system") -> None:
        discussion_panel.append_line(self, text, tag)

    def _clear_discussion_history(self) -> None:
        discussion_panel.clear_history(self)

    def _update_discussion_context_status(self) -> None:
        discussion_panel.update_context_status(self)

    def _send_discussion_message(self) -> None:
        discussion_panel.send_message(self)

    def _handle_discussion_reply(self, payload: dict[str, str]) -> None:
        discussion_panel.handle_reply(self, payload)

    def _handle_discussion_error(self, message: str) -> None:
        discussion_panel.handle_error(self, message)

    def _handle_discussion_info(self, payload: dict[str, object]) -> None:
        discussion_panel.handle_info(self, payload)

    # ================================================================== menu bar

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

    # ================================================================== secondary windows

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

    def _show_debt_screen(self) -> None:
        from src.ui.debt_screen import show_debt_screen
        show_debt_screen(self)

    def _show_innovation_screen(self) -> None:
        from src.ui.innovation_screen import show_innovation_screen
        show_innovation_screen(self)

    def _show_data_dictionary_screen(self) -> None:
        show_data_dictionary_screen(self)

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

    # ================================================================== path/file pickers

    def _folder_picker(
        self,
        parent: tk.Widget,
        variable: tk.StringVar,
        browse_command: Callable[[], None],
        open_command: Callable[[], None],
    ) -> dict[str, ttk.Widget]:
        return self._path_picker(parent, variable, browse_command, open_command)

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
    ) -> dict[str, ttk.Widget]:
        wrapper = ttk.Frame(parent)
        wrapper.pack(fill="x", pady=6)
        label = ttk.Label(wrapper, width=18)
        label.pack(side="left")
        entry = ttk.Entry(wrapper, textvariable=variable)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        browse_button = self._track_button(ttk.Button(wrapper, command=browse_command))
        browse_button.pack(side="left", padx=(0, 8))
        open_button = self._track_button(ttk.Button(wrapper, command=open_command))
        open_button.pack(side="left")
        return {"label": label, "browse_button": browse_button, "open_button": open_button}

    def _track_button(self, button: ttk.Button) -> ttk.Button:
        self.action_buttons.append(button)
        return button

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

    # ================================================================== PMD / index

    def _on_pmd_toggle(self) -> None:
        self._apply_pmd_state()
        self._save_settings()

    def _apply_pmd_state(self) -> None:
        state = "normal" if self.pmd_enabled_var.get() else "disabled"
        for key in ("label", "browse_button", "open_button"):
            self.pmd_file_widgets[key].configure(state=state)

    def _selected_pmd_ruleset_file(self) -> Path | None:
        value = self.pmd_ruleset_var.get().strip()
        if not value:
            return None
        path = Path(value)
        if not path.exists() or path.is_dir():
            messagebox.showerror(
                self._t("error_title"), self._t("directory_missing_to_open")
            )
            return None
        return path

    def _selected_exclusion_file(self) -> Path | None:
        value = self.exclusion_file_var.get().strip()
        if not value:
            return None
        path = Path(value)
        if not path.exists() or path.is_dir():
            messagebox.showerror(
                self._t("error_title"), self._t("directory_missing_to_open")
            )
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

    # ================================================================== lifecycle / log

    def _on_close(self) -> None:
        self._save_settings()
        self.destroy()

    def _set_buttons_state(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in self.action_buttons:
            button.configure(state=state)

    def _append_log(self, message: str) -> None:
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", str(message) + "\n")
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_widget.configure(state="normal")
        self.log_widget.delete("1.0", "end")
        self.log_widget.configure(state="disabled")
