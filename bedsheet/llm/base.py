"""LLM client protocol and response types."""
from dataclasses import dataclass, field
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
    parsed_output: Any = None  # Populated when output_schema is used


@dataclass
class ToolDefinition:
    """Definition of a tool for the LLM."""
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class OutputSchema:
    """Schema for structured output.

    Can be initialized with a Pydantic model or a JSON schema dict.
    """
    schema: dict[str, Any]
    _pydantic_model: Any = field(default=None, repr=False)

    @classmethod
    def from_pydantic(cls, model: Any) -> "OutputSchema":
        """Create from a Pydantic BaseModel class."""
        # Get JSON schema from Pydantic model
        schema = model.model_json_schema()
        return cls(schema=schema, _pydantic_model=model)

    @classmethod
    def from_dict(cls, schema: dict[str, Any]) -> "OutputSchema":
        """Create from a JSON schema dict."""
        return cls(schema=schema)


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM clients."""

    async def chat(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
        output_schema: OutputSchema | None = None,
    ) -> LLMResponse:
        """Send messages to the LLM and get a response."""
        ...

    def chat_stream(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
        output_schema: OutputSchema | None = None,
    ) -> AsyncIterator[str | LLMResponse]:
        """Stream response. Yields str tokens, then final LLMResponse."""
        ...
