"""CSV import/export of the Data Dictionary extra fields."""

from __future__ import annotations

import csv
from tkinter import filedialog, messagebox

from src.ui.data_dictionary_screen.constants import _normalize_csv_header


class _DataDictionaryCsvMixin:
    """Export/import the object name plus the 5 custom fields (Commentaire
    Dewey, Piloté par, Status, Squad Responsable, Squad Consommatrice)
    to/from a CSV file."""

    CSV_HEADERS = [
        "API Name",
        "Commentaire Dewey",
        "Piloté par",
        "Status",
        "Squad Responsable",
        "Squad Consommatrice",
    ]
    _CSV_OBJECT_HEADER_ALIASES = {"api name", "nom api", "objet", "object"}
    _CSV_COMMENT_HEADER_ALIASES = {"commentaire dewey"}
    _CSV_PILOTED_BY_HEADER_ALIASES = {"pilote par"}
    _CSV_STATUS_HEADER_ALIASES = {"status", "statut"}
    # "squad" is kept for backward compatibility with CSV files exported
    # before the field was renamed to "Squad Responsable".
    _CSV_SQUAD_HEADER_ALIASES = {"squad", "squad responsable"}
    _CSV_SQUAD_CONSUMER_HEADER_ALIASES = {"squad consommatrice", "squad consumer"}

    # Export/import of the per-field extra info (Commentaire Dewey, Piloté
    # par), one row per field of every currently selected object.
    FIELDS_CSV_HEADERS = ["Objet", "API Name Champ", "Label Champ", "Commentaire Dewey", "Piloté par"]
    _FIELDS_CSV_OBJECT_HEADER_ALIASES = {"objet", "object", "api name objet", "nom api objet"}
    _FIELDS_CSV_FIELD_API_NAME_HEADER_ALIASES = {
        "api name champ",
        "nom api champ",
        "field api name",
        "champ",
    }
    _FIELDS_CSV_COMMENT_HEADER_ALIASES = {"commentaire dewey"}
    _FIELDS_CSV_PILOTED_BY_HEADER_ALIASES = {"pilote par"}

    def _export_csv(self) -> None:
        """Export the object name plus the 5 custom fields (Commentaire
        Dewey, Piloté par, Status, Squad Responsable, Squad Consommatrice)
        for the currently selected objects to a CSV file chosen by the
        user."""
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
                            self.object_squad_consumer.get(obj, ""),
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
            elif normalized in self._CSV_SQUAD_CONSUMER_HEADER_ALIASES:
                column_by_role["squad_consumer"] = header

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
            squad_consumer = (
                row.get(column_by_role.get("squad_consumer", ""), "") or ""
            ).strip()[: self.SQUAD_MAX_LENGTH]

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
            if "squad_consumer" in column_by_role:
                if squad_consumer:
                    self.object_squad_consumer[obj] = squad_consumer
                elif obj in self.object_squad_consumer:
                    del self.object_squad_consumer[obj]

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

    def _export_fields_csv(self) -> None:
        """Export, for every currently selected object, one row per field
        with its "Commentaire Dewey" and "Piloté par" values (blank when
        not yet filled in) to a CSV file chosen by the user."""
        if not self.selected_objects:
            messagebox.showwarning(
                self.app._t("info_title"), self.app._t("data_dictionary_fields_csv_export_no_objects")
            )
            return

        file_path = filedialog.asksaveasfilename(
            title=self.app._t("data_dictionary_fields_csv_export_title"),
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="data_dictionary_fields_infos.csv",
        )
        if not file_path:
            return

        ordered_objects = sorted(self.selected_objects)
        exported_count = 0
        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow(self.FIELDS_CSV_HEADERS)
                for obj in ordered_objects:
                    for api_name, label in self._list_object_fields(obj):
                        writer.writerow(
                            [
                                obj,
                                api_name,
                                label,
                                self.field_comments.get(obj, {}).get(api_name, ""),
                                self.field_piloted_by.get(obj, {}).get(api_name, ""),
                            ]
                        )
                        exported_count += 1
        except OSError as exc:
            messagebox.showerror(
                self.app._t("error_title"),
                self.app._t("data_dictionary_fields_csv_export_error", error=str(exc)),
            )
            return

        messagebox.showinfo(
            self.app._t("success_title"),
            self.app._t(
                "data_dictionary_fields_csv_export_success", count=exported_count, path=file_path
            ),
        )

    def _import_fields_csv(self) -> None:
        """Import per-field "Commentaire Dewey" / "Piloté par" values from a
        CSV file chosen by the user. Rows referencing an unknown object or a
        field that does not belong to that object are skipped; objects that
        are known but not yet selected get added to the selection."""
        file_path = filedialog.askopenfilename(
            title=self.app._t("data_dictionary_fields_csv_import_title"),
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
                self.app._t("data_dictionary_fields_csv_import_error", error=str(exc)),
            )
            return

        column_by_role: dict[str, str] = {}
        for header in fieldnames:
            normalized = _normalize_csv_header(header)
            if normalized in self._FIELDS_CSV_OBJECT_HEADER_ALIASES:
                column_by_role["object"] = header
            elif normalized in self._FIELDS_CSV_FIELD_API_NAME_HEADER_ALIASES:
                column_by_role["field_api_name"] = header
            elif normalized in self._FIELDS_CSV_COMMENT_HEADER_ALIASES:
                column_by_role["comment"] = header
            elif normalized in self._FIELDS_CSV_PILOTED_BY_HEADER_ALIASES:
                column_by_role["piloted_by"] = header

        if "object" not in column_by_role or "field_api_name" not in column_by_role:
            messagebox.showerror(
                self.app._t("error_title"),
                self.app._t("data_dictionary_fields_csv_import_missing_column"),
            )
            return

        known_objects = set(self.all_objects)
        updated_count = 0
        added_count = 0
        skipped_count = 0
        valid_fields_by_object: dict[str, set[str]] = {}

        for row in rows:
            obj = (row.get(column_by_role["object"]) or "").strip()
            field_api_name = (row.get(column_by_role["field_api_name"]) or "").strip()
            if not obj or obj not in known_objects or not field_api_name:
                if obj or field_api_name:
                    skipped_count += 1
                continue

            if obj not in valid_fields_by_object:
                valid_fields_by_object[obj] = {
                    api_name for api_name, _label in self._list_object_fields(obj)
                }
            if field_api_name not in valid_fields_by_object[obj]:
                skipped_count += 1
                continue

            comment = (row.get(column_by_role.get("comment", ""), "") or "").strip()
            piloted_by = (row.get(column_by_role.get("piloted_by", ""), "") or "").strip()

            if "comment" in column_by_role:
                if comment:
                    self.field_comments.setdefault(obj, {})[field_api_name] = comment
                elif field_api_name in self.field_comments.get(obj, {}):
                    del self.field_comments[obj][field_api_name]
            if "piloted_by" in column_by_role:
                if piloted_by:
                    self.field_piloted_by.setdefault(obj, {})[field_api_name] = piloted_by
                elif field_api_name in self.field_piloted_by.get(obj, {}):
                    del self.field_piloted_by[obj][field_api_name]

            if obj not in self.selected_objects:
                self.selected_objects.add(obj)
                added_count += 1
            updated_count += 1

        self._persist_field_comments()
        self.app.settings["dd_selected_objects"] = list(self.selected_objects)
        self.app._save_settings()

        self._refresh_lists()
        self._set_comment_target(
            self.current_comment_object if self.current_comment_object in self.selected_objects else None
        )

        messagebox.showinfo(
            self.app._t("success_title"),
            self.app._t(
                "data_dictionary_fields_csv_import_success",
                updated=updated_count,
                added=added_count,
                skipped=skipped_count,
            ),
        )
