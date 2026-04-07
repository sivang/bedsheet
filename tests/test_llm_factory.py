"""Tests for the LLM client factory.

Locks in the env-var priority for `make_llm_client()` so a future refactor
can't silently flip the default provider or model. The factory's docstring
documents:

    GEMINI_API_KEY    -> GeminiClient   (model: GEMINI_MODEL or gemini-3-flash-preview)
    ANTHROPIC_API_KEY -> AnthropicClient (model: ANTHROPIC_MODEL or claude-sonnet-4-5-20250929)

Gemini wins when both keys are set. Neither key set raises RuntimeError.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from bedsheet.llm.factory import make_llm_client


def test_factory_picks_gemini_when_only_gemini_key_set(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    with patch("bedsheet.llm.gemini.genai"):
        client = make_llm_client()

    from bedsheet.llm.gemini import GeminiClient

    assert isinstance(client, GeminiClient)
    assert client.model == "gemini-3-flash-preview"


def test_factory_respects_gemini_model_override(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3-pro-preview")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with patch("bedsheet.llm.gemini.genai"):
        client = make_llm_client()

    from bedsheet.llm.gemini import GeminiClient

    assert isinstance(client, GeminiClient)
    assert client.model == "gemini-3-pro-preview"


def test_factory_picks_gemini_when_both_keys_set(monkeypatch):
    """Gemini takes priority when both keys are set. This is the documented
    contract — it prevents a user with a stray ANTHROPIC_API_KEY in their
    shell from being silently routed to Anthropic."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

    with patch("bedsheet.llm.gemini.genai"), patch("bedsheet.llm.anthropic.anthropic"):
        client = make_llm_client()

    from bedsheet.llm.gemini import GeminiClient

    assert isinstance(client, GeminiClient)


def test_factory_picks_anthropic_when_only_anthropic_key_set(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-key")
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

    with patch("bedsheet.llm.anthropic.anthropic"):
        client = make_llm_client()

    from bedsheet.llm.anthropic import AnthropicClient

    assert isinstance(client, AnthropicClient)
    assert client.model == "claude-sonnet-4-5-20250929"


def test_factory_respects_anthropic_model_override(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

    with patch("bedsheet.llm.anthropic.anthropic"):
        client = make_llm_client()

    from bedsheet.llm.anthropic import AnthropicClient

    assert isinstance(client, AnthropicClient)
    assert client.model == "claude-3-haiku-20240307"


def test_factory_raises_when_no_keys_set(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="No LLM API key"):
        make_llm_client()
