from __future__ import annotations

import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.reporting.excel_writer import ExcelReportWriter
from src.reporting.html_writer import HtmlReportWriter
from src.reporting.word_writer import WordReportWriter

if TYPE_CHECKING:
    from src.ui.application import Application


def show_data_dictionary_screen(app: Application) -> None:
    """Create and show the data dictionary creation window."""
    DataDictionaryScreen(app)


class DataDictionaryScreen:
    def __init__(self, app: Application) -> None:
        self.app = app
        self.window = tk.Toplevel(app)
        self.window.title(app._t("data_dictionary_title"))
        self.window.geometry("800x700")
        app._configure_secondary_window(self.window)

        # Settings persistence
        self.html_var = tk.BooleanVar(value=app.settings.get("dd_html", True))
        self.word_var = tk.BooleanVar(value=app.settings.get("dd_word", True))
        self.excel_var = tk.BooleanVar(value=app.settings.get("dd_excel", True))
        self.selected_objects = set(app.settings.get("dd_selected_objects", []))
        self.all_objects = []

        self._build_ui()
        self._load_objects()

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.window, padding=16)
        main_frame.pack(fill="both", expand=True)

        # Header
        ttk.Label(
            main_frame,
            text=self.app._t("data_dictionary_title"),
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        # Formats
        format_frame = ttk.LabelFrame(main_frame, text=self.app._t("data_dictionary_formats"), padding=10)
        format_frame.pack(fill="x", pady=(0, 12))
        
        ttk.Checkbutton(format_frame, text="HTML", variable=self.html_var).pack(side="left", padx=10)
        ttk.Checkbutton(format_frame, text="Word", variable=self.word_var).pack(side="left", padx=10)
        ttk.Checkbutton(format_frame, text="Excel", variable=self.excel_var).pack(side="left", padx=10)

        # Objects selection area
        selection_container = ttk.Frame(main_frame)
        selection_container.pack(fill="both", expand=True, pady=(0, 12))

        # Left side: Available
        available_frame = ttk.LabelFrame(selection_container, text="Objets disponibles", padding=10)
        available_frame.pack(side="left", fill="both", expand=True)

        filter_row = ttk.Frame(available_frame)
        filter_row.pack(fill="x", pady=(0, 8))
        ttk.Label(filter_row, text=self.app._t("exclusions_filter_label")).pack(side="left", padx=(0, 8))
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *args: self._apply_filter())
        ttk.Entry(filter_row, textvariable=self.filter_var).pack(side="left", fill="x", expand=True)

        list_container_left = ttk.Frame(available_frame)
        list_container_left.pack(fill="both", expand=True)

        self.available_listbox = tk.Listbox(list_container_left, selectmode="extended", exportselection=False)
        available_scroll = ttk.Scrollbar(list_container_left, orient="vertical", command=self.available_listbox.yview)
        self.available_listbox.configure(yscrollcommand=available_scroll.set)
        self.available_listbox.pack(side="left", fill="both", expand=True)
        available_scroll.pack(side="right", fill="y")

        # Center: Buttons
        button_frame = ttk.Frame(selection_container, padding=10)
        button_frame.pack(side="left", fill="y", expand=False)
        
        ttk.Label(button_frame, text="").pack(expand=True) # Spacer
        ttk.Button(button_frame, text=" Ajouter > ", command=self._move_to_selected).pack(pady=5)
        ttk.Button(button_frame, text=" < Retirer ", command=self._move_to_available).pack(pady=5)
        ttk.Label(button_frame, text="").pack(expand=True) # Spacer

        # Right side: Selected
        selected_frame = ttk.LabelFrame(selection_container, text="Objets sélectionnés", padding=10)
        selected_frame.pack(side="left", fill="both", expand=True)

        list_container_right = ttk.Frame(selected_frame)
        list_container_right.pack(fill="both", expand=True)

        self.selected_listbox = tk.Listbox(list_container_right, selectmode="extended", exportselection=False)
        selected_scroll = ttk.Scrollbar(list_container_right, orient="vertical", command=self.selected_listbox.yview)
        self.selected_listbox.configure(yscrollcommand=selected_scroll.set)
        self.selected_listbox.pack(side="left", fill="both", expand=True)
        selected_scroll.pack(side="right", fill="y")

        # Footer
        footer_frame = ttk.Frame(main_frame, padding=(0, 12, 0, 0))
        footer_frame.pack(fill="x")
        
        ttk.Label(footer_frame, text=self.app._t("data_dictionary_naming_convention"), font=("Segoe UI", 9, "italic")).pack(side="left")
        
        ttk.Button(
            footer_frame,
            text=self.app._t("configuration_close"),
            command=self.window.destroy,
        ).pack(side="right")
        
        ttk.Button(
            footer_frame,
            text=self.app._t("data_dictionary_generate"),
            command=self._generate,
        ).pack(side="right", padx=(0, 8))

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
        parser = SalesforceMetadataParser(source_dir)
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

    def _move_to_available(self) -> None:
        selection = self.selected_listbox.curselection()
        if not selection:
            return
        
        for index in reversed(selection):
            obj = self.selected_listbox.get(index)
            if obj in self.selected_objects:
                self.selected_objects.remove(obj)
        
        self._refresh_lists()

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
        self.app._save_settings()

        # Start generation task
        self.app.task_manager.start_task(
            status_text="Génération du Data Dictionnary...",
            task=self._run_generation,
            success_message=self.app._t("data_dictionary_success"),
        )
        self.window.destroy()

    def _run_generation(self) -> None:
        source_dir = Path(self.app.source_var.get())
        output_dir = Path(self.app.output_var.get())
        
        # Parse selected objects
        parser = SalesforceMetadataParser(source_dir, log_callback=self.app.task_manager.queue_log)
        snapshot = parser.parse()
        
        # Filter snapshot objects
        snapshot.objects = [obj for obj in snapshot.objects if obj.api_name in self.selected_objects]
        
        date_str = datetime.now().strftime("%Y%m%d")
        filename_base = f"dataDictionnary_{date_str}"
        
        if self.excel_var.get():
            excel_dir = output_dir / "excel"
            excel_dir.mkdir(parents=True, exist_ok=True)
            writer = ExcelReportWriter(log_callback=self.app.task_manager.queue_log)
            writer.write_data_dictionary_workbooks(snapshot.objects, excel_dir, filename_base=filename_base)

        if self.word_var.get():
            word_dir = output_dir / "word"
            word_dir.mkdir(parents=True, exist_ok=True)
            writer = WordReportWriter(language=self.app.language, log_callback=self.app.task_manager.queue_log)
            writer.write_data_dictionary_document(snapshot, word_dir / f"{filename_base}.docx")

        if self.html_var.get():
            html_dir = output_dir / "html"
            html_dir.mkdir(parents=True, exist_ok=True)
            writer = HtmlReportWriter(output_dir, log_callback=self.app.task_manager.queue_log)
            # Generate individual pages
            writer.write_object_pages(snapshot)
            # Generate combined page
            writer.write_combined_data_dictionary_html(snapshot, html_dir / f"{filename_base}.html")
