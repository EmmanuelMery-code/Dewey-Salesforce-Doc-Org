from __future__ import annotations

import csv
import tkinter as tk
import unicodedata
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.reporting.excel_writer import ExcelReportWriter
from src.reporting.html_writer import HtmlReportWriter
from src.reporting.word_writer import WordReportWriter
from src.ui.picklist_csv_export import export_picklist_csvs
from src.ui import theme

if TYPE_CHECKING:
    from src.ui.application import Application


def show_data_dictionary_screen(app: Application) -> None:
    """Create and show the data dictionary creation window."""
    DataDictionaryScreen(app)


def _normalize_csv_header(value: str) -> str:
    """Accent/case-insensitive normalization used to recognize CSV columns
    regardless of the exact casing/accents used by whoever prepared the
    file (e.g. "Piloté Par" vs "piloté par" vs "Pilote Par")."""
    ascii_value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return ascii_value.strip().lower()


class DataDictionaryScreen:
    STATUS_OPTIONS = ["-", "en dév.", "Livré"]
    SQUAD_MAX_LENGTH = 50

    CSV_HEADERS = ["API Name", "Commentaire Dewey", "Piloté par", "Status", "Squad"]
    _CSV_OBJECT_HEADER_ALIASES = {"api name", "nom api", "objet", "object"}
    _CSV_COMMENT_HEADER_ALIASES = {"commentaire dewey"}
    _CSV_PILOTED_BY_HEADER_ALIASES = {"pilote par"}
    _CSV_STATUS_HEADER_ALIASES = {"status", "statut"}
    _CSV_SQUAD_HEADER_ALIASES = {"squad"}

    def __init__(self, app: Application) -> None:
        self.app = app
        self.window = tk.Toplevel(app)
        self.window.title(app._t("data_dictionary_title"))
        self.window.geometry("800x760")
        app._configure_secondary_window(self.window)

        # Settings persistence
        self.html_var = tk.BooleanVar(value=app.settings.get("dd_html", True))
        self.word_var = tk.BooleanVar(value=app.settings.get("dd_word", True))
        self.excel_var = tk.BooleanVar(value=app.settings.get("dd_excel", True))
        self.selected_objects = set(app.settings.get("dd_selected_objects", []))
        self.object_comments: dict[str, str] = dict(app.settings.get("dd_object_comments", {}))
        self.object_piloted_by: dict[str, str] = dict(app.settings.get("dd_object_piloted_by", {}))
        self.object_status: dict[str, str] = dict(app.settings.get("dd_object_status", {}))
        self.object_squad: dict[str, str] = dict(app.settings.get("dd_object_squad", {}))
        self.include_comment_var = tk.BooleanVar(value=app.settings.get("dd_include_comment", True))
        self.include_piloted_by_var = tk.BooleanVar(value=app.settings.get("dd_include_piloted_by", True))
        self.include_status_var = tk.BooleanVar(value=app.settings.get("dd_include_status", True))
        self.include_squad_var = tk.BooleanVar(value=app.settings.get("dd_include_squad", True))
        self.concat_description_var = tk.BooleanVar(
            value=app.settings.get("dd_concat_description_in_comment", True)
        )
        self.all_objects = []
        self.current_comment_object: str | None = None

        self._build_ui()
        self._load_objects()

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

    def _load_objects(self) -> None:
        source_path = self.app.source_var.get()
        if not source_path:
            messagebox.showinfo(self.app._t("info_title"), self.app._t("data_dictionary_no_objects"))
            return

        source_dir = Path(source_path)
        if not source_dir.exists():
            messagebox.showinfo(self.app._t("info_title"), self.app._t("data_dictionary_no_objects"))
            return

        # Use the parser to find package roots and objects
        parser = SalesforceMetadataParser(
            source_dir, exclusion_config_path=self.app._selected_exclusion_file()
        )
        package_roots = parser._resolve_package_roots()
        
        self.all_objects = []
        for root in package_roots:
            obj_dir = root / "objects"
            if obj_dir.exists():
                for d in obj_dir.iterdir():
                    if d.is_dir():
                        self.all_objects.append(d.name)
        
        if not self.all_objects:
            messagebox.showinfo(self.app._t("info_title"), self.app._t("data_dictionary_no_objects"))
            return

        self.all_objects = sorted(list(set(self.all_objects)))
        
        # Initial population of lists
        self._refresh_lists()

    def _refresh_lists(self) -> None:
        self._apply_filter()
        self._refresh_selected_list()

    def _refresh_selected_list(self) -> None:
        self.selected_listbox.delete(0, tk.END)
        for obj in sorted(list(self.selected_objects)):
            self.selected_listbox.insert(tk.END, obj)

    def _apply_filter(self) -> None:
        query = self.filter_var.get().lower()
        self.available_listbox.delete(0, tk.END)
        
        for obj in self.all_objects:
            if obj not in self.selected_objects:
                if not query or query in obj.lower():
                    self.available_listbox.insert(tk.END, obj)

    def _move_to_selected(self) -> None:
        selection = self.available_listbox.curselection()
        if not selection:
            return
        
        for index in reversed(selection):
            obj = self.available_listbox.get(index)
            self.selected_objects.add(obj)
        
        self._refresh_lists()
        self._set_comment_target(None)

    def _move_to_available(self) -> None:
        selection = self.selected_listbox.curselection()
        if not selection:
            return
        
        for index in reversed(selection):
            obj = self.selected_listbox.get(index)
            if obj in self.selected_objects:
                self.selected_objects.remove(obj)
        
        self._refresh_lists()
        self._set_comment_target(None)

    def _on_object_select(self, event: tk.Event) -> None:
        widget = event.widget
        selection = widget.curselection()
        if len(selection) == 1:
            self._set_comment_target(widget.get(selection[0]))
        else:
            self._set_comment_target(None)

    def _validate_squad_input(self, proposed_value: str) -> bool:
        return len(proposed_value) <= self.SQUAD_MAX_LENGTH

    def _set_comment_target(self, obj: str | None) -> None:
        self.current_comment_object = obj
        self.comment_text.configure(state="normal")
        self.comment_text.delete("1.0", tk.END)

        if obj:
            self.comment_label_var.set(self.app._t("data_dictionary_comment_for", object=obj))
            self.comment_text.insert("1.0", self.object_comments.get(obj, ""))
            self.piloted_by_var.set(self.object_piloted_by.get(obj, ""))
            self.status_var.set(self.object_status.get(obj, self.STATUS_OPTIONS[0]))
            self.squad_var.set(self.object_squad.get(obj, ""))
            self.piloted_by_entry.configure(state="normal")
            self.status_combo.configure(state="readonly")
            self.squad_entry.configure(state="normal")
            self.save_comment_btn.configure(state="normal")
            has_extra_info = (
                obj in self.object_comments
                or obj in self.object_piloted_by
                or obj in self.object_status
                or obj in self.object_squad
            )
            self.delete_comment_btn.configure(state="normal" if has_extra_info else "disabled")
        else:
            self.comment_label_var.set(self.app._t("data_dictionary_comment_placeholder"))
            self.comment_text.configure(state="disabled")
            self.piloted_by_var.set("")
            self.status_var.set(self.STATUS_OPTIONS[0])
            self.squad_var.set("")
            self.piloted_by_entry.configure(state="disabled")
            self.status_combo.configure(state="disabled")
            self.squad_entry.configure(state="disabled")
            self.save_comment_btn.configure(state="disabled")
            self.delete_comment_btn.configure(state="disabled")

    def _save_comment(self) -> None:
        if not self.current_comment_object:
            return

        obj = self.current_comment_object
        comment = self.comment_text.get("1.0", tk.END).strip()
        piloted_by = self.piloted_by_var.get().strip()
        status = self.status_var.get().strip() or self.STATUS_OPTIONS[0]
        squad = self.squad_var.get().strip()[: self.SQUAD_MAX_LENGTH]

        if comment:
            self.object_comments[obj] = comment
        elif obj in self.object_comments:
            del self.object_comments[obj]

        if piloted_by:
            self.object_piloted_by[obj] = piloted_by
        elif obj in self.object_piloted_by:
            del self.object_piloted_by[obj]

        if status != self.STATUS_OPTIONS[0]:
            self.object_status[obj] = status
        elif obj in self.object_status:
            del self.object_status[obj]

        if squad:
            self.object_squad[obj] = squad
        elif obj in self.object_squad:
            del self.object_squad[obj]

        has_extra_info = (
            obj in self.object_comments
            or obj in self.object_piloted_by
            or obj in self.object_status
            or obj in self.object_squad
        )
        self.delete_comment_btn.configure(state="normal" if has_extra_info else "disabled")

        self._persist_comments()

    def _delete_comment(self) -> None:
        if not self.current_comment_object:
            return

        obj = self.current_comment_object
        changed = False
        if obj in self.object_comments:
            del self.object_comments[obj]
            changed = True
        if obj in self.object_piloted_by:
            del self.object_piloted_by[obj]
            changed = True
        if obj in self.object_status:
            del self.object_status[obj]
            changed = True
        if obj in self.object_squad:
            del self.object_squad[obj]
            changed = True

        if changed:
            self._persist_comments()

        self.comment_text.delete("1.0", tk.END)
        self.piloted_by_var.set("")
        self.status_var.set(self.STATUS_OPTIONS[0])
        self.squad_var.set("")
        self.delete_comment_btn.configure(state="disabled")

    def _persist_comments(self) -> None:
        self.app.settings["dd_object_comments"] = dict(self.object_comments)
        self.app.settings["dd_object_piloted_by"] = dict(self.object_piloted_by)
        self.app.settings["dd_object_status"] = dict(self.object_status)
        self.app.settings["dd_object_squad"] = dict(self.object_squad)
        self.app._save_settings()

    def _generate(self) -> None:
        if not self.selected_objects:
            messagebox.showwarning(self.app._t("info_title"), "Veuillez sélectionner au moins un objet.")
            return

        if not (self.html_var.get() or self.word_var.get() or self.excel_var.get()):
            messagebox.showwarning(self.app._t("info_title"), "Veuillez sélectionner au moins un format de sortie.")
            return

        # Check for existing files
        output_dir = Path(self.app.output_var.get())
        date_str = datetime.now().strftime("%Y%m%d")
        filename_base = f"dataDictionnary_{date_str}"
        
        existing_files = []
        if self.excel_var.get():
            excel_path = output_dir / "excel" / f"{filename_base}.xlsx"
            if excel_path.exists():
                existing_files.append(excel_path.name)
        if self.word_var.get():
            word_path = output_dir / "word" / f"{filename_base}.docx"
            if word_path.exists():
                existing_files.append(word_path.name)
        if self.html_var.get():
            html_path = output_dir / "html" / f"{filename_base}.html"
            if html_path.exists():
                existing_files.append(html_path.name)
        
        if existing_files:
            msg = "Les fichiers suivants existent déjà :\n\n" + "\n".join(f"- {f}" for f in existing_files)
            msg += "\n\nVoulez-vous les écraser ?"
            if not messagebox.askyesno("Fichiers existants", msg):
                return

        # Save settings
        self.app.settings["dd_html"] = self.html_var.get()
        self.app.settings["dd_word"] = self.word_var.get()
        self.app.settings["dd_excel"] = self.excel_var.get()
        self.app.settings["dd_selected_objects"] = list(self.selected_objects)
        self.app.settings["dd_include_comment"] = self.include_comment_var.get()
        self.app.settings["dd_include_piloted_by"] = self.include_piloted_by_var.get()
        self.app.settings["dd_include_status"] = self.include_status_var.get()
        self.app.settings["dd_include_squad"] = self.include_squad_var.get()
        self.app.settings["dd_concat_description_in_comment"] = self.concat_description_var.get()
        self.app._save_settings()

        # Start generation task
        self.app.task_manager.start_task(
            status_text="Génération du Data Dictionnary...",
            task=self._run_generation,
            success_message=self.app._t("data_dictionary_success"),
        )
        self.window.destroy()

    def _export_picklist_csv(self) -> None:
        """Same export as "Documentation > Creer les CSV des picklists", but
        restricted to the objects currently selected in this screen."""
        if not self.selected_objects:
            messagebox.showwarning(self.app._t("info_title"), "Veuillez sélectionner au moins un objet.")
            return

        self.app.settings["dd_selected_objects"] = list(self.selected_objects)
        self.app._save_settings()

        export_picklist_csvs(self.app, selected_objects=set(self.selected_objects))

    def _export_csv(self) -> None:
        """Export the object name plus the 4 custom fields (Commentaire
        Dewey, Piloté par, Status, Squad) for the currently selected
        objects to a CSV file chosen by the user."""
        if not self.selected_objects:
            messagebox.showwarning(
                self.app._t("info_title"), self.app._t("data_dictionary_csv_export_no_objects")
            )
            return

        file_path = filedialog.asksaveasfilename(
            title=self.app._t("data_dictionary_csv_export_title"),
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="data_dictionary_infos.csv",
        )
        if not file_path:
            return

        ordered_objects = sorted(self.selected_objects)
        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow(self.CSV_HEADERS)
                for obj in ordered_objects:
                    writer.writerow(
                        [
                            obj,
                            self.object_comments.get(obj, ""),
                            self.object_piloted_by.get(obj, ""),
                            self.object_status.get(obj, self.STATUS_OPTIONS[0]),
                            self.object_squad.get(obj, ""),
                        ]
                    )
        except OSError as exc:
            messagebox.showerror(
                self.app._t("error_title"),
                self.app._t("data_dictionary_csv_export_error", error=str(exc)),
            )
            return

        messagebox.showinfo(
            self.app._t("success_title"),
            self.app._t(
                "data_dictionary_csv_export_success", count=len(ordered_objects), path=file_path
            ),
        )

    def _import_csv(self) -> None:
        """Import the object name plus the 4 custom fields from a CSV file
        chosen by the user, updating the in-memory state (and persisted
        settings) accordingly. Objects found in the file that are not
        already selected get added to the selection; unrecognized object
        names are skipped and reported to the user."""
        file_path = filedialog.askopenfilename(
            title=self.app._t("data_dictionary_csv_import_title"),
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", newline="", encoding="utf-8-sig") as handle:
                sample = handle.read(4096)
                handle.seek(0)
                delimiter = ";" if sample.count(";") >= sample.count(",") else ","
                reader = csv.DictReader(handle, delimiter=delimiter)
                rows = list(reader)
                fieldnames = reader.fieldnames or []
        except OSError as exc:
            messagebox.showerror(
                self.app._t("error_title"),
                self.app._t("data_dictionary_csv_import_error", error=str(exc)),
            )
            return

        column_by_role: dict[str, str] = {}
        for header in fieldnames:
            normalized = _normalize_csv_header(header)
            if normalized in self._CSV_OBJECT_HEADER_ALIASES:
                column_by_role["object"] = header
            elif normalized in self._CSV_COMMENT_HEADER_ALIASES:
                column_by_role["comment"] = header
            elif normalized in self._CSV_PILOTED_BY_HEADER_ALIASES:
                column_by_role["piloted_by"] = header
            elif normalized in self._CSV_STATUS_HEADER_ALIASES:
                column_by_role["status"] = header
            elif normalized in self._CSV_SQUAD_HEADER_ALIASES:
                column_by_role["squad"] = header

        if "object" not in column_by_role:
            messagebox.showerror(
                self.app._t("error_title"),
                self.app._t("data_dictionary_csv_import_missing_column"),
            )
            return

        known_objects = set(self.all_objects)
        updated_count = 0
        added_count = 0
        skipped_count = 0

        for row in rows:
            obj = (row.get(column_by_role["object"]) or "").strip()
            if not obj or obj not in known_objects:
                if obj:
                    skipped_count += 1
                continue

            comment = (row.get(column_by_role.get("comment", ""), "") or "").strip()
            piloted_by = (row.get(column_by_role.get("piloted_by", ""), "") or "").strip()
            status = (row.get(column_by_role.get("status", ""), "") or "").strip() or self.STATUS_OPTIONS[0]
            squad = (row.get(column_by_role.get("squad", ""), "") or "").strip()[: self.SQUAD_MAX_LENGTH]

            if "comment" in column_by_role:
                if comment:
                    self.object_comments[obj] = comment
                elif obj in self.object_comments:
                    del self.object_comments[obj]
            if "piloted_by" in column_by_role:
                if piloted_by:
                    self.object_piloted_by[obj] = piloted_by
                elif obj in self.object_piloted_by:
                    del self.object_piloted_by[obj]
            if "status" in column_by_role:
                if status != self.STATUS_OPTIONS[0]:
                    self.object_status[obj] = status
                elif obj in self.object_status:
                    del self.object_status[obj]
            if "squad" in column_by_role:
                if squad:
                    self.object_squad[obj] = squad
                elif obj in self.object_squad:
                    del self.object_squad[obj]

            if obj not in self.selected_objects:
                self.selected_objects.add(obj)
                added_count += 1
            updated_count += 1

        self._persist_comments()
        self.app.settings["dd_selected_objects"] = list(self.selected_objects)
        self.app._save_settings()

        self._refresh_lists()
        self._set_comment_target(
            self.current_comment_object if self.current_comment_object in self.selected_objects else None
        )

        messagebox.showinfo(
            self.app._t("success_title"),
            self.app._t(
                "data_dictionary_csv_import_success",
                updated=updated_count,
                added=added_count,
                skipped=skipped_count,
            ),
        )

    def _run_generation(self) -> None:
        source_dir = Path(self.app.source_var.get())
        output_dir = Path(self.app.output_var.get())
        
        # Parse selected objects
        parser = SalesforceMetadataParser(
            source_dir,
            exclusion_config_path=self.app._selected_exclusion_file(),
            log_callback=self.app.task_manager.queue_log,
        )
        snapshot = parser.parse()
        
        # Filter snapshot objects
        snapshot.objects = [obj for obj in snapshot.objects if obj.api_name in self.selected_objects]

        # Attach the user-defined extra info ("Commentaire Dewey", "Piloté
        # par", "Status") to each object so the writers can include it
        # alongside the parsed metadata.
        for obj in snapshot.objects:
            obj.dewey_comment = self.object_comments.get(obj.api_name, "")
            obj.dewey_piloted_by = self.object_piloted_by.get(obj.api_name, "")
            obj.dewey_status = self.object_status.get(obj.api_name, self.STATUS_OPTIONS[0])
            obj.dewey_squad = self.object_squad.get(obj.api_name, "")
        
        date_str = datetime.now().strftime("%Y%m%d")
        filename_base = f"dataDictionnary_{date_str}"

        include_comment = self.include_comment_var.get()
        include_piloted_by = self.include_piloted_by_var.get()
        include_status = self.include_status_var.get()
        include_squad = self.include_squad_var.get()
        concat_description = self.concat_description_var.get()

        if self.excel_var.get():
            excel_dir = output_dir / "excel"
            excel_dir.mkdir(parents=True, exist_ok=True)
            writer = ExcelReportWriter(log_callback=self.app.task_manager.queue_log)
            writer.write_data_dictionary_workbooks(
                snapshot.objects,
                excel_dir,
                filename_base=filename_base,
                include_comment=include_comment,
                include_piloted_by=include_piloted_by,
                include_status=include_status,
                include_squad=include_squad,
                concat_description=concat_description,
            )

        if self.word_var.get():
            word_dir = output_dir / "word"
            word_dir.mkdir(parents=True, exist_ok=True)
            writer = WordReportWriter(language=self.app.language, log_callback=self.app.task_manager.queue_log)
            writer.write_data_dictionary_document(
                snapshot,
                word_dir / f"{filename_base}.docx",
                include_comment=include_comment,
                include_piloted_by=include_piloted_by,
                include_status=include_status,
                include_squad=include_squad,
                concat_description=concat_description,
            )

        if self.html_var.get():
            html_dir = output_dir / "html"
            html_dir.mkdir(parents=True, exist_ok=True)
            writer = HtmlReportWriter(output_dir, log_callback=self.app.task_manager.queue_log)
            # Generate individual pages
            writer.write_object_pages(
                snapshot,
                include_comment=include_comment,
                include_piloted_by=include_piloted_by,
                include_status=include_status,
                include_squad=include_squad,
                concat_description=concat_description,
            )
            # Generate combined page
            writer.write_combined_data_dictionary_html(
                snapshot,
                html_dir / f"{filename_base}.html",
                include_comment=include_comment,
                include_piloted_by=include_piloted_by,
                include_status=include_status,
                include_squad=include_squad,
                concat_description=concat_description,
            )
