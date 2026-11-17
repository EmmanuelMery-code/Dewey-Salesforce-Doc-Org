"""Onglet de configuration Nebula Logger : interrupteur, format et tags."""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import TYPE_CHECKING

from src.analyzer.nebula_config import DEFAULT_NEBULA_LOG_FORMAT, DEFAULT_NEBULA_TAGS
from src.ui import theme

if TYPE_CHECKING:
    from src.ui.application import Application


def build_panel(app: "Application", parent: ttk.Frame) -> None:
    """Affiche l'onglet Nebula et garde les widgets sur l'application."""

    ttk.Label(
        parent,
        text=app._t("configuration_nebula_title"),
        style=theme.SECTION_LABEL,
    ).pack(anchor="w", pady=(0, theme.SPACE_XS))
    ttk.Label(
        parent,
        text=app._t("configuration_nebula_description"),
        wraplength=820,
        justify="left",
    ).pack(anchor="w", pady=(0, theme.SPACE_SM))

    enabled = tk.BooleanVar(value=bool(app.nebula_rules_enabled))
    ttk.Checkbutton(
        parent,
        text=app._t("configuration_nebula_enabled"),
        variable=enabled,
        command=lambda: _apply_master_switch(app, bool(enabled.get())),
    ).pack(anchor="w", pady=(0, theme.SPACE_SM))

    ttk.Label(parent, text=app._t("configuration_nebula_format_label")).pack(anchor="w")
    format_var = tk.StringVar(value=app.nebula_log_format)
    ttk.Entry(parent, textvariable=format_var).pack(fill="x", pady=(theme.SPACE_XS, 0))
    format_row = ttk.Frame(parent)
    format_row.pack(fill="x", pady=(theme.SPACE_XS, 0))
    ttk.Button(
        format_row,
        text=app._t("configuration_nebula_format_reset"),
        command=lambda: format_var.set(DEFAULT_NEBULA_LOG_FORMAT),
    ).pack(side="left")
    ttk.Label(
        parent,
        text=app._t("configuration_nebula_format_hint"),
        wraplength=820,
        justify="left",
        style=theme.MUTED_LABEL,
    ).pack(anchor="w", pady=(theme.SPACE_XS, theme.SPACE_SM))

    ttk.Label(parent, text=app._t("configuration_nebula_tags_label")).pack(anchor="w")
    list_frame = ttk.Frame(parent)
    list_frame.pack(fill="both", expand=True, pady=(theme.SPACE_XS, 0))
    listbox = tk.Listbox(list_frame, height=8, exportselection=False)
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
    scrollbar.pack(side="right", fill="y")
    listbox.configure(yscrollcommand=scrollbar.set)
    for tag in app.nebula_tags:
        listbox.insert(tk.END, tag)

    button_row = ttk.Frame(parent)
    button_row.pack(fill="x", pady=(theme.SPACE_SM, 0))
    ttk.Button(
        button_row,
        text=app._t("configuration_nebula_tags_add"),
        command=lambda: _add_tag(app, listbox),
    ).pack(side="left")
    ttk.Button(
        button_row,
        text=app._t("configuration_nebula_tags_edit"),
        command=lambda: _edit_tag(app, listbox),
    ).pack(side="left", padx=(theme.SPACE_SM, 0))
    ttk.Button(
        button_row,
        style=theme.DANGER_BUTTON,
        text=app._t("configuration_nebula_tags_remove"),
        command=lambda: _remove_tag(app, listbox),
    ).pack(side="left", padx=(theme.SPACE_SM, 0))
    ttk.Button(
        button_row,
        text=app._t("configuration_nebula_tags_reset"),
        command=lambda: _reset_tags(listbox),
    ).pack(side="right")
    ttk.Label(
        parent,
        text=app._t("configuration_nebula_tags_hint"),
        wraplength=820,
        justify="left",
        style=theme.MUTED_LABEL,
    ).pack(anchor="w", pady=(theme.SPACE_SM, 0))

    app._nebula_enabled_var = enabled
    app._nebula_format_var = format_var
    app._nebula_tags_listbox = listbox


def collect(app: "Application") -> tuple[bool, str, list[str]] | None:
    """Lit le formulaire. Retourne None si l'expression reguliere est invalide."""

    enabled_var = getattr(app, "_nebula_enabled_var", None)
    format_var = getattr(app, "_nebula_format_var", None)
    listbox = getattr(app, "_nebula_tags_listbox", None)
    enabled = bool(enabled_var.get()) if enabled_var is not None else bool(app.nebula_rules_enabled)
    log_format = format_var.get().strip() if format_var is not None else app.nebula_log_format
    if not log_format:
        log_format = DEFAULT_NEBULA_LOG_FORMAT
    if listbox is None:
        tags = list(app.nebula_tags)
    else:
        tags = [str(listbox.get(index)).strip() for index in range(listbox.size())]
        tags = [tag for tag in tags if tag]
    try:
        re.compile(log_format)
    except re.error as exc:
        messagebox.showerror(
            app._t("configuration_nebula_format_invalid_title"),
            app._t("configuration_nebula_format_invalid", error=str(exc)),
            parent=app.configuration_window or app,
        )
        return None
    return enabled, log_format, tags


def apply_disabled_rules(app: "Application") -> None:
    """Quand l'interrupteur est coupe, decoche toutes les regles Nebula."""

    enabled_var = getattr(app, "_nebula_enabled_var", None)
    if enabled_var is None or bool(enabled_var.get()):
        return
    _apply_master_switch(app, False)


def reset_state(app: "Application") -> None:
    app._nebula_enabled_var = None
    app._nebula_format_var = None
    app._nebula_tags_listbox = None


def _apply_master_switch(app: "Application", enabled: bool) -> None:
    for rule_id, var in getattr(app, "_analyzer_rule_vars", {}).items():
        if rule_id.startswith("NEBULA-"):
            var.set(enabled)


def _read_tags(listbox: tk.Listbox) -> set[str]:
    return {str(listbox.get(index)).strip().casefold() for index in range(listbox.size())}


def _ask_tag(app: "Application", title: str, initial: str = "") -> str | None:
    value = simpledialog.askstring(
        title,
        app._t("configuration_nebula_tags_prompt"),
        initialvalue=initial,
        parent=app.configuration_window or app,
    )
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _add_tag(app: "Application", listbox: tk.Listbox) -> None:
    new_value = _ask_tag(app, app._t("configuration_nebula_tags_add"))
    if new_value is None:
        return
    if new_value.casefold() in _read_tags(listbox):
        messagebox.showwarning(
            app._t("info_title"),
            app._t("configuration_nebula_tags_duplicate"),
            parent=app.configuration_window or app,
        )
        return
    listbox.insert(tk.END, new_value)


def _edit_tag(app: "Application", listbox: tk.Listbox) -> None:
    selection = listbox.curselection()
    if not selection:
        messagebox.showinfo(
            app._t("info_title"),
            app._t("configuration_nebula_tags_select_first"),
            parent=app.configuration_window or app,
        )
        return
    index = selection[0]
    new_value = _ask_tag(
        app, app._t("configuration_nebula_tags_edit"), initial=str(listbox.get(index))
    )
    if new_value is None:
        return
    others = _read_tags(listbox)
    others.discard(str(listbox.get(index)).strip().casefold())
    if new_value.casefold() in others:
        messagebox.showwarning(
            app._t("info_title"),
            app._t("configuration_nebula_tags_duplicate"),
            parent=app.configuration_window or app,
        )
        return
    listbox.delete(index)
    listbox.insert(index, new_value)


def _remove_tag(app: "Application", listbox: tk.Listbox) -> None:
    selection = listbox.curselection()
    if not selection:
        messagebox.showinfo(
            app._t("info_title"),
            app._t("configuration_nebula_tags_select_first"),
            parent=app.configuration_window or app,
        )
        return
    listbox.delete(selection[0])


def _reset_tags(listbox: tk.Listbox) -> None:
    listbox.delete(0, tk.END)
    for tag in DEFAULT_NEBULA_TAGS:
        listbox.insert(tk.END, tag)
