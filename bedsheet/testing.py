"""Testing utilities for Bedsheet Agents."""
from dataclasses import dataclass, field

from bedsheet.llm.base import LLMResponse, ToolCall, ToolDefinition
from bedsheet.memory.base import Message


@dataclass
class MockResponse:
    """A mock response for testing."""
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    thinking: str | None = None


class MockLLMClient:
    """Mock LLM client for testing agent logic without API calls."""

    def __init__(self, responses: list[MockResponse]) -> None:
        self._responses = iter(responses)

    async def chat(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Return the next mock response."""
        response = next(self._responses)

        stop_reason = "tool_use" if response.tool_calls else "end_turn"

        return LLMResponse(
            text=response.text,
            tool_calls=response.tool_calls,
            stop_reason=stop_reason,
            thinking=response.thinking,
        )
