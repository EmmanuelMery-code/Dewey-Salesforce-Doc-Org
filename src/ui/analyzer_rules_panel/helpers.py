"""Leaf helpers for the analyzer-rules panel (display, filtering, counting)."""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING

from src.analyzer.models import Rule

if TYPE_CHECKING:
    from src.ui.application import Application


def _severity_display(app: Application, severity: str) -> str:
    return app._t(f"configuration_rules_severity_{severity.lower()}")


def _severity_code_from_display(app: Application, display: str) -> str | None:
    for level in app.ANALYZER_SEVERITY_ORDER:
        if _severity_display(app, level) == display:
            return level
    return None


def _scope_display(app: Application, scope: str) -> str:
    key = f"configuration_rules_scope_{scope}"
    translated = app._t(key)
    if translated == key:
        return scope
    return translated


def _scope_code_from_display(app: Application, display: str) -> str | None:
    for rule in app._analyzer_rules_cache:
        if _scope_display(app, rule.scope) == display:
            return rule.scope
    return None


def _set_detail_text(app: Application, text: str) -> None:
    widget = app._analyzer_rule_detail_widget
    if widget is None:
        return
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", text)
    widget.configure(state="disabled")


def _open_selected_reference(app: Application) -> None:
    reference = app._analyzer_rule_selected_reference
    if not reference:
        return
    try:
        webbrowser.open(reference)
    except Exception as exc:  # pragma: no cover - browser-dependent
        app._append_log(f"{exc}")


def _rule_visible(app: Application, rule: Rule) -> bool:
    all_label = app._t("configuration_rules_filter_all")
    if app._analyzer_rule_filter_severity is not None:
        chosen = app._analyzer_rule_filter_severity.get()
        if chosen and chosen != all_label:
            code = _severity_code_from_display(app, chosen)
            if code and rule.severity != code:
                return False
    if app._analyzer_rule_filter_category is not None:
        chosen = app._analyzer_rule_filter_category.get()
        if chosen and chosen != all_label and rule.category != chosen:
            return False
    if app._analyzer_rule_filter_scope is not None:
        chosen = app._analyzer_rule_filter_scope.get()
        if chosen and chosen != all_label:
            code = _scope_code_from_display(app, chosen)
            if code and rule.scope != code:
                return False
    return True


def _refresh_rule_count(app: Application) -> None:
    var = app._analyzer_rule_count_var
    if var is None:
        return
    total = len(app._analyzer_rule_vars)
    enabled = sum(1 for v in app._analyzer_rule_vars.values() if v.get())
    var.set(
        app._t("configuration_rules_enabled_count", enabled=enabled, total=total)
    )
