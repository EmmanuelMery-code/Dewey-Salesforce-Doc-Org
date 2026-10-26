"""Catalog of models served by the Salesforce LLM Gateway.

``GATEWAY_MODELS`` is a snapshot of ``GET /models`` taken on 2026-10-22.
The configuration screen can replace it with a live query; see
:meth:`src.ai.ai_service_providers.GatewayService.list_models`.
"""

from __future__ import annotations

from typing import Any

GATEWAY_MODELS: list[str] = [
    "auto-model-preview",
    "claude-auto-model-preview",
    "claude-haiku-4-5-20251001",
    "claude-haiku-4-5-vertex",
    "claude-haiku-5-5",
    "claude-opus-4-5-20251101",
    "claude-opus-4-6-v1",
    "claude-opus-4-6-vertex",
    "claude-opus-4-7",
    "claude-opus-4-7-vertex",
    "claude-opus-4-8",
    "claude-opus-4-8-vertex",
    "claude-opus-5-5",
    "claude-opus-5-5-vertex",
    "claude-sonnet-4-20250514",
    "claude-sonnet-4-5-20250929",
    "claude-sonnet-4-5-vertex",
    "claude-sonnet-4-6",
    "claude-sonnet-4-6-vertex",
    "claude-sonnet-5",
    "claude-sonnet-5-5",
    "claude-sonnet-5-5-vertex",
    "claude-sonnet-5-vertex",
    "codex-auto-model-preview",
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
    "gemini-3.1-pro-preview",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
    "gemma-3-4b-it-bedrock",
    "gemma-4-31b-bedrock",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5.2-codex",
    "gpt-5.3-codex",
    "gpt-5.4-bedrock",
    "gpt-5.5",
    "gpt-5.5-bedrock",
    "gpt-5.6",
    "gpt-5.6-luna",
    "gpt-5.6-luna-bedrock",
    "gpt-5.6-sol",
    "gpt-5.6-sol-bedrock",
    "gpt-5.6-terra",
    "gpt-5.6-terra-bedrock",
    "gpt-6-luna",
    "gpt-6-luna-openai",
    "gpt-6-sol",
    "gpt-6-sol-openai",
    "gpt-6.1-sol",
    "gpt-6.1-sol-openai",
    "grok-4.6",
    "grok-4.7",
]


def models_endpoint(chat_url: str) -> str:
    """Return the ``/models`` URL that matches a chat-completions URL."""

    suffix = "/chat/completions"
    text = (chat_url or "").rstrip("/")
    if text.endswith(suffix):
        return text[: -len(suffix)] + "/models"
    return text + "/models"


def parse_gateway_model_ids(payload: Any) -> list[str]:
    """Extract a sorted, de-duplicated model id list from a gateway payload."""

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    seen: set[str] = set()
    models: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        models.append(model_id)
    models.sort(key=str.casefold)
    return models
