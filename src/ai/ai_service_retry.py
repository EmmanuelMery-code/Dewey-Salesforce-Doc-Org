"""AI provider errors plus rate-limit/quota classification and retry-with-backoff helpers."""

from __future__ import annotations

import re
import time
from typing import Any, Callable


RetryNotifier = Callable[[int, int, float], None]
"""Callback invoked when a provider has to wait before retrying.

Signature: ``(attempt, max_attempts, wait_seconds)``
"""


DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_WAIT_SECONDS = 20.0
MAX_RETRY_WAIT_SECONDS = 90.0


_RETRY_DELAY_RE = re.compile(r"retry[_\s]*delay[^0-9]*?(\d+(?:\.\d+)?)", re.IGNORECASE)
_RETRY_IN_RE = re.compile(r"retry\s+in\s+(\d+(?:\.\d+)?)\s*s", re.IGNORECASE)
_SECONDS_FIELD_RE = re.compile(r"seconds\s*[:=]\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


class AIProviderNotConfigured(Exception):
    """Raised when an AI provider is selected but its API key is missing."""


class AIProviderNotInstalled(Exception):
    """Raised when the Python SDK for a provider is not installed."""


class DailyQuotaExceeded(Exception):
    """Raised when a free-tier *per-day* (RPD) quota has been spent.

    Unlike per-minute quotas, retrying after a few seconds will not help.
    The UI should surface the exception message verbatim so the user
    understands they must either wait for the daily reset, switch model,
    or switch provider.
    """


def _is_rate_limit_exception(exc: BaseException) -> bool:
    """Return True when the exception looks like a 429 / quota error.

    Supports both the legacy ``google.generativeai`` SDK (raises
    ``google.api_core.exceptions.ResourceExhausted``) and the new
    ``google.genai`` SDK (raises ``google.genai.errors.ClientError`` /
    ``APIError`` with a ``.code`` attribute equal to 429).
    """
    class_name = type(exc).__name__
    if class_name in {"ResourceExhausted", "TooManyRequests", "RateLimitError"}:
        return True
    # New google-genai SDK packs the HTTP status in `.code` on ClientError.
    code = getattr(exc, "code", None)
    if isinstance(code, int) and code == 429:
        return True
    if class_name in {"ClientError", "APIError"} and "429" in str(exc):
        return True
    message = str(exc)
    lowered = message.lower()
    if "429" in lowered:
        return True
    if "resourceexhausted" in lowered:
        return True
    if "quota" in lowered and ("exceed" in lowered or "limit" in lowered):
        return True
    if "rate limit" in lowered:
        return True
    return False


def _is_daily_quota_exception(exc: BaseException) -> bool:
    """Return True if the 429 concerns a *per-day* (RPD) quota.

    Google differentiates quotas through the ``quota_id`` field of the error:
    - ``GenerateRequestsPerMinutePerProjectPerModel-FreeTier`` for RPM
    - ``GenerateRequestsPerDayPerProjectPerModel-FreeTier`` for RPD
    - ``GenerateContentInputTokensPerModelPerMinute-FreeTier`` for TPM
    """
    if not _is_rate_limit_exception(exc):
        return False
    lowered = str(exc).lower()
    if "perdayper" in lowered.replace("_", "").replace("-", ""):
        return True
    if "perday" in lowered.replace(" ", ""):
        return True
    if "daily" in lowered and "quota" in lowered:
        return True
    return False


def _humanize_quota_error(exc: BaseException) -> str:
    """Return a short, actionable message for the user.

    Strips the verbose protobuf-ish payload Google returns and keeps only
    what is useful to decide what to do next.
    """
    raw = str(exc)
    lowered = raw.lower()
    compact = lowered.replace("_", "").replace("-", "").replace(" ", "")

    # Order matters: TPM quota_id *also* contains "PerMinute" so we must match
    # the token-based quotas before the generic per-minute one.
    if "perdayperproject" in compact or "perday" in lowered.replace(" ", ""):
        return (
            "Quota journalier (RPD) Gemini epuise pour ce modele sur le palier "
            "gratuit. Le compteur est remis a zero a minuit heure Pacifique "
            "(~09h00 UTC). Solutions : attendre le reset, changer de modele "
            "via Configuration > Discussion, ou basculer sur Claude."
        )
    if "tokens" in lowered and ("perminute" in compact or "tpm" in lowered):
        return (
            "Quota de tokens par minute (TPM) Gemini atteint. Le contexte "
            "envoye a l'IA est trop gros pour le palier gratuit. Effacez "
            "l'historique ou reduisez la taille du prompt systeme via "
            "Configuration > Discussion."
        )
    if "perminute" in compact or "rate limit" in lowered:
        return (
            "Quota par minute (RPM) Gemini atteint. Lucie retente "
            "automatiquement apres la pause demandee par Google."
        )
    # Fallback: keep the original message (truncated) for transparency.
    truncated = raw if len(raw) < 280 else raw[:280] + "..."
    return truncated


def _extract_retry_seconds(exc: BaseException) -> float:
    """Best-effort extraction of the suggested retry delay from the error."""
    candidate: float | None = None

    retry_delay = getattr(exc, "retry_delay", None)
    if retry_delay is not None:
        seconds = getattr(retry_delay, "seconds", None)
        if isinstance(seconds, (int, float)) and seconds > 0:
            candidate = float(seconds)

    if candidate is None:
        retry_after = getattr(exc, "retry_after", None)
        if isinstance(retry_after, (int, float)) and retry_after > 0:
            candidate = float(retry_after)

    if candidate is None:
        message = str(exc)
        for regex in (_RETRY_IN_RE, _RETRY_DELAY_RE, _SECONDS_FIELD_RE):
            match = regex.search(message)
            if match:
                try:
                    value = float(match.group(1))
                except (TypeError, ValueError):
                    continue
                if value > 0:
                    candidate = value
                    break

    if candidate is None:
        candidate = DEFAULT_RETRY_WAIT_SECONDS

    # Add a small safety margin and cap to avoid blocking the UI for minutes.
    return min(candidate + 1.0, MAX_RETRY_WAIT_SECONDS)


def _call_with_retry(
    callable_: Callable[[], Any],
    *,
    provider_label: str,
    on_retry: RetryNotifier | None,
    max_retries: int,
) -> Any:
    """Invoke ``callable_`` and retry on rate-limit style errors.

    The retry delay is derived from the server's hint (``retry_delay``
    / ``retry_after`` / "retry in Ns") and capped by
    :data:`MAX_RETRY_WAIT_SECONDS`.
    """
    attempts = max(1, int(max_retries))
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return callable_()
        except Exception as exc:  # noqa: BLE001 - we classify below
            last_exc = exc
            if not _is_rate_limit_exception(exc):
                raise
            if _is_daily_quota_exception(exc):
                # RPD quotas will not recover within the retry window; stop now
                # and surface a clear, localisable message to the UI.
                raise DailyQuotaExceeded(_humanize_quota_error(exc)) from exc
            if attempt >= attempts:
                break
            wait_seconds = _extract_retry_seconds(exc)
            if on_retry is not None:
                try:
                    on_retry(attempt, attempts, wait_seconds)
                except Exception:  # pragma: no cover - callback is best-effort
                    pass
            _ = provider_label  # kept for future structured logging
            time.sleep(wait_seconds)
    # Exhausted all retries: re-raise the last quota error so the UI shows it.
    assert last_exc is not None
    raise last_exc
