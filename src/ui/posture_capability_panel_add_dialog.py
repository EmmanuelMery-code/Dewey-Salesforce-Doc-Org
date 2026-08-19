"""Modal dialog to add a custom posture capability.

Extracted from :mod:`src.ui.posture_capability_panel` to keep that module
under the repository's line-count budget. Holds the "Add capability" dialog
itself plus the metadata-suggestion helpers it relies on (suggesting a
level from a snapshot metric count, generating a unique capability id).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from src.core.customization_metrics import (
    CAPABILITY_CATALOG,
    CAPABILITY_LEVEL_ORDER,
    CapabilityLevel,
    PostureCapabilityConfig,
    SNAPSHOT_METRIC_KEYS,
)
from src.ui import theme

if TYPE_CHECKING:
    from src.ui.application import Application


def _add_capability_dialog(app: "Application") -> None:
    """Open a small modal that walks the user through adding a capability.

    The dialog suggests metadata-backed counters (custom objects, flows,
    Apex classes, LWC, ...) so the new capability is grounded in the
    snapshot. The user can also leave the metadata empty to add a
    label-only capability.
    """

    from src.ui.posture_capability_panel import (
        _level_display,
        _render_table,
        collect_config,
    )

    used_labels: set[str] = {
        entry.label.casefold() for entry in collect_config(app) if entry.label
    }

    parent = app.configuration_window or app
    dialog = tk.Toplevel(parent)
    dialog.title(app._t("configuration_posture_add_title"))
    dialog.geometry("520x420")
    dialog.transient(parent)
    dialog.grab_set()

    container = ttk.Frame(dialog, padding=theme.SPACE_LG)
    container.pack(fill="both", expand=True)

    ttk.Label(
        container,
        text=app._t("configuration_posture_add_description"),
        wraplength=480,
        justify="left",
    ).pack(anchor="w", pady=(0, theme.SPACE_MD))

    label_frame = ttk.Frame(container)
    label_frame.pack(fill="x", pady=(0, theme.SPACE_SM))
    ttk.Label(label_frame, text=app._t("configuration_posture_field_label"), width=22).pack(side="left")
    label_var = tk.StringVar()
    ttk.Entry(label_frame, textvariable=label_var).pack(
        side="left", fill="x", expand=True
    )

    metric_frame = ttk.Frame(container)
    metric_frame.pack(fill="x", pady=(0, theme.SPACE_SM))
    ttk.Label(
        metric_frame, text=app._t("configuration_posture_field_metadata"), width=22
    ).pack(side="left")
    metric_choices = [app._t("configuration_posture_metadata_none")]
    metric_keys: list[str] = [""]
    metrics = getattr(app, "latest_metrics", None)
    for key, label in SNAPSHOT_METRIC_KEYS.items():
        count = snapshot_metric_count_safe(metrics, key)
        if metrics is not None:
            metric_choices.append(f"{label}  ({count})")
        else:
            metric_choices.append(label)
        metric_keys.append(key)
    metric_var = tk.StringVar(value=metric_choices[0])
    metric_combo = ttk.Combobox(
        metric_frame, textvariable=metric_var, values=metric_choices, state="readonly", width=30
    )
    metric_combo.pack(side="left", fill="x", expand=True)

    weight_frame = ttk.Frame(container)
    weight_frame.pack(fill="x", pady=(0, theme.SPACE_SM))
    ttk.Label(
        weight_frame, text=app._t("configuration_posture_field_weight"), width=22
    ).pack(side="left")
    weight_var = tk.StringVar(value="2")
    ttk.Entry(weight_frame, textvariable=weight_var, width=6).pack(side="left")

    level_frame = ttk.Frame(container)
    level_frame.pack(fill="x", pady=(0, theme.SPACE_SM))
    ttk.Label(
        level_frame, text=app._t("configuration_posture_field_level"), width=22
    ).pack(side="left")
    level_choices = [_level_display(app, level) for level in CAPABILITY_LEVEL_ORDER]
    level_var = tk.StringVar(value=level_choices[0])
    ttk.Combobox(
        level_frame,
        textvariable=level_var,
        values=level_choices,
        state="readonly",
        width=30,
    ).pack(side="left", fill="x", expand=True)

    suggestion_label = ttk.Label(
        container,
        text="",
        wraplength=480,
        justify="left",
        style=theme.MUTED_LABEL,
    )
    suggestion_label.pack(anchor="w", pady=(theme.SPACE_XS, theme.SPACE_SM))

    def _apply_suggestion(*_args: object) -> None:
        try:
            index = metric_choices.index(metric_var.get())
        except ValueError:
            return
        key = metric_keys[index]
        if not key:
            suggestion_label.configure(text="")
            return
        if not label_var.get().strip():
            label_var.set(SNAPSHOT_METRIC_KEYS[key])
        count = snapshot_metric_count_safe(metrics, key)
        if metrics is None:
            suggestion_label.configure(
                text=app._t("configuration_posture_suggestion_no_metrics")
            )
            return
        suggested = _suggest_level(count)
        level_var.set(_level_display(app, suggested))
        suggestion_label.configure(
            text=app._t(
                "configuration_posture_suggestion",
                count=count,
                level=_level_display(app, suggested),
            )
        )

    metric_var.trace_add("write", _apply_suggestion)

    button_row = ttk.Frame(container)
    button_row.pack(fill="x", pady=(theme.SPACE_SM, 0))

    def _save() -> None:
        raw_label = label_var.get().strip()
        if not raw_label:
            messagebox.showerror(
                app._t("error_title"),
                app._t("configuration_posture_label_required"),
                parent=dialog,
            )
            return
        if raw_label.casefold() in used_labels:
            messagebox.showerror(
                app._t("error_title"),
                app._t("configuration_posture_label_duplicate"),
                parent=dialog,
            )
            return
        weight_text = weight_var.get().strip()
        if not weight_text.lstrip("-").isdigit() or int(weight_text) < 0:
            messagebox.showerror(
                app._t("error_title"),
                app._t("configuration_posture_invalid_weight"),
                parent=dialog,
            )
            return
        try:
            metric_index = metric_choices.index(metric_var.get())
        except ValueError:
            metric_index = 0
        metadata_key = metric_keys[metric_index]
        level = None
        for level_candidate in CAPABILITY_LEVEL_ORDER:
            if _level_display(app, level_candidate) == level_var.get():
                level = level_candidate
                break
        if level is None:
            level = CapabilityLevel.ADOPT
        new_id = _build_custom_id(app, raw_label)
        new_entry = PostureCapabilityConfig(
            capability_id=new_id,
            label=raw_label,
            weight=int(weight_text),
            level=level,
            custom=True,
            metadata_key=metadata_key,
        )
        app.posture_config = collect_config(app) + [new_entry]
        _render_table(app)
        dialog.destroy()

    ttk.Button(button_row, text=app._t("configuration_save"), command=_save, style=theme.PRIMARY_BUTTON).pack(
        side="right"
    )
    ttk.Button(button_row, text=app._t("configuration_cancel"), command=dialog.destroy).pack(
        side="right", padx=(0, theme.SPACE_SM)
    )

    dialog.focus_set()


def snapshot_metric_count_safe(metrics: object, key: str) -> int:
    if metrics is None:
        return 0
    value = getattr(metrics, key, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _suggest_level(count: int) -> CapabilityLevel:
    if count <= 0:
        return CapabilityLevel.ADOPT
    if count <= 5:
        return CapabilityLevel.ADAPT_LOW
    return CapabilityLevel.ADAPT_HIGH


def _build_custom_id(app: "Application", label: str) -> str:
    from src.ui.posture_capability_panel import collect_config

    used_ids: set[str] = {entry.capability_id for entry in collect_config(app)}
    used_ids.update(d.capability_id for d in CAPABILITY_CATALOG)
    base = "custom_" + "".join(
        ch.lower() if ch.isalnum() else "_" for ch in label
    ).strip("_") or "custom_capability"
    candidate = base
    suffix = 2
    while candidate in used_ids:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate
