"""Concrete AI provider implementations (Claude, Gemini, Gateway) built on AIServiceBase."""

from __future__ import annotations

from typing import Any

import requests

from .ai_service import AIMessage, AIServiceBase
from .ai_service_retry import (
    AIProviderNotConfigured,
    AIProviderNotInstalled,
    DEFAULT_MAX_RETRIES,
    RetryNotifier,
    _call_with_retry,
)


GEMINI_MODELS: list[str] = [
    # Google retired gemini-1.5-* and gemini-2.0-* families in March 2026.
    # Only the gemini-2.5-* family is served on the free tier now.
    # Ordered from the most generous free-tier RPM/RPD to the strictest.
    # As of April 2026 (source: ai.google.dev/gemini-api/docs/rate-limits):
    #   - gemini-2.5-flash-lite : 15 RPM / 1000 RPD / 250k TPM
    #   - gemini-2.5-flash      : 10 RPM /  500 RPD / 250k TPM
    #   - gemini-2.5-pro        :  5 RPM /  100 RPD / 250k TPM
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]

CLAUDE_MODELS: list[str] = [
    "claude-sonnet-4-5-20250929",
    "claude-opus-4-20250514",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
]


class ClaudeService(AIServiceBase):
    """Anthropic Claude chat service."""

    name = "Claude"
    default_model = "claude-sonnet-4-5-20250929"
    available_models = CLAUDE_MODELS

    def chat(
        self,
        messages: list[AIMessage],
        system_prompt: str = "",
        max_tokens: int = 8192,
        *,
        on_retry: RetryNotifier | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> str:
        if not self.api_key:
            raise AIProviderNotConfigured(
                "Aucune cle API Claude configuree. Ajoutez-la dans Configuration > Discussion."
            )
        try:
            import anthropic  # type: ignore
        except ImportError as exc:  # pragma: no cover - runtime check
            raise AIProviderNotInstalled(
                "Le package 'anthropic' n'est pas installe. Executez: pip install anthropic"
            ) from exc

        payload: list[dict[str, Any]] = []
        for message in messages:
            if message.role not in ("user", "assistant"):
                continue
            if not message.content.strip():
                continue
            payload.append({"role": message.role, "content": message.content})
        if not payload:
            raise ValueError("Aucun message utilisateur a envoyer.")

        client = anthropic.Anthropic(api_key=self.api_key)

        def _call() -> Any:
            return client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt or "You are a helpful Salesforce expert assistant.",
                messages=payload,
            )

        response = _call_with_retry(
            _call,
            provider_label=self.name,
            on_retry=on_retry,
            max_retries=max_retries,
        )

        fragments: list[str] = []
        for block in response.content:
            text = getattr(block, "text", None)
            if text:
                fragments.append(text)
        return "".join(fragments).strip() or "(Reponse vide de Claude)"


class GeminiService(AIServiceBase):
    """Google Gemini chat service."""

    name = "Gemini"
    # gemini-2.5-flash-lite has the most generous free-tier quota as of 2026-04
    # (15 RPM / 1000 RPD / 250k TPM).
    default_model = "gemini-2.5-flash-lite"
    available_models = GEMINI_MODELS

    def chat(
        self,
        messages: list[AIMessage],
        system_prompt: str = "",
        max_tokens: int = 8192,
        *,
        on_retry: RetryNotifier | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> str:
        if not self.api_key:
            raise AIProviderNotConfigured(
                "Aucune cle API Gemini configuree. Ajoutez-la dans Configuration > Discussion."
            )

        if not messages or messages[-1].role != "user":
            raise ValueError("Le dernier message doit provenir de l'utilisateur.")

        effective_system = (
            system_prompt or "You are a helpful Salesforce expert assistant."
        )
        history_messages = list(messages[:-1])
        last_prompt = messages[-1].content

        # Prefer the official google-genai SDK (new, active support).
        # Fall back to the deprecated google-generativeai only if the new
        # package is not yet installed on the user's machine, so existing
        # setups keep working while they migrate.
        try:
            from google import genai as google_genai  # type: ignore
            from google.genai import types as genai_types  # type: ignore
        except ImportError:
            return self._chat_legacy_sdk(
                history_messages=history_messages,
                last_prompt=last_prompt,
                system_prompt=effective_system,
                max_tokens=max_tokens,
                on_retry=on_retry,
                max_retries=max_retries,
            )

        client = google_genai.Client(api_key=self.api_key)
        history_payload = [
            genai_types.Content(
                role="user" if message.role == "user" else "model",
                parts=[genai_types.Part(text=message.content)],
            )
            for message in history_messages
            if message.role in ("user", "assistant") and message.content.strip()
        ]
        config = genai_types.GenerateContentConfig(
            system_instruction=effective_system,
            max_output_tokens=max_tokens,
        )

        def _call() -> Any:
            # Recreate the chat on every attempt so that a failed send_message
            # does not leave half-populated history on the next retry.
            chat = client.chats.create(
                model=self.model,
                config=config,
                history=history_payload,
            )
            return chat.send_message(last_prompt)

        response = _call_with_retry(
            _call,
            provider_label=self.name,
            on_retry=on_retry,
            max_retries=max_retries,
        )

        text = getattr(response, "text", "") or ""
        return text.strip() or "(Reponse vide de Gemini)"

    def _chat_legacy_sdk(
        self,
        *,
        history_messages: list[AIMessage],
        last_prompt: str,
        system_prompt: str,
        max_tokens: int,
        on_retry: RetryNotifier | None,
        max_retries: int,
    ) -> str:
        """Fallback path for users still on the deprecated google-generativeai.

        The new ``google-genai`` package is strongly preferred because the
        legacy one no longer receives bug fixes. If nothing is installed,
        we point users to the new package.
        """
        try:
            import google.generativeai as legacy_genai  # type: ignore
        except ImportError as exc:  # pragma: no cover - runtime guard
            raise AIProviderNotInstalled(
                "Aucun SDK Gemini trouve. Installez le package officiel : "
                "pip install google-genai"
            ) from exc

        legacy_genai.configure(api_key=self.api_key)
        model = legacy_genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
            generation_config={"max_output_tokens": max_tokens},
        )

        history: list[dict[str, Any]] = []
        for message in history_messages:
            if message.role not in ("user", "assistant"):
                continue
            if not message.content.strip():
                continue
            role = "user" if message.role == "user" else "model"
            history.append({"role": role, "parts": [message.content]})

        def _call() -> Any:
            chat = model.start_chat(history=history)
            return chat.send_message(last_prompt)

        response = _call_with_retry(
            _call,
            provider_label=self.name,
            on_retry=on_retry,
            max_retries=max_retries,
        )
        text = getattr(response, "text", "") or ""
        return text.strip() or "(Reponse vide de Gemini)"


class GatewayService(AIServiceBase):
    """LLM Gateway chat service."""

    name = "Gateway"
    default_model = "gpt-5"
    url = "https://eng-ai-model-gateway.sfproxy.devx-preprod.aws-esvc1-useast2.aws.sfdc.cl/chat/completions"

    def __init__(self, api_key: str, model: str | None = None, cert_path: str | None = None) -> None:
        super().__init__(api_key, model)
        self.cert_path = cert_path or "config/Salesforce_Internal_Root_CA_3.pem"

    def chat(
        self,
        messages: list[AIMessage],
        system_prompt: str = "",
        max_tokens: int = 8192,
        *,
        on_retry: RetryNotifier | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> str:
        if not self.api_key:
            raise AIProviderNotConfigured(
                "Aucune cle API Gateway configuree. Ajoutez-la dans Configuration > Discussion."
            )

        payload_messages = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})
        
        for msg in messages:
            payload_messages.append({"role": msg.role, "content": msg.content})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": payload_messages,
            "max_tokens": max_tokens
        }

        def _call() -> Any:
            response = requests.post(
                self.url, 
                headers=headers, 
                json=payload, 
                verify=self.cert_path,
                timeout=180
            )
            response.raise_for_status()
            return response.json()

        try:
            result = _call_with_retry(
                _call,
                provider_label=self.name,
                on_retry=on_retry,
                max_retries=max_retries,
            )
            
            # Extract content from OpenAI-compatible response format
            if "choices" in result and len(result["choices"]) > 0:
                choice = result["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    return choice["message"]["content"].strip()
            
            return "(Reponse vide du Gateway)"
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    if "error" in error_data and "message" in error_data["error"]:
                        error_msg = error_data["error"]["message"]
                    else:
                        error_msg = e.response.text
                except Exception:
                    error_msg = e.response.text
            raise Exception(f"Erreur Gateway : {error_msg}") from e
