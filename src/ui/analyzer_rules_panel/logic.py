"""Rule loading, row rendering, selection, filtering and bulk actions."""

from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog, ttk
from typing import TYPE_CHECKING

from src.analyzer.models import Rule
from src.analyzer.rule_catalog import RuleCatalog
from src.ui.analyzer_rules_panel.helpers import (
    _refresh_rule_count,
    _rule_visible,
    _scope_display,
    _set_detail_text,
    _severity_display,
)

if TYPE_CHECKING:
    from src.ui.application import Application


def _load_rules_for_editor(app: Application) -> list[Rule]:
    try:
        catalog = RuleCatalog.load(app._analyzer_rules_file)
    except OSError as exc:
        app._append_log(app._t("configuration_rules_load_error", error=str(exc)))
        return []
    except Exception as exc:  # parse errors
        app._append_log(app._t("configuration_rules_load_error", error=str(exc)))
        return []
    if not app._analyzer_rules_file.exists():
        app._append_log(
            app._t("configuration_rules_file_missing", path=str(app._analyzer_rules_file))
        )
    return catalog.all


def _render_rule_rows(app: Application, parent: ttk.Frame, rules: list[Rule]) -> None:
    for child in parent.winfo_children():
        child.destroy()
    app._analyzer_rule_rows = []
    app._analyzer_rule_vars = {}

    grouped: dict[str, list[Rule]] = {}
    for rule in rules:
        grouped.setdefault(rule.scope, []).append(rule)
    for scope_rules in grouped.values():
        scope_rules.sort(
            key=lambda r: (
                app.ANALYZER_SEVERITY_ORDER.index(r.severity)
                if r.severity in app.ANALYZER_SEVERITY_ORDER
                else 99,
                r.id,
            )
        )

    ordered_scopes = sorted(
        grouped.keys(), key=lambda s: _scope_display(app, s).lower()
    )
    for scope in ordered_scopes:
        section = ttk.LabelFrame(parent, text=_scope_display(app, scope), padding=6)
        section.pack(fill="x", pady=(2, 4), padx=2)
        for rule in grouped[scope]:
            _render_single_rule_row(app, section, rule)


def _render_single_rule_row(app: Application, parent: ttk.Frame, rule: Rule) -> None:
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=1)

    var = tk.BooleanVar(value=rule.enabled)
    app._analyzer_rule_vars[rule.id] = var
    var.trace_add("write", lambda *_args: _refresh_rule_count(app))

    # Initialize API version vars with current Salesforce version (60.0) if None
    current_sf_version = "60.0"
    min_val = str(rule.min_api_version) if rule.min_api_version is not None else current_sf_version
    max_val = str(rule.max_api_version) if rule.max_api_version is not None else current_sf_version

    app._analyzer_rule_min_api_vars[rule.id] = tk.StringVar(value=min_val)
    app._analyzer_rule_max_api_vars[rule.id] = tk.StringVar(value=max_val)

    check = ttk.Checkbutton(row, variable=var)
    check.pack(side="left", padx=(0, 4))

    severity_color = app.ANALYZER_SEVERITY_COLORS.get(rule.severity, "#1e293b")
    severity_label = tk.Label(
        row,
        text=_severity_display(app, rule.severity),
        foreground="white",
        background=severity_color,
        font=("Segoe UI", 8, "bold"),
        padx=6,
        pady=1,
    )
    severity_label.pack(side="left", padx=(0, 4))

    id_label = ttk.Label(row, text=rule.id, font=("Consolas", 9), foreground="#334155")
    id_label.pack(side="left", padx=(0, 6))

    title_label = ttk.Label(row, text=rule.title, font=("Segoe UI", 9))
    title_label.pack(side="left", fill="x", expand=True)

    category_text = rule.category
    if rule.subcategory:
        category_text = f"{rule.category} / {rule.subcategory}"
    category_label = ttk.Label(
        row, text=category_text, foreground="#475569", font=("Segoe UI", 8, "italic")
    )
    category_label.pack(side="right", padx=(6, 0))

    def _select(_event=None, _rule: Rule = rule) -> None:
        _select_rule(app, _rule)

    for widget in (row, severity_label, id_label, title_label, category_label):
        widget.bind("<Button-1>", _select)

    app._analyzer_rule_rows.append({"rule": rule, "row": row})


def _select_rule(app: Application, rule: Rule) -> None:
    app._analyzer_rule_selected_id = rule.id
    app._analyzer_rule_selected_reference = rule.reference or ""

    # Update API version entry fields
    if rule.id in app._analyzer_rule_min_api_vars:
        app._analyzer_rule_min_api_entry_var.set(app._analyzer_rule_min_api_vars[rule.id].get())
    if rule.id in app._analyzer_rule_max_api_vars:
        app._analyzer_rule_max_api_entry_var.set(app._analyzer_rule_max_api_vars[rule.id].get())

    lines: list[str] = [f"{rule.id} - {rule.title}", ""]
    lines.append(
        f"{app._t('configuration_rules_column_severity')}: "
        f"{_severity_display(app, rule.severity)}"
    )
    category_text = rule.category
    if rule.subcategory:
        category_text = f"{rule.category} / {rule.subcategory}"
    lines.append(f"{app._t('configuration_rules_column_category')}: {category_text}")
    lines.append("")
    if rule.description:
        lines.append(app._t("configuration_rules_detail_description") + ":")
        lines.append(rule.description)
        lines.append("")
    if rule.rationale:
        lines.append(app._t("configuration_rules_detail_rationale") + ":")
        lines.append(rule.rationale)
        lines.append("")
    if rule.remediation:
        lines.append(app._t("configuration_rules_detail_remediation") + ":")
        lines.append(rule.remediation)
        lines.append("")
    if rule.source:
        lines.append(app._t("configuration_rules_detail_source") + ": " + rule.source)
    if rule.reference:
        lines.append(
            app._t("configuration_rules_detail_reference") + ": " + rule.reference
        )
    _set_detail_text(app, "\n".join(lines))


def _set_all_rules(app: Application, enabled: bool) -> None:
    for rule_id, var in app._analyzer_rule_vars.items():
        rule = next(
            (r for r in app._analyzer_rules_cache if r.id == rule_id), None
        )
        if rule is None:
            continue
        if _rule_visible(app, rule):
            var.set(enabled)


def _apply_filters(app: Application) -> None:
    for entry in app._analyzer_rule_rows:
        rule: Rule = entry["rule"]  # type: ignore[assignment]
        row = entry["row"]
        if _rule_visible(app, rule):
            row.pack(fill="x", pady=1)
        else:
            row.pack_forget()


def _reload_rules(app: Application) -> None:
    if app.configuration_window is None or not app.configuration_window.winfo_exists():
        return
    app.configuration_window.destroy()
    app._append_log(
        app._t("configuration_rules_reloaded", path=str(app._analyzer_rules_file))
    )
    app._show_configuration_screen()


def _set_all_api_versions(app: Application, target: str) -> None:
    """Prompt for a version and apply it to all rules (min or max)."""
    title = app._t(f"configuration_rules_set_all_{target}")
    prompt = app._t("configuration_rules_set_all_prompt")

    new_version = simpledialog.askstring(title, prompt, parent=app.configuration_window)
    if new_version is None: # User cancelled
        return

    new_version = new_version.strip()

    vars_dict = app._analyzer_rule_min_api_vars if target == "min" else app._analyzer_rule_max_api_vars

    for rule_id, var in vars_dict.items():
        var.set(new_version)

    # If a rule is currently selected, update the detail entry field as well
    selected_id = getattr(app, "_analyzer_rule_selected_id", None)
    if selected_id:
        if target == "min":
            app._analyzer_rule_min_api_entry_var.set(new_version)
        else:
            app._analyzer_rule_max_api_entry_var.set(new_version)
