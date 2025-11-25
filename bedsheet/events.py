"""Event types for streaming agent execution."""
from dataclasses import dataclass, field
from typing import Any, Literal, Union


@dataclass
class ThinkingEvent:
    """Emitted when the LLM is thinking (extended thinking mode)."""
    content: str
    type: Literal["thinking"] = field(default="thinking", init=False)


@dataclass
class ToolCallEvent:
    """Emitted when the LLM requests a tool call."""
    tool_name: str
    tool_input: dict[str, Any]
    call_id: str
    type: Literal["tool_call"] = field(default="tool_call", init=False)


@dataclass
class ToolResultEvent:
    """Emitted after a tool call completes."""
    call_id: str
    result: Any
    error: str | None = None
    type: Literal["tool_result"] = field(default="tool_result", init=False)


@dataclass
class CompletionEvent:
    """Emitted when the agent produces a final response."""
    response: str
    type: Literal["completion"] = field(default="completion", init=False)


@dataclass
class ErrorEvent:
    """Emitted when an error occurs during execution."""
    error: str
    recoverable: bool = False
    type: Literal["error"] = field(default="error", init=False)


Event = Union[ThinkingEvent, ToolCallEvent, ToolResultEvent, CompletionEvent, ErrorEvent]
