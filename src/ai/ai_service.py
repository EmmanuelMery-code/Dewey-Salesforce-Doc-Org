"""AI provider abstraction layer: chat message type, base service, and provider factory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ai_service_retry import (
    AIProviderNotConfigured,
    AIProviderNotInstalled,
    DailyQuotaExceeded,
    DEFAULT_MAX_RETRIES,
    RetryNotifier,
)


@dataclass(slots=True)
class AIMessage:
    """Represents a single message in a chat conversation."""

    role: str  # "user" or "assistant"
    content: str


class AIServiceBase:
    """Base class for AI providers."""

    name: str = "base"
    default_model: str = ""
    available_models: list[str] = []

    def __init__(self, api_key: str, model: str | None = None) -> None:
        self.api_key = (api_key or "").strip()
        self.model = (model or self.default_model).strip() or self.default_model

    def is_ready(self) -> bool:
        return bool(self.api_key)

    def chat(
        self,
        messages: list[AIMessage],
        system_prompt: str = "",
        max_tokens: int = 8192,
        *,
        on_retry: RetryNotifier | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> str:
        raise NotImplementedError


# Imported here (after AIMessage/AIServiceBase are defined) rather than at the
# top of the file: ai_service_providers imports AIMessage/AIServiceBase back
# from this module, so importing it earlier would create an import-time cycle.
from .ai_service_providers import (  # noqa: E402
    CLAUDE_MODELS,
    GEMINI_MODELS,
    ClaudeService,
    GatewayService,
    GeminiService,
)


def create_service(provider: str, settings: dict[str, Any]) -> AIServiceBase:
    """Build the correct AI service for the selected provider."""
    provider_norm = (provider or "").strip().lower()
    if provider_norm == "claude":
        return ClaudeService(
            api_key=str(settings.get("claude_api_key", "") or ""),
            model=str(settings.get("claude_model", "") or "") or None,
        )
    if provider_norm == "gemini":
        return GeminiService(
            api_key=str(settings.get("gemini_api_key", "") or ""),
            model=str(settings.get("gemini_model", "") or "") or None,
        )
    if provider_norm == "gateway":
        return GatewayService(
            api_key=str(settings.get("gateway_api_key", "") or ""),
            model=str(settings.get("gateway_model", "") or "") or None,
            cert_path=str(settings.get("gateway_cert_path", "") or "") or None,
        )
    raise ValueError(f"Fournisseur IA inconnu : {provider}")
