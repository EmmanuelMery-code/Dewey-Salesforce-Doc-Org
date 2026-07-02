"""Screen to view and manage generation history.

The window (``show_history_screen``) and its modal dialogs live in dedicated
modules; the public entry point is re-exported here so existing
``from src.ui.history_screen import show_history_screen`` call sites keep
working unchanged.
"""

from __future__ import annotations

from src.ui.history_screen.screen import show_history_screen

__all__ = ["show_history_screen"]
