"""Data Dictionary creation screen.

Split into thematic mixins: UI construction (``builders``), CSV
import/export of the extra fields (``csv_io``) and report generation
(``generation``). This module keeps the window lifecycle, the
available/selected object lists and the per-object "extra info" comment
panel (Commentaire Dewey / Piloté par / Status / Squad).
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

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
