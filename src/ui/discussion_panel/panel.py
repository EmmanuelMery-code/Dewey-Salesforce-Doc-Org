"""Discussion tab layout."""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import TYPE_CHECKING

from src.ui.discussion_panel.history_view import (
    clear_history,
    copy_current_question,
    copy_discussion,
    copy_last_question,
    go_next,
    go_previous,
    update_navigation_state,
)
from src.ui.discussion_panel.messaging import (
    send_message,
    summarize_org,
    toggle_force_existing_docs,
)

if TYPE_CHECKING:
    from src.ui.application import Application


def build_panel(app: Application, parent: ttk.Frame) -> None:
    """Render the discussion tab into ``parent``."""

    container = ttk.Frame(parent, padding=12)
    container.pack(fill="both", expand=True)

    app.discussion_title_label = ttk.Label(container, font=("Segoe UI", 13, "bold"))
    app.discussion_title_label.pack(anchor="w")
    app.discussion_description_label = ttk.Label(
        container, wraplength=700, justify="left"
    )
    app.discussion_description_label.pack(anchor="w", pady=(4, 8))

    provider_row = ttk.Frame(container)
    provider_row.pack(fill="x", pady=(0, 8))
    app.discussion_provider_label = ttk.Label(provider_row, width=18)
    app.discussion_provider_label.pack(side="left")
    app.discussion_provider_value = ttk.Label(
        provider_row, textvariable=app.ai_provider_var, font=("Segoe UI", 10, "bold")
    )
    app.discussion_provider_value.pack(side="left")

    app.discussion_context_status_var = tk.StringVar(
        value=app._t("discussion_context_empty")
    )
    app.discussion_context_label = ttk.Label(
        provider_row,
        textvariable=app.discussion_context_status_var,
        foreground="#6b7280",
    )
    app.discussion_context_label.pack(side="left", padx=(16, 0))
    # Button placed at the end of the provider row so the user can
    # explicitly tell the assistant to rely on the documentation that
    # already lives in the output folder, ignoring the in-memory
    # snapshot if any.
    app.discussion_force_docs_button = app._track_button(
        ttk.Button(
            provider_row,
            command=lambda: toggle_force_existing_docs(app),
        )
    )
    app.discussion_force_docs_button.pack(side="left", padx=(16, 0))

    app.discussion_history_label = ttk.Label(container)
    app.discussion_history_label.pack(anchor="w")
    history = scrolledtext.ScrolledText(container, wrap="word", height=14)
    history.pack(fill="both", expand=True, pady=(2, 8))
    history.configure(state="disabled")
    history.tag_configure("user", foreground="#1d4ed8", font=("Segoe UI", 10, "bold"))
    history.tag_configure("assistant", foreground="#047857")
    history.tag_configure(
        "system", foreground="#6b7280", font=("Segoe UI", 9, "italic")
    )
    history.tag_configure("error", foreground="#b91c1c")
    # Yellow background highlight applied transiently by the
    # previous/next navigation buttons. Configured with high priority so
    # it visually wins over the per-role styling above.
    history.tag_configure("question_active", background="#fde68a")
    history.tag_raise("question_active")
    app.discussion_history_widget = history

    input_row = ttk.Frame(container)
    input_row.pack(fill="x")
    app.discussion_input_label = ttk.Label(input_row, width=18)
    app.discussion_input_label.pack(side="left")
    app.discussion_input_var = tk.StringVar()
    app.discussion_input_entry = ttk.Entry(input_row, textvariable=app.discussion_input_var)
    app.discussion_input_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
    app.discussion_input_entry.bind(
        "<Return>", lambda _event: send_message(app)
    )
    app.discussion_send_button = app._track_button(
        ttk.Button(input_row, command=lambda: send_message(app))
    )
    app.discussion_send_button.pack(side="left")
    app.discussion_clear_button = app._track_button(
        ttk.Button(input_row, command=lambda: clear_history(app))
    )
    app.discussion_clear_button.pack(side="left", padx=(8, 0))

    app.discussion_summarize_button = app._track_button(
        ttk.Button(input_row, command=lambda: summarize_org(app))
    )
    app.discussion_summarize_button.pack(side="left", padx=(8, 0))

    # Navigation + copy bar shown right below the input field.
    nav_row = ttk.Frame(container)
    nav_row.pack(fill="x", pady=(6, 0))
    # Empty cell aligned with the 'Votre message' label so buttons
    # line up under the entry rather than under the label.
    ttk.Label(nav_row, width=18).pack(side="left")
    app.discussion_prev_button = app._track_button(
        ttk.Button(nav_row, command=lambda: go_previous(app))
    )
    app.discussion_prev_button.pack(side="left")
    app.discussion_next_button = app._track_button(
        ttk.Button(nav_row, command=lambda: go_next(app))
    )
    app.discussion_next_button.pack(side="left", padx=(8, 0))
    app.discussion_copy_last_button = app._track_button(
        ttk.Button(nav_row, command=lambda: copy_last_question(app))
    )
    app.discussion_copy_last_button.pack(side="left", padx=(16, 0))
    app.discussion_copy_current_button = app._track_button(
        ttk.Button(nav_row, command=lambda: copy_current_question(app))
    )
    app.discussion_copy_current_button.pack(side="left", padx=(8, 0))
    app.discussion_copy_all_button = app._track_button(
        ttk.Button(nav_row, command=lambda: copy_discussion(app))
    )
    app.discussion_copy_all_button.pack(side="left", padx=(8, 0))

    update_navigation_state(app)
