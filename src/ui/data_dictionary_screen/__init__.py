"""Data Dictionary creation screen.

The window (``show_data_dictionary_screen``) and its mixins live in
dedicated modules; the public entry point is re-exported here so existing
``from src.ui.data_dictionary_screen import show_data_dictionary_screen``
call sites keep working unchanged.
"""

from __future__ import annotations

from src.ui.data_dictionary_screen.screen import show_data_dictionary_screen

__all__ = ["show_data_dictionary_screen"]
