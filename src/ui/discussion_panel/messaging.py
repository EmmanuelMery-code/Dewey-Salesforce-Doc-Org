"""AI messaging flow: sending prompts and handling worker replies."""

from __future__ import annotations

import time
from pathlib import Path
from threading import Thread
from typing import TYPE_CHECKING

from src.ai import (
    AIMessage,
    AIProviderNotConfigured,
    AIProviderNotInstalled,
    DailyQuotaExceeded,
    build_org_context,
    build_system_prompt,
    create_service,
)
from src.ui.discussion_panel.history_view import (
    _append_user_question,
    _rollback_failed_user_message,
    append_line,
    update_context_status,
    update_navigation_state,
)

if TYPE_CHECKING:
    from src.ui.application import Application


def _has_generated_documentation(directory: str | None) -> bool:
    """Return True when ``directory`` looks like a Lucie documentation folder."""

    if not directory:
        return False

    try:
        path = Path(directory).expanduser()
    except (OSError, RuntimeError, ValueError):
        return False
    if not path.is_dir():
        return False
    if (path / "html" / "index.html").is_file():
        return True
    # Fallback: any typical sub-folder is a good indicator too.
    for probe in ("html", "excel", "word"):
        if (path / probe).is_dir():
            return True
    return any((path / "html" / sub).is_dir() for sub in ("objects", "apex", "flows", "omni"))


def toggle_force_existing_docs(app: Application) -> None:
    """Toggle the 'use existing documentation only' mode.

    When activated, :func:`send_message` passes ``snapshot=None`` to
    :func:`build_org_context`, which forces the assistant to walk through
    the documentation folder (and source folder) directly instead of
    relying on the in-memory analysis snapshot.

    Refuses to enable the mode when the configured output folder does
    not contain a generated documentation, so the user gets a clear
    error message instead of a silently broken context.
    """

    output_dir = app.output_var.get().strip()

    if not app.discussion_force_existing_docs:
        if not _has_generated_documentation(output_dir):
            append_line(
                app, app._t("discussion_force_docs_no_dir"), tag="error"
            )
            return
        app.discussion_force_existing_docs = True
        append_line(
            app,
            app._t("discussion_force_docs_enabled", path=output_dir),
            tag="system",
        )
    else:
        app.discussion_force_existing_docs = False
        append_line(app, app._t("discussion_force_docs_disabled"), tag="system")

    if hasattr(app, "discussion_force_docs_button"):
        app.discussion_force_docs_button.configure(
            text=app._t(
                "discussion_force_docs_active"
                if app.discussion_force_existing_docs
                else "discussion_force_docs"
            )
        )
    update_context_status(app)


def summarize_org(app: Application) -> None:
    """Send a pre-defined prompt to the AI to summarize the org."""
    if app.discussion_pending:
        append_line(app, app._t("discussion_busy"), tag="error")
        return

    app.is_summarize_request = True
    prompt = app._t("discussion_summarize_prompt")
    app.discussion_input_var.set(prompt)
    send_message(app)


def send_message(app: Application) -> None:
    if app.discussion_pending:
        append_line(app, app._t("discussion_busy"), tag="error")
        return

    now = time.monotonic()
    gap = now - app._discussion_last_send_ts
    if app._discussion_last_send_ts and gap < app.DISCUSSION_MIN_INTERVAL_SECONDS:
        wait = app.DISCUSSION_MIN_INTERVAL_SECONDS - gap
        append_line(
            app,
            app._t("discussion_throttle_wait", seconds=int(round(wait)) or 1),
            tag="system",
        )
        return

    message = app.discussion_input_var.get().strip()
    if not message:
        return
    provider = app.ai_provider_var.get().strip() or app.AI_PROVIDERS[0]

    _append_user_question(app, message)
    app.discussion_input_var.set("")
    app.discussion_messages.append(AIMessage(role="user", content=message))
    app.discussion_question_index = None
    update_navigation_state(app)

    if provider == "Claude":
        key_var = app.claude_api_key_var
    elif provider == "Gemini":
        key_var = app.gemini_api_key_var
    elif provider == "Gateway":
        key_var = app.gateway_api_key_var
    else:
        key_var = app.gemini_api_key_var # Fallback

    if not key_var.get().strip():
        append_line(
            app,
            app._t("discussion_not_configured", provider=provider),
            tag="error",
        )
        _rollback_failed_user_message(app)
        return

    system_prompt = app.system_prompt or build_system_prompt(app.language)

    # If it's a summarize request, we MUST ensure we use the latest metrics from the DB for the selected alias
    history_metrics = None
    if getattr(app, "is_summarize_request", False):
        try:
            # Get the effective alias (either from the entry or the selected org)
            selected_org = app._selected_org()
            alias = selected_org.org_ref if selected_org else app.alias_var.get().strip()

            if alias:
                app_root = Path(__file__).resolve().parent.parent.parent.parent
                db_path = app_root / "history.db"
                if db_path.exists():
                    from src.core.history_service import HistoryService
                    service = HistoryService(db_path)
                    entries = service.list_entries_for_alias(alias)
                    if entries:
                        history_metrics = entries[0] # Latest entry
        except Exception as exc:
            append_line(app, f"Avertissement : impossible de charger l'historique pour le resume : {exc}", tag="system")

    snapshot_for_context = (
        None
        if getattr(app, "discussion_force_existing_docs", False)
        else app.latest_snapshot
    )
    context = build_org_context(
        snapshot_for_context,
        source_dir=app.source_var.get().strip() or None,
        documentation_dir=app.output_var.get().strip() or None,
        exclusion_path=app.exclusion_file_var.get().strip() or None,
        history_entry=history_metrics,
    )

    full_system = f"{system_prompt}\n\n{context}"

    settings_for_service = {
        "claude_api_key": app.claude_api_key_var.get(),
        "gemini_api_key": app.gemini_api_key_var.get(),
        "gateway_api_key": app.gateway_api_key_var.get(),
        "gateway_cert_path": app.gateway_cert_path_var.get(),
        "claude_model": app.claude_model_var.get().strip() or app.DEFAULT_CLAUDE_MODEL,
        "gemini_model": app.gemini_model_var.get().strip() or app.DEFAULT_GEMINI_MODEL,
        "gateway_model": app.gateway_model_var.get().strip() or app.DEFAULT_GATEWAY_MODEL,
    }

    try:
        service = create_service(provider, settings_for_service)
    except ValueError as exc:
        append_line(app, str(exc), tag="error")
        _rollback_failed_user_message(app)
        return

    messages_snapshot = list(app.discussion_messages)
    app.discussion_pending = True
    app._discussion_last_send_ts = time.monotonic()
    app.discussion_send_button.configure(state="disabled")
    if hasattr(app, "discussion_summarize_button"):
        app.discussion_summarize_button.configure(state="disabled")
    append_line(
        app, app._t("discussion_thinking", provider=provider), tag="system"
    )

    queue = app.task_manager.queue

    def on_retry(attempt: int, max_attempts: int, wait_seconds: float) -> None:
        queue.put(
            (
                "discussion_info",
                {
                    "provider": provider,
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "seconds": int(round(wait_seconds)),
                    "kind": "rate_limit",
                },
            )
        )

    def worker() -> None:
        try:
            # Increase max_tokens for summaries to avoid truncation
            max_tokens = 8192 if getattr(app, "is_summarize_request", False) else 4096

            reply = service.chat(
                messages_snapshot,
                system_prompt=full_system,
                max_tokens=max_tokens,
                on_retry=on_retry,
            )
            queue.put(("discussion_reply", {"provider": provider, "reply": reply}))
        except (AIProviderNotConfigured, AIProviderNotInstalled) as exc:
            queue.put(("discussion_error", str(exc)))
        except DailyQuotaExceeded as exc:
            queue.put(("discussion_error", str(exc)))
        except Exception as exc:  # pragma: no cover - network failures
            queue.put(("discussion_error", f"{type(exc).__name__}: {exc}"))

    app.discussion_worker = Thread(target=worker, daemon=True)
    app.discussion_worker.start()


def handle_reply(app: Application, payload: dict[str, str]) -> None:
    reply = payload.get("reply", "")
    provider = payload.get("provider", "")
    app.discussion_pending = False
    app.discussion_send_button.configure(state="normal")
    if hasattr(app, "discussion_summarize_button"):
        app.discussion_summarize_button.configure(state="normal")
    if reply:
        app.discussion_messages.append(AIMessage(role="assistant", content=reply))
        append_line(app, f"[{provider}] {reply}", tag="assistant")

        # If it was a summarize request, save as RTF
        if getattr(app, "is_summarize_request", False):
            app.is_summarize_request = False
            try:
                from src.core.audit_generator import generate_ai_summary_rtf
                output_dir = Path(app.output_var.get().strip())
                word_dir = output_dir / "word"
                word_dir.mkdir(parents=True, exist_ok=True)
                rtf_path = word_dir / "ai_org_summary.rtf"
                generate_ai_summary_rtf(reply, rtf_path)
                append_line(app, f"Resume IA enregistre dans : {rtf_path}", tag="system")
            except Exception as exc:
                append_line(app, f"Erreur lors de l'enregistrement du resume RTF : {exc}", tag="error")
    else:
        app.discussion_empty_reply = True # Just to keep track
        append_line(app, app._t("discussion_empty_reply"), tag="error")
    update_navigation_state(app)


def handle_error(app: Application, message: str) -> None:
    app.discussion_pending = False
    app.is_summarize_request = False
    app.discussion_send_button.configure(state="normal")
    if hasattr(app, "discussion_summarize_button"):
        app.discussion_summarize_button.configure(state="normal")
    _rollback_failed_user_message(app)
    append_line(app, app._t("discussion_error", error=message), tag="error")


def handle_info(app: Application, payload: dict[str, object]) -> None:
    kind = str(payload.get("kind", ""))
    if kind == "rate_limit":
        append_line(
            app,
            app._t(
                "discussion_rate_limit_wait",
                provider=str(payload.get("provider", "")),
                seconds=int(payload.get("seconds", 0) or 0),
                attempt=int(payload.get("attempt", 0) or 0),
                max_attempts=int(payload.get("max_attempts", 0) or 0),
            ),
            tag="system",
        )
