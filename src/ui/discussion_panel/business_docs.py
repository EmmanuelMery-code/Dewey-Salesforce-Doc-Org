"""Generate the business and maintainability Word documents from Discussion."""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path
from threading import Thread
from typing import TYPE_CHECKING

from src.ai import (
    AIMessage,
    AIProviderNotConfigured,
    AIProviderNotInstalled,
    DailyQuotaExceeded,
    create_service,
)
from src.ai.org_document_digest import (
    build_business_brief,
    build_maintainability_skeleton,
    documentation_ready,
    read_documentation_excerpt,
)
from src.ai.org_document_prompts import (
    business_system_prompt,
    maintainability_system_prompt,
    user_message,
)
from src.reporting.markdown_docx import (
    document_filename,
    ensure_remaining_section,
    prepare_maintainability_markdown,
    word_output_path,
    write_markdown_document,
)
from src.ui.discussion_panel.history_view import append_line, release_discussion_job

if TYPE_CHECKING:
    from src.ui.application import Application

KIND_BUSINESS = "business"
KIND_MAINTAINABILITY = "maintainability"


def generate_business_document(app: Application) -> None:
    """Describe the org from a business point of view and save a Word file."""

    _start(app, KIND_BUSINESS)


def generate_maintainability_document(app: Application) -> None:
    """List maintainability corrections, grouped by object, and save a Word file."""

    _start(app, KIND_MAINTAINABILITY)


def handle_document(app: Application, payload: dict[str, str]) -> None:
    """Show the path of a document produced by the background job."""

    release_discussion_job(app)
    path = str(payload.get("path") or "").strip()
    if path:
        append_line(app, app._t("discussion_doc_saved", path=path), tag="system")
        app.status_var.set(app._t("operation_done"))
    else:
        append_line(app, app._t("discussion_empty_reply"), tag="error")
        app.status_var.set(app._t("operation_failed"))


def _start(app: Application, kind: str) -> None:
    if app.discussion_pending:
        append_line(app, app._t("discussion_busy"), tag="error")
        return
    worker = getattr(app.task_manager, "worker", None)
    if worker is not None and worker.is_alive():
        append_line(app, app._t("action_already_running"), tag="error")
        return

    alias = _org_alias(app)
    if not alias:
        append_line(app, app._t("discussion_doc_missing_alias"), tag="error")
        return

    source_text = app.source_var.get().strip()
    source = Path(source_text) if source_text else None
    if source is None or not source.is_dir() or not _dir_has_entries(source):
        append_line(app, app._t("discussion_doc_missing_source"), tag="error")
        return

    output_text = app.output_var.get().strip()
    if not output_text:
        append_line(app, app._t("discussion_doc_missing_output"), tag="error")
        return
    output = Path(output_text)
    if output.exists() and not output.is_dir():
        append_line(app, app._t("discussion_doc_missing_output"), tag="error")
        return

    provider = app.ai_provider_var.get().strip() or app.AI_PROVIDERS[0]
    if not _api_key(app, provider):
        append_line(app, app._t("discussion_not_configured", provider=provider), tag="error")
        return

    label = app._t(
        "discussion_doc_business" if kind == KIND_BUSINESS else "discussion_doc_maintainability"
    )
    stamp = date.today().strftime("%Y%m%d")
    filename = document_filename(kind, alias, stamp)
    target = word_output_path(output, filename)
    language = app.language or "fr"
    exclusion = app.exclusion_file_var.get().strip()
    exclusion_path = exclusion if exclusion and Path(exclusion).is_file() else None

    append_line(app, app._t("discussion_doc_started", label=label, alias=alias), tag="system")
    append_line(
        app,
        app._t("discussion_doc_paths", source=str(source), output=str(output)),
        tag="system",
    )
    if not documentation_ready(output):
        append_line(app, app._t("discussion_doc_no_html"), tag="system")

    app.discussion_pending = True
    app.discussion_document_kind = kind
    app.discussion_locks_ui = True
    app._discussion_last_send_ts = time.monotonic()
    app._set_buttons_state(False)
    app.status_var.set(app._t("discussion_doc_busy_status", label=label))

    settings = {
        "claude_api_key": app.claude_api_key_var.get(),
        "gemini_api_key": app.gemini_api_key_var.get(),
        "gateway_api_key": app.gateway_api_key_var.get(),
        "gateway_cert_path": app.gateway_cert_path_var.get(),
        "claude_model": app.claude_model_var.get().strip() or app.DEFAULT_CLAUDE_MODEL,
        "gemini_model": app.gemini_model_var.get().strip() or app.DEFAULT_GEMINI_MODEL,
        "gateway_model": app.gateway_model_var.get().strip() or app.DEFAULT_GATEWAY_MODEL,
    }
    queue = app.task_manager.queue

    def status(key: str, **fmt: object) -> None:
        queue.put(("discussion_info", {"kind": "status", "message": app._t(key, **fmt)}))

    def worker() -> None:
        try:
            status("discussion_doc_reading_source")
            from src.parsers.salesforce_parser import SalesforceMetadataParser

            snapshot = SalesforceMetadataParser(
                source,
                exclusion_config_path=exclusion_path,
                log_callback=lambda message: queue.put(
                    ("discussion_info", {"kind": "status", "message": message})
                ),
            ).parse()
            status(
                "discussion_doc_source_ready",
                objects=len(snapshot.objects),
                flows=len(snapshot.flows),
                apex=len(snapshot.apex_artifacts),
            )
            status("discussion_doc_reading_output")
            if kind == KIND_BUSINESS:
                brief = build_business_brief(
                    snapshot,
                    output,
                    alias=alias,
                    source_dir=str(source),
                    language=language,
                )
                system = business_system_prompt(language, alias)
                prompt = user_message(
                    "Faits extraits des dossiers. Rédige le document demandé."
                    if not language.lower().startswith("en")
                    else "Facts extracted from the folders. Write the requested document.",
                    brief.digest,
                )
                title = (
                    "Business description of the organisation"
                    if language.lower().startswith("en")
                    else "Description métier de l'organisation"
                )
            else:
                skeleton = build_maintainability_skeleton(
                    snapshot,
                    output,
                    alias=alias,
                    source_dir=str(source),
                    language=language,
                )
                system = maintainability_system_prompt(language)
                excerpt = read_documentation_excerpt(output, language)[:4000]
                if language.lower().startswith("en"):
                    intro = (
                        "Skeleton to complete without changing the headings.\n\n"
                        "Generated documentation (do not turn this into its own section; "
                        "use it only to clarify a correction already listed):\n"
                        + excerpt
                    )
                else:
                    intro = (
                        "Squelette à compléter sans changer les titres.\n\n"
                        "Documentation générée (ne pas en faire une section ; s'en servir "
                        "seulement pour préciser une correction déjà listée) :\n"
                        + excerpt
                    )
                prompt = user_message(intro, skeleton)
                title = (
                    "Maintainability corrections"
                    if language.lower().startswith("en")
                    else "Corrections de maintenabilité"
                )
                brief = None

            service = create_service(provider, settings)
            status("discussion_doc_calling_ai", provider=provider)

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

            reply = service.chat(
                [AIMessage(role="user", content=prompt)],
                system_prompt=system,
                max_tokens=8192,
                on_retry=on_retry,
            )
            if not (reply or "").strip():
                queue.put(("discussion_error", app._t("discussion_empty_reply")))
                return

            if kind == KIND_BUSINESS:
                markdown = ensure_remaining_section(
                    reply,
                    brief.gaps if brief is not None else [],
                    language,
                )
            else:
                markdown = prepare_maintainability_markdown(skeleton, reply)

            subtitle = f"{alias} — {stamp[:4]}-{stamp[4:6]}-{stamp[6:]}"
            details = f"Source : {source}\nSortie : {output}"
            if language.lower().startswith("en"):
                details = f"Source: {source}\nOutput: {output}"
            saved = write_markdown_document(
                markdown,
                target,
                title=title,
                subtitle=subtitle,
                details=details,
                language=language,
            )
            queue.put(
                (
                    "discussion_document",
                    {"provider": provider, "path": str(saved), "kind": kind},
                )
            )
        except (AIProviderNotConfigured, AIProviderNotInstalled, DailyQuotaExceeded) as exc:
            queue.put(("discussion_error", str(exc)))
        except Exception as exc:  # pragma: no cover - disk and network failures
            queue.put(("discussion_error", f"{type(exc).__name__}: {exc}"))

    app.discussion_worker = Thread(target=worker, daemon=True)
    app.discussion_worker.start()


def _org_alias(app: Application) -> str:
    alias = app.alias_var.get().strip()
    if alias:
        return alias
    selected = app._selected_org()
    if selected is not None and getattr(selected, "org_ref", ""):
        return str(selected.org_ref).strip()
    return ""


def _api_key(app: Application, provider: str) -> str:
    if provider == "Claude":
        return app.claude_api_key_var.get().strip()
    if provider == "Gateway":
        return app.gateway_api_key_var.get().strip()
    return app.gemini_api_key_var.get().strip()


def _dir_has_entries(path: Path) -> bool:
    try:
        next(path.iterdir())
    except (StopIteration, OSError):
        return False
    return True
