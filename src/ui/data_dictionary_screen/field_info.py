"""Per-field extra info panel of the Data Dictionary screen.

Owns the "Informations complementaires sur les champs" panel: the field
list of the currently targeted object and the Commentaire Dewey / Piloté
par values attached to each of its fields.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from src.core.utils import child_text, parse_xml


class _DataDictionaryFieldInfoMixin:
    """Read an object's fields and edit their Commentaire Dewey / Piloté par."""

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
