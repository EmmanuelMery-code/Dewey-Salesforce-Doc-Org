"""UI construction for the Data Dictionary screen."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.ui import theme


class _DataDictionaryUiBuilderMixin:
    """Builds every widget of the Data Dictionary window.

    Expects the concrete screen class to also provide the command callbacks
    referenced below (``_move_to_selected``, ``_save_comment``, ``_generate``,
    the CSV import/export handlers, ...) plus the state variables created in
    ``__init__`` (``html_var``, ``include_*_var``, ``STATUS_OPTIONS``, ...).
    """

    def _build_ui(self) -> None:
        scroll_container = ttk.Frame(self.window)
        scroll_container.pack(fill="both", expand=True)

        canvas = tk.Canvas(scroll_container, highlightthickness=0)
        vertical_scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vertical_scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        vertical_scrollbar.pack(side="right", fill="y")

        main_frame = ttk.Frame(canvas, padding=theme.SPACE_LG)
        main_frame_id = canvas.create_window((0, 0), window=main_frame, anchor="nw")

        def _sync_scrollregion(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _sync_frame_width(event: tk.Event) -> None:
            canvas.itemconfigure(main_frame_id, width=event.width)

        main_frame.bind("<Configure>", _sync_scrollregion)
        canvas.bind("<Configure>", _sync_frame_width)

        def _on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        # Header
        ttk.Label(
            main_frame,
            text=self.app._t("data_dictionary_title"),
            style=theme.TITLE_LABEL,
        ).pack(anchor="w", pady=(0, theme.SPACE_MD))

        # Formats
        format_frame = ttk.LabelFrame(main_frame, text=self.app._t("data_dictionary_formats"), padding=theme.SPACE_MD)
        format_frame.pack(fill="x", pady=(0, theme.SPACE_MD))
        
        ttk.Checkbutton(format_frame, text="HTML", variable=self.html_var).pack(side="left", padx=theme.SPACE_MD)
        ttk.Checkbutton(format_frame, text="Word", variable=self.word_var).pack(side="left", padx=theme.SPACE_MD)
        ttk.Checkbutton(format_frame, text="Excel", variable=self.excel_var).pack(side="left", padx=theme.SPACE_MD)

        # Fields to include in the generated dictionary
        fields_frame = ttk.LabelFrame(
            main_frame, text=self.app._t("data_dictionary_fields_title"), padding=theme.SPACE_MD
        )
        fields_frame.pack(fill="x", pady=(0, theme.SPACE_MD))

        ttk.Checkbutton(
            fields_frame,
            text=self.app._t("data_dictionary_comment_label"),
            variable=self.include_comment_var,
        ).pack(side="left", padx=theme.SPACE_MD)
        ttk.Checkbutton(
            fields_frame,
            text=self.app._t("data_dictionary_piloted_by_label"),
            variable=self.include_piloted_by_var,
        ).pack(side="left", padx=theme.SPACE_MD)
        ttk.Checkbutton(
            fields_frame,
            text=self.app._t("data_dictionary_status_label"),
            variable=self.include_status_var,
        ).pack(side="left", padx=theme.SPACE_MD)
        ttk.Checkbutton(
            fields_frame,
            text=self.app._t("data_dictionary_squad_label"),
            variable=self.include_squad_var,
        ).pack(side="left", padx=theme.SPACE_MD)

        # Separate, clearly distinct option controlling whether the
        # "Commentaire Dewey" column concatenates the metadata Description
        # or only shows the user-entered comment on its own.
        concat_frame = ttk.LabelFrame(
            main_frame, text=self.app._t("data_dictionary_concat_section_title"), padding=theme.SPACE_MD
        )
        concat_frame.pack(fill="x", pady=(0, theme.SPACE_MD))

        ttk.Checkbutton(
            concat_frame,
            text=self.app._t("data_dictionary_concat_description_label"),
            variable=self.concat_description_var,
        ).pack(side="left", padx=theme.SPACE_MD)

        # Objects selection area
        selection_container = ttk.Frame(main_frame)
        selection_container.pack(fill="both", expand=True, pady=(0, theme.SPACE_MD))

        # Left side: Available
        available_frame = ttk.LabelFrame(selection_container, text="Objets disponibles", padding=theme.SPACE_MD)
        available_frame.pack(side="left", fill="both", expand=True)

        filter_row = ttk.Frame(available_frame)
        filter_row.pack(fill="x", pady=(0, theme.SPACE_SM))
        ttk.Label(filter_row, text=self.app._t("exclusions_filter_label")).pack(side="left", padx=(0, theme.SPACE_SM))
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *args: self._apply_filter())
        ttk.Entry(filter_row, textvariable=self.filter_var).pack(side="left", fill="x", expand=True)

        list_container_left = ttk.Frame(available_frame)
        list_container_left.pack(fill="both", expand=True)

        self.available_listbox = tk.Listbox(
            list_container_left, selectmode="extended", exportselection=False, height=12
        )
        available_scroll = ttk.Scrollbar(list_container_left, orient="vertical", command=self.available_listbox.yview)
        self.available_listbox.configure(yscrollcommand=available_scroll.set)
        self.available_listbox.pack(side="left", fill="both", expand=True)
        available_scroll.pack(side="right", fill="y")

        # Center: Buttons
        button_frame = ttk.Frame(selection_container, padding=theme.SPACE_MD)
        button_frame.pack(side="left", fill="y", expand=False)
        
        ttk.Label(button_frame, text="").pack(expand=True) # Spacer
        ttk.Button(button_frame, text=" Ajouter > ", command=self._move_to_selected).pack(pady=theme.SPACE_SM)
        ttk.Button(button_frame, text=" < Retirer ", command=self._move_to_available).pack(pady=theme.SPACE_SM)
        ttk.Label(button_frame, text="").pack(expand=True) # Spacer

        # Right side: Selected
        selected_frame = ttk.LabelFrame(selection_container, text="Objets sélectionnés", padding=theme.SPACE_MD)
        selected_frame.pack(side="left", fill="both", expand=True)

        list_container_right = ttk.Frame(selected_frame)
        list_container_right.pack(fill="both", expand=True)

        self.selected_listbox = tk.Listbox(
            list_container_right, selectmode="extended", exportselection=False, height=12
        )
        selected_scroll = ttk.Scrollbar(list_container_right, orient="vertical", command=self.selected_listbox.yview)
        self.selected_listbox.configure(yscrollcommand=selected_scroll.set)
        self.selected_listbox.pack(side="left", fill="both", expand=True)
        selected_scroll.pack(side="right", fill="y")

        self.available_listbox.bind("<<ListboxSelect>>", self._on_object_select)
        self.selected_listbox.bind("<<ListboxSelect>>", self._on_object_select)

        # Object comment panel
        self.comment_label_var = tk.StringVar(value=self.app._t("data_dictionary_comment_placeholder"))
        comment_frame = ttk.LabelFrame(main_frame, text=self.app._t("data_dictionary_comment_title"), padding=theme.SPACE_MD)
        comment_frame.pack(fill="x", pady=(0, theme.SPACE_MD))

        ttk.Label(comment_frame, textvariable=self.comment_label_var, font=theme.FONT_SMALL_ITALIC).pack(
            anchor="w", pady=(0, theme.SPACE_SM)
        )

        ttk.Label(comment_frame, text=self.app._t("data_dictionary_comment_label")).pack(anchor="w")
        comment_text_container = ttk.Frame(comment_frame)
        comment_text_container.pack(fill="x", pady=(0, theme.SPACE_SM))
        self.comment_text = tk.Text(comment_text_container, height=4, wrap="word", state="disabled")
        comment_text_scroll = ttk.Scrollbar(comment_text_container, orient="vertical", command=self.comment_text.yview)
        self.comment_text.configure(yscrollcommand=comment_text_scroll.set)
        self.comment_text.pack(side="left", fill="x", expand=True)
        comment_text_scroll.pack(side="right", fill="y")

        extra_fields_row = ttk.Frame(comment_frame)
        extra_fields_row.pack(fill="x", pady=(0, theme.SPACE_SM))

        piloted_by_frame = ttk.Frame(extra_fields_row)
        piloted_by_frame.pack(side="left", fill="x", expand=True, padx=(0, theme.SPACE_MD))
        ttk.Label(piloted_by_frame, text=self.app._t("data_dictionary_piloted_by_label")).pack(anchor="w")
        self.piloted_by_var = tk.StringVar()
        self.piloted_by_entry = ttk.Entry(piloted_by_frame, textvariable=self.piloted_by_var, state="disabled")
        self.piloted_by_entry.pack(fill="x")

        status_frame = ttk.Frame(extra_fields_row)
        status_frame.pack(side="left", fill="x", expand=True, padx=(0, theme.SPACE_MD))
        ttk.Label(status_frame, text=self.app._t("data_dictionary_status_label")).pack(anchor="w")
        self.status_var = tk.StringVar(value=self.STATUS_OPTIONS[0])
        self.status_combo = ttk.Combobox(
            status_frame,
            textvariable=self.status_var,
            values=self.STATUS_OPTIONS,
            state="disabled",
        )
        self.status_combo.pack(fill="x")

        squad_frame = ttk.Frame(extra_fields_row)
        squad_frame.pack(side="left", fill="x", expand=True)
        ttk.Label(squad_frame, text=self.app._t("data_dictionary_squad_label")).pack(anchor="w")
        self.squad_var = tk.StringVar()
        squad_validate = (self.window.register(self._validate_squad_input), "%P")
        self.squad_entry = ttk.Entry(
            squad_frame,
            textvariable=self.squad_var,
            state="disabled",
            validate="key",
            validatecommand=squad_validate,
        )
        self.squad_entry.pack(fill="x")

        comment_buttons_row = ttk.Frame(comment_frame)
        comment_buttons_row.pack(fill="x", pady=(theme.SPACE_SM, 0))

        self.save_comment_btn = ttk.Button(
            comment_buttons_row,
            text=self.app._t("data_dictionary_comment_save"),
            command=self._save_comment,
            state="disabled",
        )
        self.save_comment_btn.pack(side="left")

        self.delete_comment_btn = ttk.Button(
            comment_buttons_row,
            text=self.app._t("data_dictionary_comment_delete"),
            command=self._delete_comment,
            state="disabled",
        )
        self.delete_comment_btn.pack(side="left", padx=(theme.SPACE_SM, 0))

        # Footer
        footer_frame = ttk.Frame(main_frame, padding=(0, theme.SPACE_MD, 0, 0))
        footer_frame.pack(fill="x")
        
        ttk.Label(footer_frame, text=self.app._t("data_dictionary_naming_convention"), font=theme.FONT_SMALL_ITALIC).pack(side="left")
        
        ttk.Button(
            footer_frame,
            text=self.app._t("configuration_close"),
            command=self.window.destroy,
        ).pack(side="right")

        ttk.Button(
            footer_frame,
            text=self.app._t("data_dictionary_picklist_csv_button"),
            command=self._export_picklist_csv,
        ).pack(side="right", padx=(0, theme.SPACE_SM))

        ttk.Button(
            footer_frame,
            text=self.app._t("data_dictionary_import_csv_button"),
            command=self._import_csv,
        ).pack(side="right", padx=(0, theme.SPACE_SM))

        ttk.Button(
            footer_frame,
            text=self.app._t("data_dictionary_export_csv_button"),
            command=self._export_csv,
        ).pack(side="right", padx=(0, theme.SPACE_SM))

        ttk.Button(
            footer_frame,
            text=self.app._t("data_dictionary_generate"),
            command=self._generate,
            style=theme.PRIMARY_BUTTON,
        ).pack(side="right", padx=(0, theme.SPACE_SM))
