"""Objects and fields being designed, absent from the org metadata.

The user declares them from the Data Dictionary screen; they are persisted
in the app settings, carry the "En conception" status and are promoted to
"Livré" as soon as the metadata catches up.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from src.core.data_dictionary_selection import DELIVERED_STATUS, IN_DESIGN_STATUS
from src.ui import theme

#: Offered by the "champ en conception" dialog; the combobox stays editable
#: so a type missing from this list can still be typed in.
VIRTUAL_FIELD_TYPES = (
    "Text",
    "TextArea",
    "LongTextArea",
    "Number",
    "Currency",
    "Percent",
    "Checkbox",
    "Date",
    "DateTime",
    "Email",
    "Phone",
    "Url",
    "Picklist",
    "MultiselectPicklist",
    "Lookup",
    "MasterDetail",
    "Formula",
    "Rollup",
    "Auto Number",
)


def _promotion_recap(app, promoted_objects: list[str], promoted_fields: dict[str, list[str]]) -> str:
    """Recap listing, grouped by object, what just moved to "Livré"."""
    lines: list[str] = []
    for obj in sorted(set(promoted_objects) | set(promoted_fields)):
        suffix = app._t("data_dictionary_virtual_promoted_object_suffix") if obj in promoted_objects else ""
        lines.append(f"- {obj}{suffix}")
        for field_api_name in promoted_fields.get(obj, []):
            lines.append(f"    * {field_api_name}")
    return app._t("data_dictionary_virtual_promoted_message", details="\n".join(lines))


class _VirtualEntryDialog:
    """Modal capture of a virtual object/field, re-prompting on invalid input.

    ``specs`` is a list of ``(key, label, values)``; a non-empty ``values``
    turns the row into an editable combobox. ``validate`` returns an error
    message to display, or ``None`` to accept.
    """

    #: Wide enough for the free-text "Commentaire Dewey" row; the grid makes
    #: every row share it, so the whole dialog widens with it.
    ENTRY_WIDTH = 46

    def __init__(self, parent: tk.Misc, app, title: str, specs, validate) -> None:
        self.app = app
        self.validate = validate
        self.result: dict[str, str] | None = None

        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.transient(parent)
        self.window.resizable(False, False)
        app._configure_secondary_window(self.window)

        frame = ttk.Frame(self.window, padding=theme.SPACE_LG)
        frame.pack(fill="both", expand=True)

        self.variables: dict[str, tk.StringVar] = {}
        for row, (key, label, values) in enumerate(specs):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=theme.SPACE_XS)
            variable = tk.StringVar()
            self.variables[key] = variable
            if values:
                widget = ttk.Combobox(frame, textvariable=variable, values=list(values))
            else:
                widget = ttk.Entry(frame, textvariable=variable, width=self.ENTRY_WIDTH)
            widget.grid(row=row, column=1, sticky="ew", padx=(theme.SPACE_MD, 0), pady=theme.SPACE_XS)
            if row == 0:
                widget.focus_set()
        frame.columnconfigure(1, weight=1)

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(specs), column=0, columnspan=2, sticky="e", pady=(theme.SPACE_MD, 0))
        ttk.Button(
            buttons,
            text=app._t("data_dictionary_virtual_dialog_cancel"),
            command=self.window.destroy,
        ).pack(side="right")
        ttk.Button(
            buttons,
            text=app._t("data_dictionary_virtual_dialog_create"),
            command=self._on_validate,
            style=theme.PRIMARY_BUTTON,
        ).pack(side="right", padx=(0, theme.SPACE_SM))

        self.window.bind("<Return>", lambda _event: self._on_validate())
        self.window.bind("<Escape>", lambda _event: self.window.destroy())
        self.window.grab_set()
        parent.wait_window(self.window)

    def _on_validate(self) -> None:
        values = {key: variable.get().strip() for key, variable in self.variables.items()}
        error = self.validate(values)
        if error:
            messagebox.showerror(self.app._t("error_title"), error, parent=self.window)
            return
        self.result = values
        self.window.destroy()


class _DataDictionaryVirtualEntriesMixin:
    """Create, delete and promote the "En conception" objects and fields."""

    VIRTUAL_FIELD_TYPES = VIRTUAL_FIELD_TYPES

    # ------------------------------------------------------------- queries

    def _is_virtual_object(self, obj: str) -> bool:
        return obj in self.virtual_objects

    def _is_virtual_field(self, obj: str, field_api_name: str) -> bool:
        return field_api_name in self.virtual_fields.get(obj, {})

    def _virtual_object_fields(self, obj: str) -> list[tuple[str, str]]:
        """``[(api_name, label), ...]`` for ``obj``'s virtual fields."""
        return [
            (api_name, info.get("label") or api_name)
            for api_name, info in sorted(self.virtual_fields.get(obj, {}).items())
        ]

    # ---------------------------------------------------------- validation

    def _virtual_name_error(self, api_name: str, label: str) -> str | None:
        if not api_name:
            return self.app._t("data_dictionary_virtual_error_api_name_required")
        if any(character.isspace() for character in api_name):
            return self.app._t("data_dictionary_virtual_error_api_name_whitespace")
        if not label:
            return self.app._t("data_dictionary_virtual_error_label_required")
        return None

    def _virtual_object_error(self, api_name: str, label: str) -> str | None:
        error = self._virtual_name_error(api_name, label)
        if error:
            return error
        if api_name in self.virtual_objects:
            return self.app._t("data_dictionary_virtual_error_object_duplicate", name=api_name)
        if api_name in self._metadata_objects:
            return self.app._t("data_dictionary_virtual_error_object_exists", name=api_name)
        return None

    def _virtual_field_error(
        self, obj: str, api_name: str, label: str, field_type: str
    ) -> str | None:
        error = self._virtual_name_error(api_name, label)
        if error:
            return error
        if not field_type:
            return self.app._t("data_dictionary_virtual_error_type_required")
        if api_name in self.virtual_fields.get(obj, {}):
            return self.app._t("data_dictionary_virtual_error_field_duplicate", name=api_name)
        if any(api_name == real for real, _label in self._real_object_fields(obj)):
            return self.app._t("data_dictionary_virtual_error_field_exists", name=api_name)
        return None

    # ------------------------------------------------------------ mutation

    def _create_virtual_object(self, api_name: str, label: str, comment: str = "") -> None:
        self.virtual_objects[api_name] = {"label": label}
        self.object_status[api_name] = IN_DESIGN_STATUS
        # Only a non-empty comment is stored, as ``_save_comment`` does, so the
        # mapping never carries empty values.
        if comment:
            self.object_comments[api_name] = comment
        self.selected_objects.add(api_name)
        if api_name not in self.all_objects:
            self.all_objects = sorted([*self.all_objects, api_name])
        self._persist_virtual_entries()
        self._persist_comments()
        self.app.settings["dd_selected_objects"] = list(self.selected_objects)
        self.app._save_settings()

    def _create_virtual_field(
        self, obj: str, api_name: str, label: str, field_type: str, comment: str = ""
    ) -> None:
        self.virtual_fields.setdefault(obj, {})[api_name] = {
            "label": label,
            "type": field_type,
        }
        self.field_status.setdefault(obj, {})[api_name] = IN_DESIGN_STATUS
        # Only a non-empty comment is stored, as ``_save_field_comment`` does,
        # which also means the object key itself stays out when there is none.
        if comment:
            self.field_comments.setdefault(obj, {})[api_name] = comment
        self._persist_virtual_entries()
        self._persist_field_comments()

    def _delete_virtual_object(self, obj: str) -> None:
        self.virtual_objects.pop(obj, None)
        self.virtual_fields.pop(obj, None)
        self.object_status.pop(obj, None)
        self.object_comments.pop(obj, None)
        self.object_piloted_by.pop(obj, None)
        self.object_squad.pop(obj, None)
        self.object_squad_consumer.pop(obj, None)
        self.field_status.pop(obj, None)
        self.field_comments.pop(obj, None)
        self.field_piloted_by.pop(obj, None)
        self.selected_objects.discard(obj)
        if obj in self.all_objects:
            self.all_objects = [name for name in self.all_objects if name != obj]
        self._persist_virtual_entries()
        self._persist_comments()
        self._persist_field_comments()
        self.app.settings["dd_selected_objects"] = list(self.selected_objects)
        self.app._save_settings()

    def _delete_virtual_field(self, obj: str, field_api_name: str) -> None:
        self.virtual_fields.get(obj, {}).pop(field_api_name, None)
        self.field_status.get(obj, {}).pop(field_api_name, None)
        self.field_comments.get(obj, {}).pop(field_api_name, None)
        self.field_piloted_by.get(obj, {}).pop(field_api_name, None)
        self._persist_virtual_entries()
        self._persist_field_comments()

    # ----------------------------------------------------------- promotion

    def _promote_virtual_entries(self) -> tuple[list[str], dict[str, list[str]]]:
        """Move to "Livré" every virtual entry the metadata now contains.

        Unconditional: the metadata is ground truth, so a status the user
        had meanwhile set by hand is overwritten.
        """
        promoted_objects = [
            api_name
            for api_name in sorted(self.virtual_objects)
            if api_name in self._metadata_objects
        ]
        for api_name in promoted_objects:
            del self.virtual_objects[api_name]
            self.object_status[api_name] = DELIVERED_STATUS

        promoted_fields: dict[str, list[str]] = {}
        for obj in sorted(self.virtual_fields):
            if obj not in self._metadata_objects:
                continue
            real_names = {api_name for api_name, _label in self._real_object_fields(obj)}
            moved = sorted(
                api_name for api_name in self.virtual_fields[obj] if api_name in real_names
            )
            for api_name in moved:
                del self.virtual_fields[obj][api_name]
                self.field_status.setdefault(obj, {})[api_name] = DELIVERED_STATUS
            if moved:
                promoted_fields[obj] = moved

        if promoted_objects or promoted_fields:
            self._persist_virtual_entries()
            self._persist_comments()
            self._persist_field_comments()
        return promoted_objects, promoted_fields

    def _promote_virtual_entries_and_report(self) -> None:
        promoted_objects, promoted_fields = self._promote_virtual_entries()
        if not promoted_objects and not promoted_fields:
            return
        messagebox.showinfo(
            self.app._t("data_dictionary_virtual_promoted_title"),
            _promotion_recap(self.app, promoted_objects, promoted_fields),
        )

    # --------------------------------------------------------- persistence

    def _persist_virtual_entries(self) -> None:
        self.app.settings["dd_virtual_objects"] = {
            obj: dict(info) for obj, info in self.virtual_objects.items()
        }
        self.app.settings["dd_virtual_fields"] = {
            obj: {name: dict(info) for name, info in fields.items()}
            for obj, fields in self.virtual_fields.items()
        }
        self.app._save_settings()

    # -------------------------------------------------------------- dialogs

    def _add_virtual_object(self) -> None:
        dialog = _VirtualEntryDialog(
            self.window,
            self.app,
            self.app._t("data_dictionary_virtual_object_dialog_title"),
            [
                ("api_name", self.app._t("data_dictionary_virtual_api_name_label"), None),
                ("label", self.app._t("data_dictionary_virtual_label_label"), None),
                ("comment", self.app._t("data_dictionary_virtual_comment_label"), None),
            ],
            lambda values: self._virtual_object_error(values["api_name"], values["label"]),
        )
        if not dialog.result:
            return

        api_name = dialog.result["api_name"]
        self._create_virtual_object(
            api_name, dialog.result["label"], dialog.result["comment"]
        )
        self._refresh_lists()
        self._set_comment_target(api_name)

    def _add_virtual_field(self) -> None:
        obj = self.current_comment_object
        if not obj:
            messagebox.showinfo(
                self.app._t("info_title"),
                self.app._t("data_dictionary_virtual_field_no_object"),
            )
            return

        dialog = _VirtualEntryDialog(
            self.window,
            self.app,
            self.app._t("data_dictionary_virtual_field_dialog_title"),
            [
                ("api_name", self.app._t("data_dictionary_virtual_api_name_label"), None),
                ("label", self.app._t("data_dictionary_virtual_label_label"), None),
                ("type", self.app._t("data_dictionary_virtual_type_label"), VIRTUAL_FIELD_TYPES),
                ("comment", self.app._t("data_dictionary_virtual_comment_label"), None),
            ],
            lambda values: self._virtual_field_error(
                obj, values["api_name"], values["label"], values["type"]
            ),
        )
        if not dialog.result:
            return

        api_name = dialog.result["api_name"]
        self._create_virtual_field(
            obj,
            api_name,
            dialog.result["label"],
            dialog.result["type"],
            dialog.result["comment"],
        )
        self._refresh_fields_list(obj)
        self._refresh_selected_list()
        self.fields_tree.selection_set(api_name)
