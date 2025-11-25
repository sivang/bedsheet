"""Redis-backed memory storage for production use."""
import json
from dataclasses import asdict

import redis.asyncio

from bedsheet.memory.base import Message


class RedisMemory:
    """Redis-backed memory storage for production use.

    Works with local Redis, AWS ElastiCache, or Google Cloud Memorystore.
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379",
        prefix: str = "bedsheet:session:",
        ttl: int | None = None,
    ) -> None:
        self._client = redis.asyncio.from_url(url)
        self._prefix = prefix
        self._ttl = ttl

    def _key(self, session_id: str) -> str:
        """Generate Redis key for a session."""
        return f"{self._prefix}{session_id}"

    async def get_messages(self, session_id: str) -> list[Message]:
        """Retrieve all messages for a session."""
        data = await self._client.get(self._key(session_id))
        if data is None:
            return []

        messages_data = json.loads(data)
        return [Message(**msg) for msg in messages_data]

    async def add_message(self, session_id: str, message: Message) -> None:
        """Add a message to a session's history."""
        messages = await self.get_messages(session_id)
        messages.append(message)
        await self._save_messages(session_id, messages)

    async def add_messages(self, session_id: str, messages: list[Message]) -> None:
        """Add multiple messages to a session's history."""
        existing = await self.get_messages(session_id)
        existing.extend(messages)
        await self._save_messages(session_id, existing)

    async def clear(self, session_id: str) -> None:
        """Clear all messages for a session."""
        await self._client.delete(self._key(session_id))

    async def _save_messages(self, session_id: str, messages: list[Message]) -> None:
        """Save messages to Redis."""
        data = json.dumps([asdict(msg) for msg in messages])
        await self._client.set(
            self._key(session_id),
            data,
            ex=self._ttl,
        )
