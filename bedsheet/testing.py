"""Testing utilities for Bedsheet Agents."""
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from bedsheet.llm.base import LLMResponse, OutputSchema, ToolCall, ToolDefinition
from bedsheet.memory.base import Message


@dataclass
class MockResponse:
    """A mock response for testing."""
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    thinking: str | None = None
    parsed_output: Any = None  # For structured output testing


class MockLLMClient:
    """Mock LLM client for testing agent logic without API calls."""

    def __init__(self, responses: list[MockResponse]) -> None:
        self._responses = iter(responses)

    def _get_next_response(self) -> MockResponse:
        """Get the next mock response from the queue."""
        return next(self._responses)

    async def chat(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
        output_schema: OutputSchema | None = None,
    ) -> LLMResponse:
        """Return the next mock response."""
        response = self._get_next_response()

        stop_reason = "tool_use" if response.tool_calls else "end_turn"

        return LLMResponse(
            text=response.text,
            tool_calls=response.tool_calls,
            stop_reason=stop_reason,
            thinking=response.thinking,
            parsed_output=response.parsed_output,
        )

    async def chat_stream(
        self,
        messages: list,
        system: str,
        tools: list | None = None,
        output_schema: OutputSchema | None = None,
    ) -> AsyncIterator[str | LLMResponse]:
        """Stream mock response - yields tokens then final LLMResponse."""
        response = self._get_next_response()

        # Stream text tokens (word by word for readability)
        if response.text:
            words = response.text.split(' ')
            for i, word in enumerate(words):
                if i > 0:
                    yield ' '
                yield word

        # Yield final response for tool calls
        yield LLMResponse(
            text=response.text,
            tool_calls=response.tool_calls or [],
            stop_reason="end_turn",
            parsed_output=response.parsed_output,
        )
