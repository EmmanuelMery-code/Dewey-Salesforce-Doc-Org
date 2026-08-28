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

        # Laid out on a grid rather than a single packed row: there are now
        # enough columns to toggle that they would overflow the window width.
        field_toggles = (
            ("data_dictionary_comment_label", self.include_comment_var),
            ("data_dictionary_piloted_by_label", self.include_piloted_by_var),
            ("data_dictionary_status_label", self.include_status_var),
            ("data_dictionary_squad_label", self.include_squad_var),
            ("data_dictionary_squad_consumer_label", self.include_squad_consumer_var),
            ("data_dictionary_field_comment_label", self.include_field_comment_var),
            (
                "data_dictionary_field_piloted_by_label",
                self.include_field_piloted_by_var,
            ),
            (
                "data_dictionary_field_automation_label",
                self.include_field_automation_var,
            ),
        )
        toggles_per_row = 4
        for column in range(toggles_per_row):
            fields_frame.columnconfigure(column, weight=1, uniform="dd_toggles")
        for index, (label_key, variable) in enumerate(field_toggles):
            ttk.Checkbutton(
                fields_frame,
                text=self.app._t(label_key),
                variable=variable,
            ).grid(
                row=index // toggles_per_row,
                column=index % toggles_per_row,
                sticky="w",
                padx=(0, theme.SPACE_MD),
                pady=theme.SPACE_XS,
            )

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

        # Objects & extra-info area: a single 3-column grid shared by the
        # selection row (row 0) and the extra-info row (row 1). Using one
        # grid with a "uniform" group on the outer columns keeps the object
        # column and the fields column aligned across both rows, instead of
        # each row's panels drifting apart with their own natural width.
        panels_container = ttk.Frame(main_frame)
        panels_container.pack(fill="both", expand=True, pady=(0, theme.SPACE_MD))
        panels_container.columnconfigure(0, weight=1, uniform="dd_panels")
        panels_container.columnconfigure(2, weight=1, uniform="dd_panels")
        panels_container.rowconfigure(0, weight=1)
        panels_container.rowconfigure(1, weight=1)

        # Left side: Available
        available_frame = ttk.LabelFrame(panels_container, text="Objets disponibles", padding=theme.SPACE_MD)
        available_frame.grid(row=0, column=0, sticky="nsew", pady=(0, theme.SPACE_MD))

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
        button_frame = ttk.Frame(panels_container, padding=theme.SPACE_MD)
        button_frame.grid(row=0, column=1, sticky="ns", pady=(0, theme.SPACE_MD))
        
        ttk.Label(button_frame, text="").pack(expand=True) # Spacer
        ttk.Button(button_frame, text=" Ajouter > ", command=self._move_to_selected).pack(pady=theme.SPACE_SM)
        ttk.Button(button_frame, text=" < Retirer ", command=self._move_to_available).pack(pady=theme.SPACE_SM)
        ttk.Label(button_frame, text="").pack(expand=True) # Spacer

        # Right side: Selected (with extra visualization columns, sortable
        # by clicking a header and filterable across all its columns)
        selected_frame = ttk.LabelFrame(panels_container, text="Objets sélectionnés", padding=theme.SPACE_MD)
        selected_frame.grid(row=0, column=2, sticky="nsew", pady=(0, theme.SPACE_MD))

        selected_filter_row = ttk.Frame(selected_frame)
        selected_filter_row.pack(fill="x", pady=(0, theme.SPACE_SM))
        ttk.Label(selected_filter_row, text=self.app._t("exclusions_filter_label")).pack(
            side="left", padx=(0, theme.SPACE_SM)
        )
        self.selected_filter_var = tk.StringVar()
        self.selected_filter_var.trace_add("write", lambda *args: self._apply_selected_filter())
        ttk.Entry(selected_filter_row, textvariable=self.selected_filter_var).pack(
            side="left", fill="x", expand=True
        )

        # Grid (rather than pack) so the horizontal scrollbar can sit under
        # the tree while the vertical one stays on its right.
        list_container_right = ttk.Frame(selected_frame)
        list_container_right.pack(fill="both", expand=True)
        list_container_right.rowconfigure(0, weight=1)
        list_container_right.columnconfigure(0, weight=1)

        self._SELECTED_COLUMN_LABELS = {
            "object": "Objet",
            "piloted_by": self.app._t("data_dictionary_piloted_by_label"),
            "status": self.app._t("data_dictionary_status_label"),
            "squad": self.app._t("data_dictionary_squad_label"),
            "squad_consumer": self.app._t("data_dictionary_squad_consumer_label"),
        }
        self.selected_listbox = ttk.Treeview(
            list_container_right,
            columns=tuple(self._SELECTED_COLUMN_LABELS.keys()),
            show="headings",
            selectmode="extended",
            height=12,
        )
        # ``minwidth`` matching ``width`` plus ``stretch=False`` keeps ttk from
        # squeezing the columns into the available space, which is what makes
        # the horizontal scrollbar below actually engage. The last column stays
        # stretchable so a widened window fills the gap instead of showing a
        # blank strip on the right.
        last_column = list(self._SELECTED_COLUMN_LABELS)[-1]
        for column in self._SELECTED_COLUMN_LABELS:
            width = 130 if column == "object" else 95
            self.selected_listbox.column(
                column,
                width=width,
                minwidth=width,
                stretch=(column == last_column),
                anchor="w",
            )
        self._update_selected_headings()
        # Background colors reflecting how many of the object's fields have
        # a "Piloté par" value: all filled -> green, some -> yellow, none -> red.
        self.selected_listbox.tag_configure("piloted_all", background="#d9f2d9")
        self.selected_listbox.tag_configure("piloted_some", background="#fdf3cf")
        self.selected_listbox.tag_configure("piloted_none", background="#f8d7d7")
        selected_scroll = ttk.Scrollbar(list_container_right, orient="vertical", command=self.selected_listbox.yview)
        selected_hscroll = ttk.Scrollbar(
            list_container_right, orient="horizontal", command=self.selected_listbox.xview
        )
        self.selected_listbox.configure(
            yscrollcommand=selected_scroll.set, xscrollcommand=selected_hscroll.set
        )
        self.selected_listbox.grid(row=0, column=0, sticky="nsew")
        selected_scroll.grid(row=0, column=1, sticky="ns")
        selected_hscroll.grid(row=1, column=0, sticky="ew")

        self.available_listbox.bind("<<ListboxSelect>>", self._on_object_select)
        self.selected_listbox.bind("<<TreeviewSelect>>", self._on_selected_tree_select)

        # Left: object comment panel, in the same grid column as
        # "Objets disponibles" so both share one width.
        self.comment_label_var = tk.StringVar(value=self.app._t("data_dictionary_comment_placeholder"))
        comment_frame = ttk.LabelFrame(
            panels_container, text=self.app._t("data_dictionary_comment_title"), padding=theme.SPACE_MD
        )
        comment_frame.grid(row=1, column=0, sticky="nsew")

        # Wrapped so this one-line hint does not dictate the panel width.
        ttk.Label(
            comment_frame,
            textvariable=self.comment_label_var,
            font=theme.FONT_SMALL_ITALIC,
            wraplength=320,
            justify="left",
        ).pack(anchor="w", pady=(0, theme.SPACE_SM))

        ttk.Label(comment_frame, text=self.app._t("data_dictionary_comment_label")).pack(anchor="w")
        comment_text_container = ttk.Frame(comment_frame)
        comment_text_container.pack(fill="x", pady=(0, theme.SPACE_SM))
        # An explicit narrow width keeps tk.Text's 80-character default from
        # dictating this panel's natural width; it stretches via fill="x".
        self.comment_text = tk.Text(
            comment_text_container, height=4, width=20, wrap="word", state="disabled"
        )
        comment_text_scroll = ttk.Scrollbar(comment_text_container, orient="vertical", command=self.comment_text.yview)
        self.comment_text.configure(yscrollcommand=comment_text_scroll.set)
        self.comment_text.pack(side="left", fill="x", expand=True)
        comment_text_scroll.pack(side="right", fill="y")

        # Piloté par / Status on the first row, with Squad Responsable /
        # Squad Consommatrice right below their respective column so the
        # panel stays as narrow as "Objets disponibles" instead of
        # spreading 4 fields on a single row.
        extra_fields_grid = ttk.Frame(comment_frame)
        extra_fields_grid.pack(fill="x", pady=(0, theme.SPACE_SM))
        extra_fields_grid.columnconfigure(0, weight=1)
        extra_fields_grid.columnconfigure(1, weight=1)

        piloted_by_frame = ttk.Frame(extra_fields_grid)
        piloted_by_frame.grid(row=0, column=0, sticky="ew", padx=(0, theme.SPACE_MD), pady=(0, theme.SPACE_SM))
        ttk.Label(piloted_by_frame, text=self.app._t("data_dictionary_piloted_by_label")).pack(anchor="w")
        self.piloted_by_var = tk.StringVar()
        self.piloted_by_entry = ttk.Entry(piloted_by_frame, textvariable=self.piloted_by_var, state="disabled")
        self.piloted_by_entry.pack(fill="x")

        status_frame = ttk.Frame(extra_fields_grid)
        status_frame.grid(row=0, column=1, sticky="ew", pady=(0, theme.SPACE_SM))
        ttk.Label(status_frame, text=self.app._t("data_dictionary_status_label")).pack(anchor="w")
        self.status_var = tk.StringVar(value=self.STATUS_OPTIONS[0])
        self.status_combo = ttk.Combobox(
            status_frame,
            textvariable=self.status_var,
            values=self.STATUS_OPTIONS,
            state="disabled",
        )
        self.status_combo.pack(fill="x")

        squad_frame = ttk.Frame(extra_fields_grid)
        squad_frame.grid(row=1, column=0, sticky="ew", padx=(0, theme.SPACE_MD))
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

        squad_consumer_frame = ttk.Frame(extra_fields_grid)
        squad_consumer_frame.grid(row=1, column=1, sticky="ew")
        ttk.Label(
            squad_consumer_frame, text=self.app._t("data_dictionary_squad_consumer_label")
        ).pack(anchor="w")
        self.squad_consumer_var = tk.StringVar()
        squad_consumer_validate = (self.window.register(self._validate_squad_input), "%P")
        self.squad_consumer_entry = ttk.Entry(
            squad_consumer_frame,
            textvariable=self.squad_consumer_var,
            state="disabled",
            validate="key",
            validatecommand=squad_consumer_validate,
        )
        self.squad_consumer_entry.pack(fill="x")

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

        # Middle: bridges the object-level and field-level panels with the
        # "copy Piloté par down to the fields" action.
        copy_button_frame = ttk.Frame(panels_container, padding=theme.SPACE_MD)
        copy_button_frame.grid(row=1, column=1, sticky="ns")

        ttk.Label(copy_button_frame, text="").pack(expand=True)  # Spacer
        ttk.Button(
            copy_button_frame,
            text=self.app._t("data_dictionary_copy_piloted_by_button"),
            command=self._copy_object_piloted_by_to_fields,
        ).pack(pady=theme.SPACE_SM)
        ttk.Label(copy_button_frame, text="").pack(expand=True)  # Spacer

        # Right: per-field extra-info panel, in the same grid column as
        # "Objets selectionnes" so both share one width.
        self.fields_comment_label_var = tk.StringVar(
            value=self.app._t("data_dictionary_fields_comment_placeholder")
        )
        fields_comment_frame = ttk.LabelFrame(
            panels_container,
            text=self.app._t("data_dictionary_fields_comment_title"),
            padding=theme.SPACE_MD,
        )
        fields_comment_frame.grid(row=1, column=2, sticky="nsew")

        fields_list_container = ttk.Frame(fields_comment_frame)
        fields_list_container.pack(fill="both", expand=True, pady=(0, theme.SPACE_SM))

        self.fields_tree = ttk.Treeview(
            fields_list_container,
            columns=("label", "api_name"),
            show="headings",
            selectmode="browse",
            height=6,
        )
        self.fields_tree.heading("label", text=self.app._t("data_dictionary_fields_column_label"))
        self.fields_tree.heading("api_name", text=self.app._t("data_dictionary_fields_column_api_name"))
        self.fields_tree.column("label", width=140, anchor="w")
        self.fields_tree.column("api_name", width=140, anchor="w")
        fields_tree_scroll = ttk.Scrollbar(
            fields_list_container, orient="vertical", command=self.fields_tree.yview
        )
        self.fields_tree.configure(yscrollcommand=fields_tree_scroll.set)
        self.fields_tree.pack(side="left", fill="both", expand=True)
        fields_tree_scroll.pack(side="right", fill="y")
        self.fields_tree.bind("<<TreeviewSelect>>", self._on_field_select)

        ttk.Label(
            fields_comment_frame,
            textvariable=self.fields_comment_label_var,
            font=theme.FONT_SMALL_ITALIC,
            wraplength=320,
            justify="left",
        ).pack(anchor="w", pady=(0, theme.SPACE_SM))

        field_extra_row = ttk.Frame(fields_comment_frame)
        field_extra_row.pack(fill="x", pady=(0, theme.SPACE_SM))

        field_comment_entry_frame = ttk.Frame(field_extra_row)
        field_comment_entry_frame.pack(side="left", fill="x", expand=True, padx=(0, theme.SPACE_MD))
        ttk.Label(field_comment_entry_frame, text=self.app._t("data_dictionary_comment_label")).pack(anchor="w")
        self.field_comment_var = tk.StringVar()
        self.field_comment_entry = ttk.Entry(
            field_comment_entry_frame, textvariable=self.field_comment_var, state="disabled"
        )
        self.field_comment_entry.pack(fill="x")

        field_piloted_by_entry_frame = ttk.Frame(field_extra_row)
        field_piloted_by_entry_frame.pack(side="left", fill="x", expand=True)
        ttk.Label(
            field_piloted_by_entry_frame, text=self.app._t("data_dictionary_piloted_by_label")
        ).pack(anchor="w")
        self.field_piloted_by_var = tk.StringVar()
        self.field_piloted_by_entry = ttk.Entry(
            field_piloted_by_entry_frame, textvariable=self.field_piloted_by_var, state="disabled"
        )
        self.field_piloted_by_entry.pack(fill="x")

        field_comment_buttons_row = ttk.Frame(fields_comment_frame)
        field_comment_buttons_row.pack(fill="x", pady=(theme.SPACE_SM, 0))

        self.save_field_comment_btn = ttk.Button(
            field_comment_buttons_row,
            text=self.app._t("data_dictionary_comment_save"),
            command=self._save_field_comment,
            state="disabled",
        )
        self.save_field_comment_btn.pack(side="left")

        self.delete_field_comment_btn = ttk.Button(
            field_comment_buttons_row,
            text=self.app._t("data_dictionary_comment_delete"),
            command=self._delete_field_comment,
            state="disabled",
        )
        self.delete_field_comment_btn.pack(side="left", padx=(theme.SPACE_SM, 0))

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
            text=self.app._t("data_dictionary_import_fields_csv_button"),
            command=self._import_fields_csv,
        ).pack(side="right", padx=(0, theme.SPACE_SM))

        ttk.Button(
            footer_frame,
            text=self.app._t("data_dictionary_export_fields_csv_button"),
            command=self._export_fields_csv,
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
