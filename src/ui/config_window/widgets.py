"""Small reusable row helpers for the configuration window."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def config_spinbox_row(
    parent: ttk.Frame,
    label_text: str,
    variable: tk.Variable,
    from_: int,
    to: int,
) -> ttk.Frame:
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=3)
    ttk.Label(row, text=label_text, width=22).pack(side="left")
    spin = ttk.Spinbox(row, from_=from_, to=to, textvariable=variable, width=8)
    spin.pack(side="left")
    return row


def config_entry_row(
    parent: ttk.Frame,
    label_text: str,
    variable: tk.Variable,
    show: str | None = None,
) -> ttk.Frame:
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=3)
    ttk.Label(row, text=label_text, width=22).pack(side="left")
    entry = ttk.Entry(row, textvariable=variable)
    if show is not None:
        entry.configure(show=show)
    entry.pack(side="left", fill="x", expand=True)
    return row


def config_combo_row(
    parent: ttk.Frame,
    label_text: str,
    variable: tk.Variable,
    values: list[str],
) -> ttk.Frame:
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=3)
    ttk.Label(row, text=label_text, width=22).pack(side="left")
    combo = ttk.Combobox(row, textvariable=variable, values=values, state="readonly", width=30)
    combo.pack(side="left", fill="x", expand=True)
    return row
