"""Public entry points for the analyzer-rules configuration tab."""

from __future__ import annotations

import re
from tkinter import ttk
from typing import TYPE_CHECKING

from src.ui.analyzer_rules_panel.builders import (
    _build_controls,
    _build_file_row,
    _build_filters,
    _build_header,
    _build_list_pane,
)
from src.ui.analyzer_rules_panel.helpers import _refresh_rule_count, _scope_display
from src.ui.analyzer_rules_panel.logic import (
    _load_rules_for_editor,
    _render_rule_rows,
)
from src.ui import theme

if TYPE_CHECKING:
    from src.ui.application import Application


def build_panel(app: Application, parent: ttk.Frame) -> None:
    """Render the analyzer-rules tab into ``parent``."""

    _build_header(app, parent)
    _build_file_row(app, parent)
    _build_controls(app, parent)
    filters = ttk.Frame(parent)
    filters.pack(fill="x", pady=(0, theme.SPACE_SM))
    scope_combo = _build_filters(app, filters)

    list_inner = _build_list_pane(app, parent)

    rules = _load_rules_for_editor(app)
    app._analyzer_rules_cache = rules

    scopes_seen = sorted({rule.scope for rule in rules})
    scope_combo.configure(
        values=[app._t("configuration_rules_filter_all")]
        + [_scope_display(app, scope) for scope in scopes_seen]
    )

    _render_rule_rows(app, list_inner, rules)
    _refresh_rule_count(app)


def persist_changes(app: Application) -> None:
    """Persist enabled/disabled state of every rule to ``rules.xml``."""

    if not app._analyzer_rule_vars:
        return
    path = app._analyzer_rules_file
    if not path.exists():
        app._append_log(app._t("configuration_rules_file_missing", path=str(path)))
        return
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        app._append_log(app._t("configuration_rules_load_error", error=str(exc)))
        return

    changes = 0
    updated = raw
    for rule in app._analyzer_rules_cache:
        var = app._analyzer_rule_vars.get(rule.id)
        min_var = app._analyzer_rule_min_api_vars.get(rule.id)
        max_var = app._analyzer_rule_max_api_vars.get(rule.id)

        if var is None:
            continue

        desired_enabled = "true" if bool(var.get()) else "false"
        desired_min = min_var.get().strip() if min_var else ""
        desired_max = max_var.get().strip() if max_var else ""

        # Find the rule start tag
        rule_pattern = re.compile(
            r'(<rule\s+id="' + re.escape(rule.id) + r'"[^>]*?>)',
            re.DOTALL,
        )

        match = rule_pattern.search(updated)
        if not match:
            continue

        tag = match.group(1)
        new_tag = tag

        # Update enabled
        if 'enabled="' in new_tag:
            new_tag = re.sub(r'enabled="[^"]*"', f'enabled="{desired_enabled}"', new_tag)
        else:
            # Insert after <rule
            new_tag = re.sub(r'<rule', f'<rule enabled="{desired_enabled}"', new_tag)

        # Update min_api_version
        if desired_min:
            if 'min_api_version="' in new_tag:
                new_tag = re.sub(r'min_api_version="[^"]*"', f'min_api_version="{desired_min}"', new_tag)
            else:
                # Add before the closing >
                new_tag = new_tag[:-1] + f' min_api_version="{desired_min}">'
        elif 'min_api_version="' in new_tag:
            # Remove it if empty
            new_tag = re.sub(r'\s*min_api_version="[^"]*"', '', new_tag)

        # Update max_api_version
        if desired_max:
            if 'max_api_version="' in new_tag:
                new_tag = re.sub(r'max_api_version="[^"]*"', f'max_api_version="{desired_max}"', new_tag)
            else:
                new_tag = new_tag[:-1] + f' max_api_version="{desired_max}">'
        elif 'max_api_version="' in new_tag:
            new_tag = re.sub(r'\s*max_api_version="[^"]*"', '', new_tag)

        if new_tag != tag:
            # Use the match span to replace only this specific occurrence
            updated = updated[:match.start()] + new_tag + updated[match.end():]
            changes += 1
    if changes == 0:
        return
    try:
        path.write_text(updated, encoding="utf-8")
    except OSError as exc:
        app._append_log(app._t("configuration_rules_write_error", error=str(exc)))
        return
    app._append_log(
        app._t("configuration_rules_saved", path=str(path), count=changes)
    )


def reset_state(app: Application) -> None:
    """Clear panel state held on the app instance.

    Called after the configuration window closes to release Tk widget
    references that would otherwise outlive the window.
    """

    app._analyzer_rule_vars = {}
    app._analyzer_rule_min_api_vars = {}
    app._analyzer_rule_max_api_vars = {}
    app._analyzer_rules_cache = []
    app._analyzer_rule_rows = []
    app._analyzer_rule_selected_id = None
    app._analyzer_rule_count_var = None
    app._analyzer_rule_min_api_entry_var = None
    app._analyzer_rule_max_api_entry_var = None
    app._analyzer_rule_detail_widget = None
    app._analyzer_rule_filter_severity = None
    app._analyzer_rule_filter_category = None
    app._analyzer_rule_filter_scope = None
