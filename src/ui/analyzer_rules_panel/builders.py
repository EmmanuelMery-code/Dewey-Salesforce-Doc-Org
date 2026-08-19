"""Widget builders for the analyzer-rules panel (header, controls, panes)."""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import TYPE_CHECKING

from src.ui.analyzer_rules_panel.helpers import (
    _open_selected_reference,
    _set_detail_text,
    _severity_display,
)
from src.ui.analyzer_rules_panel.logic import (
    _apply_filters,
    _reload_rules,
    _set_all_api_versions,
    _set_all_rules,
)
from src.ui import theme

if TYPE_CHECKING:
    from src.ui.application import Application


def _build_header(app: Application, parent: ttk.Frame) -> None:
    header = ttk.Frame(parent)
    header.pack(fill="x", pady=(0, theme.SPACE_SM))
    ttk.Label(
        header,
        text=app._t("configuration_rules_title"),
        style=theme.SECTION_LABEL,
    ).pack(anchor="w")
    ttk.Label(
        header,
        text=app._t("configuration_rules_description"),
        wraplength=880,
        justify="left",
    ).pack(anchor="w", pady=(theme.SPACE_XS, theme.SPACE_SM))


def _build_file_row(app: Application, parent: ttk.Frame) -> None:
    file_row = ttk.Frame(parent)
    file_row.pack(fill="x", pady=(0, theme.SPACE_SM))
    ttk.Label(
        file_row,
        text=app._t("configuration_rules_file_label"),
        font=("Segoe UI", 9, "bold"),
    ).pack(side="left")
    ttk.Label(
        file_row,
        text=str(app._analyzer_rules_file),
        style=theme.MUTED_LABEL,
    ).pack(side="left", padx=(theme.SPACE_SM, 0))


def _build_controls(app: Application, parent: ttk.Frame) -> None:
    controls = ttk.Frame(parent)
    controls.pack(fill="x", pady=(0, theme.SPACE_SM))
    ttk.Button(
        controls,
        text=app._t("configuration_rules_enable_all"),
        command=lambda: _set_all_rules(app, True),
    ).pack(side="left")
    ttk.Button(
        controls,
        text=app._t("configuration_rules_disable_all"),
        command=lambda: _set_all_rules(app, False),
    ).pack(side="left", padx=(theme.SPACE_SM, 0))
    ttk.Button(
        controls,
        text=app._t("configuration_rules_reload"),
        command=lambda: _reload_rules(app),
    ).pack(side="left", padx=(theme.SPACE_SM, 0))
    ttk.Button(
        controls,
        text=app._t("configuration_rules_set_all_min"),
        command=lambda: _set_all_api_versions(app, "min"),
    ).pack(side="left", padx=(theme.SPACE_SM, 0))
    ttk.Button(
        controls,
        text=app._t("configuration_rules_set_all_max"),
        command=lambda: _set_all_api_versions(app, "max"),
    ).pack(side="left", padx=(theme.SPACE_SM, 0))

    count_var = tk.StringVar(value="")
    app._analyzer_rule_count_var = count_var
    ttk.Label(controls, textvariable=count_var, style=theme.MUTED_LABEL).pack(side="right")


def _build_filters(app: Application, filters: ttk.Frame) -> ttk.Combobox:
    severities = [app._t("configuration_rules_filter_all")] + [
        _severity_display(app, level) for level in app.ANALYZER_SEVERITY_ORDER
    ]
    app._analyzer_rule_filter_severity = tk.StringVar(value=severities[0])
    _filter_combo_row(
        filters,
        app._t("configuration_rules_filter_severity"),
        app._analyzer_rule_filter_severity,
        severities,
    )

    categories = [app._t("configuration_rules_filter_all"), "Trusted", "Easy", "Adaptable"]
    app._analyzer_rule_filter_category = tk.StringVar(value=categories[0])
    _filter_combo_row(
        filters,
        app._t("configuration_rules_filter_category"),
        app._analyzer_rule_filter_category,
        categories,
    )

    scopes_labels = [app._t("configuration_rules_filter_all")]
    app._analyzer_rule_filter_scope = tk.StringVar(value=scopes_labels[0])
    scope_combo_container = ttk.Frame(filters)
    scope_combo_container.pack(side="left", padx=(theme.SPACE_SM, 0))
    ttk.Label(
        scope_combo_container,
        text=app._t("configuration_rules_filter_scope"),
    ).pack(side="left")
    scope_combo = ttk.Combobox(
        scope_combo_container,
        textvariable=app._analyzer_rule_filter_scope,
        values=scopes_labels,
        state="readonly",
        width=22,
    )
    scope_combo.pack(side="left", padx=(theme.SPACE_XS, 0))

    for var in (
        app._analyzer_rule_filter_severity,
        app._analyzer_rule_filter_category,
        app._analyzer_rule_filter_scope,
    ):
        var.trace_add("write", lambda *_args: _apply_filters(app))

    return scope_combo


def _filter_combo_row(
    parent: ttk.Frame,
    label_text: str,
    variable: tk.Variable,
    values: list[str],
) -> None:
    container = ttk.Frame(parent)
    container.pack(side="left", padx=(0, theme.SPACE_SM))
    ttk.Label(container, text=label_text).pack(side="left")
    combo = ttk.Combobox(
        container,
        textvariable=variable,
        values=values,
        state="readonly",
        width=18,
    )
    combo.pack(side="left", padx=(theme.SPACE_XS, 0))


def _build_list_pane(app: Application, parent: ttk.Frame) -> ttk.Frame:
    paned = ttk.PanedWindow(parent, orient="vertical")
    paned.pack(fill="both", expand=True)

    list_frame = ttk.Frame(paned)
    paned.add(list_frame, weight=3)

    detail_frame = ttk.LabelFrame(
        paned,
        text=app._t("configuration_rules_detail_title"),
        padding=theme.SPACE_SM,
    )
    paned.add(detail_frame, weight=2)

    list_canvas = tk.Canvas(list_frame, highlightthickness=0, height=280)
    list_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=list_canvas.yview)
    list_inner = ttk.Frame(list_canvas)
    list_inner.bind(
        "<Configure>",
        lambda _e: list_canvas.configure(scrollregion=list_canvas.bbox("all")),
    )
    list_canvas.create_window((0, 0), window=list_inner, anchor="nw")
    list_canvas.configure(yscrollcommand=list_scrollbar.set)
    list_canvas.pack(side="left", fill="both", expand=True)
    list_scrollbar.pack(side="right", fill="y")

    list_canvas.bind(
        "<Enter>",
        lambda _e: list_canvas.bind_all(
            "<MouseWheel>",
            lambda event: list_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"),
        ),
    )
    list_canvas.bind("<Leave>", lambda _e: list_canvas.unbind_all("<MouseWheel>"))

    detail_widget = scrolledtext.ScrolledText(
        detail_frame,
        wrap="word",
        height=9,
        font=("Segoe UI", 9),
        state="disabled",
    )
    detail_widget.pack(fill="both", expand=True)
    app._analyzer_rule_detail_widget = detail_widget
    _set_detail_text(app, app._t("configuration_rules_detail_empty"))

    # API Version fields
    api_version_row = ttk.Frame(detail_frame)
    api_version_row.pack(fill="x", pady=(theme.SPACE_SM, 0))

    ttk.Label(api_version_row, text=app._t("configuration_rules_min_api_version")).pack(side="left")
    app._analyzer_rule_min_api_entry_var = tk.StringVar()
    min_entry = ttk.Entry(api_version_row, textvariable=app._analyzer_rule_min_api_entry_var, width=10)
    min_entry.pack(side="left", padx=(theme.SPACE_XS, theme.SPACE_MD))

    ttk.Label(api_version_row, text=app._t("configuration_rules_max_api_version")).pack(side="left")
    app._analyzer_rule_max_api_entry_var = tk.StringVar()
    max_entry = ttk.Entry(api_version_row, textvariable=app._analyzer_rule_max_api_entry_var, width=10)
    max_entry.pack(side="left", padx=(theme.SPACE_XS, 0))

    # Sync entry fields back to the rule-specific vars
    def _sync_min(*_args):
        rule_id = getattr(app, "_analyzer_rule_selected_id", None)
        if rule_id and rule_id in app._analyzer_rule_min_api_vars:
            app._analyzer_rule_min_api_vars[rule_id].set(app._analyzer_rule_min_api_entry_var.get())

    def _sync_max(*_args):
        rule_id = getattr(app, "_analyzer_rule_selected_id", None)
        if rule_id and rule_id in app._analyzer_rule_max_api_vars:
            app._analyzer_rule_max_api_vars[rule_id].set(app._analyzer_rule_max_api_entry_var.get())

    app._analyzer_rule_min_api_entry_var.trace_add("write", _sync_min)
    app._analyzer_rule_max_api_entry_var.trace_add("write", _sync_max)

    ref_row = ttk.Frame(detail_frame)
    ref_row.pack(fill="x", pady=(theme.SPACE_SM, 0))
    app._analyzer_rule_selected_reference = ""
    ttk.Button(
        ref_row,
        text=app._t("configuration_rules_detail_open_reference"),
        command=lambda: _open_selected_reference(app),
    ).pack(side="right")

    app._analyzer_rule_vars = {}
    app._analyzer_rule_rows = []
    return list_inner
