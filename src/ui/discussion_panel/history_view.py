"""History widget helpers: rendering, navigation and clipboard actions."""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.application import Application


def append_line(app: Application, text: str, tag: str = "system") -> None:
    widget = app.discussion_history_widget
    widget.configure(state="normal")
    widget.insert("end", text + "\n", tag)
    widget.see("end")
    widget.configure(state="disabled")


def _user_questions(app: Application) -> list[str]:
    """Return the list of user-authored questions, in chronological order."""

    return [m.content for m in app.discussion_messages if m.role == "user"]


def update_navigation_state(app: Application) -> None:
    """Enable/disable the navigation and copy buttons based on history."""

    if not hasattr(app, "discussion_prev_button"):
        return

    questions = _user_questions(app)
    has_questions = bool(questions)
    has_messages = bool(app.discussion_messages)
    index = app.discussion_question_index

    can_prev = has_questions and (index is None or index > 0)
    can_next = has_questions and index is not None and index < len(questions) - 1

    app.discussion_prev_button.configure(state="normal" if can_prev else "disabled")
    app.discussion_next_button.configure(state="normal" if can_next else "disabled")
    app.discussion_copy_last_button.configure(
        state="normal" if has_questions else "disabled"
    )
    app.discussion_copy_current_button.configure(
        state="normal" if (has_questions and index is not None) else "disabled"
    )
    app.discussion_copy_all_button.configure(
        state="normal" if has_messages else "disabled"
    )


def _focus_question(app: Application, index: int) -> None:
    """Scroll the history widget to question ``index`` and highlight it."""

    ranges = getattr(app, "discussion_question_ranges", [])
    if index < 0 or index >= len(ranges):
        return
    start, end = ranges[index]
    widget = app.discussion_history_widget
    widget.tag_remove("question_active", "1.0", "end")
    widget.tag_add("question_active", start, end)
    # ``see`` ensures the line is visible; pointing first at ``end``
    # then at ``start`` keeps the question header at the top of the
    # viewport when it is taller than the visible area.
    widget.see(end)
    widget.see(start)


def go_previous(app: Application) -> None:
    questions = _user_questions(app)
    if not questions:
        return
    if app.discussion_question_index is None:
        app.discussion_question_index = len(questions) - 1
    elif app.discussion_question_index > 0:
        app.discussion_question_index -= 1
    else:
        return
    _focus_question(app, app.discussion_question_index)
    update_navigation_state(app)


def go_next(app: Application) -> None:
    questions = _user_questions(app)
    if not questions or app.discussion_question_index is None:
        return
    if app.discussion_question_index < len(questions) - 1:
        app.discussion_question_index += 1
        _focus_question(app, app.discussion_question_index)
    update_navigation_state(app)


def _set_clipboard(app: Application, text: str) -> bool:
    """Push ``text`` into the system clipboard via Tk."""

    if not text:
        return False
    try:
        app.clipboard_clear()
        app.clipboard_append(text)
        app.update_idletasks()
    except tk.TclError:
        return False
    return True


def _question_with_answer(
    app: Application, user_index: int
) -> tuple[str, str | None]:
    """Return ``(question, answer_or_None)`` for the ``user_index``-th question.

    ``user_index`` is counted in the filtered list of user messages
    (same convention as ``discussion_question_index``). The associated
    answer is the first ``assistant`` message that follows the matching
    user message in ``discussion_messages``; ``None`` when the request
    is still pending or has failed.
    """

    seen = -1
    user_position: int | None = None
    for position, message in enumerate(app.discussion_messages):
        if message.role != "user":
            continue
        seen += 1
        if seen == user_index:
            user_position = position
            break
    if user_position is None:
        return "", None
    question = app.discussion_messages[user_position].content
    answer: str | None = None
    for follower in app.discussion_messages[user_position + 1 :]:
        if follower.role == "assistant":
            answer = follower.content
            break
        if follower.role == "user":
            break
    return question, answer


def _format_qa_clipboard(app: Application, question: str, answer: str | None) -> str:
    """Render the clipboard text for a question (and optional answer)."""

    user_label = app._t("discussion_role_user")
    blocks = [f"{user_label}: {question}"]
    if answer:
        assistant_label = app._t("discussion_role_assistant")
        blocks.append(f"{assistant_label}: {answer}")
    return "\n\n".join(blocks)


def copy_last_question(app: Application) -> None:
    questions = _user_questions(app)
    if not questions:
        return
    last_index = len(questions) - 1
    question, answer = _question_with_answer(app, last_index)
    if not _set_clipboard(app, _format_qa_clipboard(app, question, answer)):
        return
    key = (
        "discussion_copy_last_with_answer_done"
        if answer
        else "discussion_copy_last_no_answer_done"
    )
    append_line(app, app._t(key))


def copy_current_question(app: Application) -> None:
    questions = _user_questions(app)
    index = app.discussion_question_index
    if not questions or index is None or not 0 <= index < len(questions):
        return
    question, answer = _question_with_answer(app, index)
    if not _set_clipboard(app, _format_qa_clipboard(app, question, answer)):
        return
    key = (
        "discussion_copy_current_with_answer_done"
        if answer
        else "discussion_copy_current_no_answer_done"
    )
    append_line(app, app._t(key, index=index + 1))


def copy_discussion(app: Application) -> None:
    if not app.discussion_messages:
        return
    role_labels = {
        "user": app._t("discussion_role_user"),
        "assistant": app._t("discussion_role_assistant"),
        "system": app._t("discussion_role_system"),
    }
    blocks: list[str] = []
    for message in app.discussion_messages:
        prefix = role_labels.get(message.role, message.role)
        blocks.append(f"{prefix}: {message.content}")
    if _set_clipboard(app, "\n\n".join(blocks)):
        append_line(app, app._t("discussion_copy_all_done"))


def _append_user_question(app: Application, message: str) -> None:
    """Append a user question to the history and remember its Tk range.

    The recorded ``(start, end)`` pair is later used by the previous /
    next navigation buttons to scroll back to the right line and
    highlight it inside the history widget.
    """

    widget = app.discussion_history_widget
    widget.configure(state="normal")
    start_idx = widget.index("end-1c")
    widget.insert("end", f"> {message}\n", "user")
    end_idx = widget.index("end-1c")
    widget.see("end")
    widget.configure(state="disabled")
    app.discussion_question_ranges.append((start_idx, end_idx))


def _rollback_failed_user_message(app: Application) -> None:
    """Undo a user message that could not be sent (e.g. missing key).

    Pops the message from the conversation list, drops its companion
    range so the navigation history stays in sync, and refreshes the
    button states. The text already inserted in the widget is kept on
    purpose so the user still sees what they tried to send.
    """

    if app.discussion_messages and app.discussion_messages[-1].role == "user":
        app.discussion_messages.pop()
    if app.discussion_question_ranges:
        app.discussion_question_ranges.pop()
    update_navigation_state(app)


def clear_history(app: Application) -> None:
    app.discussion_messages = []
    app.discussion_question_index = None
    app.discussion_question_ranges = []
    widget = app.discussion_history_widget
    widget.configure(state="normal")
    widget.tag_remove("question_active", "1.0", "end")
    widget.delete("1.0", "end")
    widget.configure(state="disabled")
    append_line(app, app._t("discussion_cleared"))
    update_navigation_state(app)


def update_context_status(app: Application) -> None:
    if not hasattr(app, "discussion_context_status_var"):
        return
    if getattr(app, "discussion_force_existing_docs", False):
        app.discussion_context_status_var.set(app._t("discussion_context_forced"))
        return
    if app.latest_snapshot is None:
        app.discussion_context_status_var.set(app._t("discussion_context_empty"))
    else:
        app.discussion_context_status_var.set(app._t("discussion_context_ready"))
