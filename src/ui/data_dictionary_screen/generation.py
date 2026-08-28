"""Report generation (Excel/Word/HTML) for the Data Dictionary screen."""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from src.core.data_dictionary_selection import (
    DataDictionarySelection,
    data_dictionary_filename_base,
)
from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.reporting.excel_writer import ExcelReportWriter
from src.reporting.html_writer import HtmlReportWriter
from src.reporting.word_writer import WordReportWriter
from src.ui.picklist_csv_export import export_picklist_csvs


class _DataDictionaryGenerationMixin:
    """Kicks off the Excel/Word/HTML Data Dictionary generation."""

    def _selection(self) -> DataDictionarySelection:
        """Snapshot of the screen state, in the form shared with the
        full documentation run."""
        return DataDictionarySelection(
            objects=set(self.selected_objects),
            object_comments=dict(self.object_comments),
            object_piloted_by=dict(self.object_piloted_by),
            object_status=dict(self.object_status),
            object_squad=dict(self.object_squad),
            object_squad_consumer=dict(self.object_squad_consumer),
            field_comments={
                obj: dict(fields) for obj, fields in self.field_comments.items()
            },
            field_piloted_by={
                obj: dict(fields) for obj, fields in self.field_piloted_by.items()
            },
            include_comment=self.include_comment_var.get(),
            include_piloted_by=self.include_piloted_by_var.get(),
            include_status=self.include_status_var.get(),
            include_squad=self.include_squad_var.get(),
            include_squad_consumer=self.include_squad_consumer_var.get(),
            include_field_comment=self.include_field_comment_var.get(),
            include_field_piloted_by=self.include_field_piloted_by_var.get(),
            include_field_automation=self.include_field_automation_var.get(),
            concat_description=self.concat_description_var.get(),
        )

    def _generate(self) -> None:
        if not self.selected_objects:
            messagebox.showwarning(self.app._t("info_title"), "Veuillez sélectionner au moins un objet.")
            return

        if not (self.html_var.get() or self.word_var.get() or self.excel_var.get()):
            messagebox.showwarning(self.app._t("info_title"), "Veuillez sélectionner au moins un format de sortie.")
            return

        # Check for existing files
        output_dir = Path(self.app.output_var.get())
        filename_base = data_dictionary_filename_base()

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
        self.app.settings["dd_include_squad_consumer"] = self.include_squad_consumer_var.get()
        self.app.settings["dd_include_field_comment"] = self.include_field_comment_var.get()
        self.app.settings["dd_include_field_piloted_by"] = self.include_field_piloted_by_var.get()
        self.app.settings["dd_include_field_automation"] = self.include_field_automation_var.get()
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

        # Restrict the snapshot to the selected objects and attach the
        # user-defined extra info ("Commentaire Dewey", "Piloté par",
        # "Status", squads) so the writers can include it alongside the
        # parsed metadata.
        selection = self._selection()
        snapshot.objects = selection.apply(snapshot.objects)

        filename_base = data_dictionary_filename_base()

        include_comment = selection.include_comment
        include_piloted_by = selection.include_piloted_by
        include_status = selection.include_status
        include_squad = selection.include_squad
        include_squad_consumer = selection.include_squad_consumer
        concat_description = selection.concat_description

        if self.excel_var.get():
            excel_dir = output_dir / "excel"
            excel_dir.mkdir(parents=True, exist_ok=True)
            writer = ExcelReportWriter(log_callback=self.app.task_manager.queue_log)
            writer.write_data_dictionary_workbooks(
                snapshot.objects,
                excel_dir,
                filename_base=filename_base,
                **selection.workbook_options(),
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
                include_squad_consumer=include_squad_consumer,
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
                include_squad_consumer=include_squad_consumer,
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
                include_squad_consumer=include_squad_consumer,
                concat_description=concat_description,
            )
