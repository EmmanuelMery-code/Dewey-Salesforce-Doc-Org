"""Mixin — UI construction, menus and interaction helpers for :class:`Application`.

Covers:
* main window layout and the Documentation / discussion tabs;
* menu bar construction (:mod:`src.ui.app_ui_menu_mixin`);
* path/folder/file picker widgets (:mod:`src.ui.app_ui_pickers_mixin`);
* folder clearing / folder policies (:mod:`src.ui.app_ui_folder_policy_mixin`);
* secondary-window navigation (:mod:`src.ui.app_ui_windows_mixin`);
* branding, macOS style fixes;
* log helpers and button-state management.
"""

from __future__ import annotations

import sys
from tkinter import scrolledtext, ttk

import tkinter as tk

from src.ui import (
    cli_panel,
    discussion_panel,
)
from src.ui import theme
from src.ui.app_ui_folder_policy_mixin import _AppUiFolderPolicyMixin
from src.ui.app_ui_menu_mixin import _AppUiMenuMixin
from src.ui.app_ui_pickers_mixin import _AppUiPickersMixin
from src.ui.app_ui_windows_mixin import _AppUiWindowsMixin


class AppUiMixin(
    _AppUiMenuMixin,
    _AppUiWindowsMixin,
    _AppUiPickersMixin,
    _AppUiFolderPolicyMixin,
):
    """Build and interact with all UI components."""

    # ================================================================== styles / branding

    def _setup_styles(self) -> None:
        style = ttk.Style(self)
        theme.register_styles(style)
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

        frame = ttk.Frame(self.main_canvas, padding=theme.SPACE_LG)
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

        self.title_label = ttk.Label(header_top, style=theme.TITLE_LABEL)
        self.title_label.pack(side="left", anchor="w")

        language_frame = ttk.Frame(header_top)
        language_frame.pack(side="right")
        self.language_title_label = ttk.Label(language_frame)
        self.language_title_label.pack(side="left", padx=(0, theme.SPACE_SM))
        self.language_combo = ttk.Combobox(
            language_frame,
            textvariable=self.language_label_var,
            state="readonly",
            width=12,
        )
        self.language_combo.pack(side="left")
        self.language_combo.bind("<<ComboboxSelected>>", self._on_language_changed)

        self.description_label = ttk.Label(header_left, wraplength=620, justify="left")
        self.description_label.pack(anchor="w", pady=(theme.SPACE_XS, theme.SPACE_SM))
        self.hero_label = ttk.Label(header_frame)
        self.hero_label.pack(side="right", anchor="ne", padx=(theme.SPACE_LG, 0))

        self.main_notebook = ttk.Notebook(frame)
        self.main_notebook.pack(fill="both", expand=True, pady=(theme.SPACE_MD, 0))

        self.documentation_tab = ttk.Frame(self.main_notebook, padding=(0, theme.SPACE_SM))
        self.discussion_tab = ttk.Frame(self.main_notebook, padding=(0, theme.SPACE_SM))
        self.main_notebook.add(self.documentation_tab, text=self._t("tab_documentation"))
        self.main_notebook.add(self.discussion_tab, text=self._t("tab_discussion"))

        cli_panel.build_panel(self, self.documentation_tab)

        self.org_check_frame = ttk.LabelFrame(self.documentation_tab, padding=theme.SPACE_MD)
        self.org_check_frame.pack(fill="x", pady=(0, theme.SPACE_MD))
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
        self.org_check_combo.pack(side="left", padx=(0, theme.SPACE_SM))
        self.org_check_button = self._track_button(
            ttk.Button(org_check_row, command=self._run_org_check_excel)
        )
        self.org_check_button.pack(side="left")

        self.doc_frame = ttk.LabelFrame(self.documentation_tab, padding=theme.SPACE_MD)
        self.doc_frame.pack(fill="x", pady=(0, theme.SPACE_MD))

        self.source_folder_widgets = self._folder_picker(
            self.doc_frame,
            self.source_var,
            self._choose_source,
            self._open_source_folder,
            self._clear_source_folder,
        )
        self.output_folder_widgets = self._folder_picker(
            self.doc_frame,
            self.output_var,
            self._choose_output,
            self._open_output_folder,
            self._clear_output_folder,
        )
        self.exclusion_file_widgets = self._file_picker(
            self.doc_frame,
            self.exclusion_file_var,
            self._choose_exclusion_file,
            self._open_exclusion_file,
        )

        self.pmd_frame = ttk.LabelFrame(self.doc_frame, padding=theme.SPACE_SM)
        self.pmd_frame.pack(fill="x", pady=(2, 0))
        pmd_toggle_row = ttk.Frame(self.pmd_frame)
        pmd_toggle_row.pack(fill="x", pady=(0, theme.SPACE_XS))
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
        button_row.pack(fill="x", pady=(theme.SPACE_SM, 0))
        self.generate_button = self._track_button(
            ttk.Button(button_row, style=theme.PRIMARY_BUTTON, command=self._start_generation)
        )
        self.generate_button.pack(side="left")
        self.open_index_button = self._track_button(
            ttk.Button(button_row, command=self._open_index)
        )
        self.open_index_button.pack(side="right")
        self.status_label = ttk.Label(button_row, textvariable=self.status_var)
        self.status_label.pack(side="left", padx=(theme.SPACE_LG, 0))

        self.log_widget = scrolledtext.ScrolledText(
            self.documentation_tab, wrap="word", height=20
        )
        self.log_widget.pack(fill="both", expand=True)
        self.log_widget.configure(state="disabled")
        self.log_widget.configure(state="normal")
        self.log_widget.delete("1.0", "end")
        self.log_widget.configure(state="disabled")

        log_actions_row = ttk.Frame(self.documentation_tab)
        log_actions_row.pack(fill="x", pady=(theme.SPACE_XS, 0))
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

    # ================================================================== misc helpers

    def _track_button(self, button: ttk.Button) -> ttk.Button:
        self.action_buttons.append(button)
        return button

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
