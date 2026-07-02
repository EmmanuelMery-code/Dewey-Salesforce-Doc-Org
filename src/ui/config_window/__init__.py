"""Configuration window for the Salesforce documentation generator.

The window is assembled from thematic modules (tab builders, row widgets and
the save handler). The public entry point ``show_configuration_screen`` is
re-exported here so existing ``from src.ui.config_window import
show_configuration_screen`` call sites keep working unchanged.
"""

from __future__ import annotations

from src.ui.config_window.window import show_configuration_screen

__all__ = ["show_configuration_screen"]
