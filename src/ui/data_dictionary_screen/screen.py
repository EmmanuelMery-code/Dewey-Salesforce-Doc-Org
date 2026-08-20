"""Data Dictionary creation screen.

Split into thematic mixins: UI construction (``builders``), CSV
import/export of the extra fields (``csv_io``) and report generation
(``generation``). This module keeps the window lifecycle, the
available/selected object lists, the per-object "extra info" comment
panel (Commentaire Dewey / Piloté par / Status / Squad Responsable /
Squad Consommatrice) and the per-field "extra info" panel (Commentaire
Dewey / Piloté par for the fields of the currently targeted object).
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from src.core.utils import child_text, parse_xml
from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.ui.data_dictionary_screen.builders import _DataDictionaryUiBuilderMixin
from src.ui.data_dictionary_screen.csv_io import _DataDictionaryCsvMixin
from src.ui.data_dictionary_screen.generation import _DataDictionaryGenerationMixin

if TYPE_CHECKING:
    from src.ui.application import Application


def show_data_dictionary_screen(app: Application) -> None:
    """Create and show the data dictionary creation window."""
    DataDictionaryScreen(app)


class DataDictionaryScreen(
    _DataDictionaryUiBuilderMixin,
    _DataDictionaryCsvMixin,
    _DataDictionaryGenerationMixin,
):
    STATUS_OPTIONS = ["-", "en dév.", "Livré"]
    SQUAD_MAX_LENGTH = 50

    def __init__(self, app: Application) -> None:
        self.app = app
        self.window = tk.Toplevel(app)
        self.window.title(app._t("data_dictionary_title"))
        self.window.geometry("1000x820")
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
        self.object_squad_consumer: dict[str, str] = dict(
            app.settings.get("dd_object_squad_consumer", {})
        )
        # Per-field extra info: {object_api_name: {field_api_name: value}}.
        self.field_comments: dict[str, dict[str, str]] = {
            obj: dict(fields) for obj, fields in app.settings.get("dd_field_comments", {}).items()
        }
        self.field_piloted_by: dict[str, dict[str, str]] = {
            obj: dict(fields) for obj, fields in app.settings.get("dd_field_piloted_by", {}).items()
        }
        self.include_comment_var = tk.BooleanVar(value=app.settings.get("dd_include_comment", True))
        self.include_piloted_by_var = tk.BooleanVar(value=app.settings.get("dd_include_piloted_by", True))
        self.include_status_var = tk.BooleanVar(value=app.settings.get("dd_include_status", True))
        self.include_squad_var = tk.BooleanVar(value=app.settings.get("dd_include_squad", True))
        self.include_squad_consumer_var = tk.BooleanVar(
            value=app.settings.get("dd_include_squad_consumer", True)
        )
        self.include_field_comment_var = tk.BooleanVar(
            value=app.settings.get("dd_include_field_comment", True)
        )
        self.include_field_piloted_by_var = tk.BooleanVar(
            value=app.settings.get("dd_include_field_piloted_by", True)
        )
        self.concat_description_var = tk.BooleanVar(
            value=app.settings.get("dd_concat_description_in_comment", True)
        )
        self.all_objects = []
        self._object_dirs: dict[str, Path] = {}
        self.current_comment_object: str | None = None
        self.current_comment_field: str | None = None
        self._selected_sort_column: str | None = None
        self._selected_sort_reverse = False

        self._build_ui()
        self._load_objects()

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
        self._object_dirs = {}
        for root in package_roots:
            obj_dir = root / "objects"
            if obj_dir.exists():
                for d in obj_dir.iterdir():
                    if d.is_dir():
                        self.all_objects.append(d.name)
                        self._object_dirs[d.name] = d
        
        if not self.all_objects:
            messagebox.showinfo(self.app._t("info_title"), self.app._t("data_dictionary_no_objects"))
            return

        self.all_objects = sorted(list(set(self.all_objects)))
        
        # Initial population of lists
        self._refresh_lists()

    def _refresh_lists(self) -> None:
        self._apply_filter()
        self._refresh_selected_list()

    def _selected_rows(self) -> list[tuple[str, str, str, str, str]]:
        """Return one row per selected object: (object, piloted_by, status,
        squad, squad_consumer), the same values shown in the "Objets
        selectionnes" columns."""
        return [
            (
                obj,
                self.object_piloted_by.get(obj, ""),
                self.object_status.get(obj, self.STATUS_OPTIONS[0]),
                self.object_squad.get(obj, ""),
                self.object_squad_consumer.get(obj, ""),
            )
            for obj in self.selected_objects
        ]

    def _refresh_selected_list(self) -> None:
        self._apply_selected_filter()

    def _selected_row_tag(self, obj: str) -> str:
        """Return the background tag for ``obj``'s row, based on how many
        of its fields have a "Piloté par" value: all filled -> green, some
        filled -> yellow, none filled (or no fields at all) -> red."""
        fields = self._list_object_fields(obj)
        if not fields:
            return "piloted_none"
        piloted = self.field_piloted_by.get(obj, {})
        filled = sum(1 for api_name, _label in fields if (piloted.get(api_name) or "").strip())
        if filled == len(fields):
            return "piloted_all"
        if filled == 0:
            return "piloted_none"
        return "piloted_some"

    def _apply_selected_filter(self) -> None:
        """Rebuild the "Objets selectionnes" tree from the current filter
        text and sort column, preserving the current comment target's
        selection highlight (without re-triggering the selection handler)."""
        query = self.selected_filter_var.get().strip().lower()
        rows = self._selected_rows()
        if query:
            rows = [row for row in rows if any(query in (value or "").lower() for value in row)]

        columns = list(self._SELECTED_COLUMN_LABELS.keys())
        if self._selected_sort_column in columns:
            column_index = columns.index(self._selected_sort_column)
            rows.sort(key=lambda row: (row[column_index] or "").lower(), reverse=self._selected_sort_reverse)
        else:
            rows.sort(key=lambda row: row[0].lower())

        self.selected_listbox.unbind("<<TreeviewSelect>>")
        self.selected_listbox.delete(*self.selected_listbox.get_children())
        for row in rows:
            self.selected_listbox.insert(
                "", tk.END, iid=row[0], values=row, tags=(self._selected_row_tag(row[0]),)
            )
        if self.current_comment_object in {row[0] for row in rows}:
            self.selected_listbox.selection_set(self.current_comment_object)
        self.selected_listbox.bind("<<TreeviewSelect>>", self._on_selected_tree_select)

    def _sort_selected_by(self, column: str) -> None:
        if self._selected_sort_column == column:
            self._selected_sort_reverse = not self._selected_sort_reverse
        else:
            self._selected_sort_column = column
            self._selected_sort_reverse = False
        self._update_selected_headings()
        self._apply_selected_filter()

    def _update_selected_headings(self) -> None:
        for column, base_label in self._SELECTED_COLUMN_LABELS.items():
            label = base_label
            if column == self._selected_sort_column:
                label += " ▼" if self._selected_sort_reverse else " ▲"
            self.selected_listbox.heading(
                column, text=label, command=lambda c=column: self._sort_selected_by(c)
            )

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
        selection = self.selected_listbox.selection()
        if not selection:
            return
        
        for obj in selection:
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

    def _on_selected_tree_select(self, event: tk.Event) -> None:
        selection = self.selected_listbox.selection()
        if len(selection) == 1:
            self._set_comment_target(selection[0])
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
            self.squad_consumer_var.set(self.object_squad_consumer.get(obj, ""))
            self.piloted_by_entry.configure(state="normal")
            self.status_combo.configure(state="readonly")
            self.squad_entry.configure(state="normal")
            self.squad_consumer_entry.configure(state="normal")
            self.save_comment_btn.configure(state="normal")
            has_extra_info = (
                obj in self.object_comments
                or obj in self.object_piloted_by
                or obj in self.object_status
                or obj in self.object_squad
                or obj in self.object_squad_consumer
            )
            self.delete_comment_btn.configure(state="normal" if has_extra_info else "disabled")
        else:
            self.comment_label_var.set(self.app._t("data_dictionary_comment_placeholder"))
            self.comment_text.configure(state="disabled")
            self.piloted_by_var.set("")
            self.status_var.set(self.STATUS_OPTIONS[0])
            self.squad_var.set("")
            self.squad_consumer_var.set("")
            self.piloted_by_entry.configure(state="disabled")
            self.status_combo.configure(state="disabled")
            self.squad_entry.configure(state="disabled")
            self.squad_consumer_entry.configure(state="disabled")
            self.save_comment_btn.configure(state="disabled")
            self.delete_comment_btn.configure(state="disabled")

        self._refresh_fields_list(obj)

    def _save_comment(self) -> None:
        if not self.current_comment_object:
            return

        obj = self.current_comment_object
        comment = self.comment_text.get("1.0", tk.END).strip()
        piloted_by = self.piloted_by_var.get().strip()
        status = self.status_var.get().strip() or self.STATUS_OPTIONS[0]
        squad = self.squad_var.get().strip()[: self.SQUAD_MAX_LENGTH]
        squad_consumer = self.squad_consumer_var.get().strip()[: self.SQUAD_MAX_LENGTH]

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

        if squad_consumer:
            self.object_squad_consumer[obj] = squad_consumer
        elif obj in self.object_squad_consumer:
            del self.object_squad_consumer[obj]

        has_extra_info = (
            obj in self.object_comments
            or obj in self.object_piloted_by
            or obj in self.object_status
            or obj in self.object_squad
            or obj in self.object_squad_consumer
        )
        self.delete_comment_btn.configure(state="normal" if has_extra_info else "disabled")

        self._persist_comments()
        self._refresh_selected_list()

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
        if obj in self.object_squad_consumer:
            del self.object_squad_consumer[obj]
            changed = True

        if changed:
            self._persist_comments()

        self.comment_text.delete("1.0", tk.END)
        self.piloted_by_var.set("")
        self.status_var.set(self.STATUS_OPTIONS[0])
        self.squad_var.set("")
        self.squad_consumer_var.set("")
        self.delete_comment_btn.configure(state="disabled")

        if changed:
            self._refresh_selected_list()

    def _persist_comments(self) -> None:
        self.app.settings["dd_object_comments"] = dict(self.object_comments)
        self.app.settings["dd_object_piloted_by"] = dict(self.object_piloted_by)
        self.app.settings["dd_object_status"] = dict(self.object_status)
        self.app.settings["dd_object_squad"] = dict(self.object_squad)
        self.app.settings["dd_object_squad_consumer"] = dict(self.object_squad_consumer)
        self.app._save_settings()

    # ------------------------------------------------------------------
    # Per-field extra info ("Informations complementaires sur les champs")
    # ------------------------------------------------------------------

    def _list_object_fields(self, obj: str) -> list[tuple[str, str]]:
        """Return ``[(api_name, label), ...]`` sorted by API name for
        ``obj``'s fields, read directly from the metadata files (no need
        for a full parser pass since only the label/API name are used)."""
        object_dir = self._object_dirs.get(obj)
        if not object_dir:
            return []

        fields_dir = object_dir / "fields"
        if not fields_dir.exists():
            return []

        fields: list[tuple[str, str]] = []
        for field_file in sorted(fields_dir.glob("*.field-meta.xml")):
            try:
                root = parse_xml(field_file)
            except Exception:
                continue
            api_name = child_text(root, "fullName") or field_file.stem.replace(".field-meta", "")
            label = child_text(root, "label") or api_name
            fields.append((api_name, label))
        return fields

    def _refresh_fields_list(self, obj: str | None) -> None:
        self.fields_tree.delete(*self.fields_tree.get_children())
        if obj:
            for api_name, label in self._list_object_fields(obj):
                self.fields_tree.insert("", tk.END, iid=api_name, values=(label, api_name))
        self._set_field_comment_target(None)

    def _on_field_select(self, event: tk.Event) -> None:
        selection = self.fields_tree.selection()
        if len(selection) == 1:
            self._set_field_comment_target(selection[0])
        else:
            self._set_field_comment_target(None)

    def _set_field_comment_target(self, field_api_name: str | None) -> None:
        self.current_comment_field = field_api_name
        obj = self.current_comment_object

        if field_api_name and obj:
            self.fields_comment_label_var.set(
                self.app._t("data_dictionary_fields_comment_for", field=field_api_name)
            )
            self.field_comment_var.set(self.field_comments.get(obj, {}).get(field_api_name, ""))
            self.field_piloted_by_var.set(
                self.field_piloted_by.get(obj, {}).get(field_api_name, "")
            )
            self.field_comment_entry.configure(state="normal")
            self.field_piloted_by_entry.configure(state="normal")
            self.save_field_comment_btn.configure(state="normal")
            has_extra_info = (
                field_api_name in self.field_comments.get(obj, {})
                or field_api_name in self.field_piloted_by.get(obj, {})
            )
            self.delete_field_comment_btn.configure(state="normal" if has_extra_info else "disabled")
        else:
            self.fields_comment_label_var.set(self.app._t("data_dictionary_fields_comment_placeholder"))
            self.field_comment_var.set("")
            self.field_piloted_by_var.set("")
            self.field_comment_entry.configure(state="disabled")
            self.field_piloted_by_entry.configure(state="disabled")
            self.save_field_comment_btn.configure(state="disabled")
            self.delete_field_comment_btn.configure(state="disabled")

    def _save_field_comment(self) -> None:
        obj = self.current_comment_object
        field_api_name = self.current_comment_field
        if not obj or not field_api_name:
            return

        comment = self.field_comment_var.get().strip()
        piloted_by = self.field_piloted_by_var.get().strip()

        if comment:
            self.field_comments.setdefault(obj, {})[field_api_name] = comment
        elif obj in self.field_comments and field_api_name in self.field_comments[obj]:
            del self.field_comments[obj][field_api_name]

        if piloted_by:
            self.field_piloted_by.setdefault(obj, {})[field_api_name] = piloted_by
        elif obj in self.field_piloted_by and field_api_name in self.field_piloted_by[obj]:
            del self.field_piloted_by[obj][field_api_name]

        has_extra_info = (
            field_api_name in self.field_comments.get(obj, {})
            or field_api_name in self.field_piloted_by.get(obj, {})
        )
        self.delete_field_comment_btn.configure(state="normal" if has_extra_info else "disabled")

        self._persist_field_comments()
        self._refresh_selected_list()

    def _delete_field_comment(self) -> None:
        obj = self.current_comment_object
        field_api_name = self.current_comment_field
        if not obj or not field_api_name:
            return

        changed = False
        if field_api_name in self.field_comments.get(obj, {}):
            del self.field_comments[obj][field_api_name]
            changed = True
        if field_api_name in self.field_piloted_by.get(obj, {}):
            del self.field_piloted_by[obj][field_api_name]
            changed = True

        if changed:
            self._persist_field_comments()
            self._refresh_selected_list()

        self.field_comment_var.set("")
        self.field_piloted_by_var.set("")
        self.delete_field_comment_btn.configure(state="disabled")

    def _persist_field_comments(self) -> None:
        self.app.settings["dd_field_comments"] = {
            obj: dict(fields) for obj, fields in self.field_comments.items()
        }
        self.app.settings["dd_field_piloted_by"] = {
            obj: dict(fields) for obj, fields in self.field_piloted_by.items()
        }
        self.app._save_settings()

    def _copy_object_piloted_by_to_fields(self) -> None:
        """Copy the object's "Piloté par" onto every one of its fields that
        does not already have a "Piloté par" value of its own."""
        obj = self.current_comment_object
        if not obj:
            messagebox.showinfo(
                self.app._t("info_title"), self.app._t("data_dictionary_copy_piloted_by_no_object")
            )
            return

        object_piloted_by = self.object_piloted_by.get(obj, "").strip()
        if not object_piloted_by:
            messagebox.showinfo(
                self.app._t("info_title"), self.app._t("data_dictionary_copy_piloted_by_no_value")
            )
            return

        existing = self.field_piloted_by.get(obj, {})
        updated_count = 0
        for api_name, _label in self._list_object_fields(obj):
            if not existing.get(api_name, "").strip():
                self.field_piloted_by.setdefault(obj, {})[api_name] = object_piloted_by
                updated_count += 1

        if updated_count == 0:
            messagebox.showinfo(
                self.app._t("info_title"), self.app._t("data_dictionary_copy_piloted_by_no_fields")
            )
            return

        self._persist_field_comments()
        self._refresh_selected_list()

        if self.current_comment_field:
            self.field_piloted_by_var.set(
                self.field_piloted_by.get(obj, {}).get(self.current_comment_field, "")
            )
            self.delete_field_comment_btn.configure(state="normal")

        messagebox.showinfo(
            self.app._t("success_title"),
            self.app._t(
                "data_dictionary_copy_piloted_by_success",
                count=updated_count,
                value=object_piloted_by,
            ),
        )
