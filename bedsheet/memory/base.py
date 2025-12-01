"""Memory protocol and message types."""
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable


@dataclass
class Message:
    """A message in the conversation history."""
    role: Literal["user", "assistant", "tool_result"]
    content: str | None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


@runtime_checkable
class Memory(Protocol):
    """Protocol for conversation memory storage."""

    async def get_messages(self, session_id: str) -> list[Message]:
        """Retrieve all messages for a session."""
        ...

    async def add_message(self, session_id: str, message: Message) -> None:
        """Add a message to a session's history."""
        ...

    async def add_messages(self, session_id: str, messages: list[Message]) -> None:
        """Add multiple messages to a session's history."""
        ...

    async def clear(self, session_id: str) -> None:
        """Clear all messages for a session."""
        ...
