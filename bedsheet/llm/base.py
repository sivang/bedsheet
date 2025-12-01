"""LLM client protocol and response types."""
from dataclasses import dataclass
from typing import Any, AsyncIterator, Protocol, runtime_checkable

from bedsheet.memory.base import Message


@dataclass
class ToolCall:
    """A tool call requested by the LLM."""
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LLMResponse:
    """Response from an LLM call."""
    text: str | None
    tool_calls: list[ToolCall]
    stop_reason: str = "end_turn"
    thinking: str | None = None


@dataclass
class ToolDefinition:
    """Definition of a tool for the LLM."""
    name: str
    description: str
    input_schema: dict[str, Any]


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM clients."""

    async def chat(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Send messages to the LLM and get a response."""
        ...

    def chat_stream(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[str | LLMResponse]:
        """Stream response. Yields str tokens, then final LLMResponse."""
        ...
