"""In-memory storage for development and testing."""
from bedsheet.memory.base import Message


class InMemory:
    """Dict-based memory storage for development and testing."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[Message]] = {}

    async def get_messages(self, session_id: str) -> list[Message]:
        """Retrieve all messages for a session."""
        return list(self._sessions.get(session_id, []))

    async def add_message(self, session_id: str, message: Message) -> None:
        """Add a message to a session's history."""
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append(message)

    async def add_messages(self, session_id: str, messages: list[Message]) -> None:
        """Add multiple messages to a session's history."""
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].extend(messages)

    async def clear(self, session_id: str) -> None:
        """Clear all messages for a session."""
        self._sessions.pop(session_id, None)
