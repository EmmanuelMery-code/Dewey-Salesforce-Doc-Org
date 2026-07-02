"""Discussion / chat tab.

Encapsulates the conversational UI used to talk to the configured AI
provider. Keeping this in its own package keeps :class:`Application` focused
on orchestration rather than chat plumbing.

The implementation is split into the panel layout, the history/navigation
view helpers and the AI messaging flow. The names consumed by
``Application`` (via ``discussion_panel.<name>``) are re-exported here so the
existing call sites keep working unchanged.
"""

from __future__ import annotations

from src.ui.discussion_panel.history_view import (
    append_line,
    clear_history,
    update_context_status,
    update_navigation_state,
)
from src.ui.discussion_panel.messaging import (
    handle_error,
    handle_info,
    handle_reply,
    send_message,
    summarize_org,
    toggle_force_existing_docs,
)
from src.ui.discussion_panel.panel import build_panel

__all__ = [
    "append_line",
    "build_panel",
    "clear_history",
    "handle_error",
    "handle_info",
    "handle_reply",
    "send_message",
    "summarize_org",
    "toggle_force_existing_docs",
    "update_context_status",
    "update_navigation_state",
]
