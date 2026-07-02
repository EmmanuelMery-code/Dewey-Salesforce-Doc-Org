"""Configuration tab listing the static-analysis rules.

The panel lets the user enable/disable rules and persist the choice back to
``rules.xml``. The implementation is split into leaf display helpers, the
rule loading/rendering logic and the widget builders. This module exposes only
the three public entry points (``build_panel``, ``persist_changes`` and
``reset_state``); the rest of the logic is internal.
"""

from __future__ import annotations

from src.ui.analyzer_rules_panel.panel import (
    build_panel,
    persist_changes,
    reset_state,
)

__all__ = ["build_panel", "persist_changes", "reset_state"]
