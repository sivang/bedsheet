"""Factory for creating LLM clients from environment variables.

Priority:
  GEMINI_API_KEY  → GeminiClient  (model: GEMINI_MODEL or gemini-2.0-flash-exp)
  ANTHROPIC_API_KEY → AnthropicClient  (model: ANTHROPIC_MODEL or claude-sonnet-4-5-20250929)
"""

import os

from bedsheet.llm.base import LLMClient


def make_llm_client() -> LLMClient:
    """Return an LLM client based on available environment variables."""
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        from bedsheet.llm.gemini import GeminiClient

        model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-exp")
        return GeminiClient(api_key=gemini_key, model=model)

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        from bedsheet.llm.anthropic import AnthropicClient

        model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
        return AnthropicClient(api_key=anthropic_key, model=model)

    raise RuntimeError("No LLM API key found. Set GEMINI_API_KEY or ANTHROPIC_API_KEY.")
