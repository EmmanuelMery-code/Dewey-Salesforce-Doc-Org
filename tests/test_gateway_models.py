"""Parsing of the Salesforce LLM Gateway model catalog."""

from __future__ import annotations

from src.ai.gateway_models import GATEWAY_MODELS, models_endpoint, parse_gateway_model_ids


def test_models_endpoint_matches_the_chat_url() -> None:
    assert (
        models_endpoint(
            "https://eng-ai-model-gateway.example/chat/completions"
        )
        == "https://eng-ai-model-gateway.example/models"
    )


def test_parse_gateway_model_ids_sorts_and_drops_blanks() -> None:
    payload = {
        "data": [
            {"id": "gpt-5", "mode": "chat"},
            {"id": "  "},
            {"id": "claude-sonnet-5"},
            "ignore-me",
            {"id": "gpt-5"},
            {"id": "gpt-6-sol", "mode": "responses"},
        ]
    }
    assert parse_gateway_model_ids(payload) == [
        "claude-sonnet-5",
        "gpt-5",
        "gpt-6-sol",
    ]
    assert parse_gateway_model_ids({}) == []
    assert parse_gateway_model_ids({"data": {}}) == []


def test_default_catalog_matches_the_gateway_snapshot() -> None:
    assert "gpt-5" in GATEWAY_MODELS
    assert "claude-sonnet-4-6" in GATEWAY_MODELS
    assert "gemini-3.5-flash" in GATEWAY_MODELS
    assert "gpt-40" not in GATEWAY_MODELS
    assert "gemini-2.0-flash" not in GATEWAY_MODELS
    assert GATEWAY_MODELS == sorted(GATEWAY_MODELS, key=str.casefold)
    assert len(GATEWAY_MODELS) == len(set(GATEWAY_MODELS))
