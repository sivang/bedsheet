import pytest
from unittest.mock import AsyncMock, patch
from bedsheet.memory.redis import RedisMemory
from bedsheet.memory.base import Message, Memory


def test_redis_memory_implements_protocol():
    with patch("bedsheet.memory.redis.redis"):
        mem = RedisMemory(url="redis://localhost:6379")
        assert isinstance(mem, Memory)


@pytest.mark.asyncio
async def test_redis_memory_get_empty():
    with patch("bedsheet.memory.redis.redis") as mock_redis:
        mock_client = AsyncMock()
        mock_redis.asyncio.from_url.return_value = mock_client
        mock_client.get.return_value = None

        mem = RedisMemory(url="redis://localhost:6379")
        messages = await mem.get_messages("session-1")

        assert messages == []
        mock_client.get.assert_called_once_with("bedsheet:session:session-1")


@pytest.mark.asyncio
async def test_redis_memory_add_and_get():
    with patch("bedsheet.memory.redis.redis") as mock_redis:
        mock_client = AsyncMock()
        mock_redis.asyncio.from_url.return_value = mock_client

        stored_data = None

        async def mock_set(key, value, ex=None):
            nonlocal stored_data
            stored_data = value

        async def mock_get(key):
            return stored_data

        mock_client.set = mock_set
        mock_client.get = mock_get

        mem = RedisMemory(url="redis://localhost:6379")

        msg = Message(role="user", content="Hello")
        await mem.add_message("session-1", msg)

        messages = await mem.get_messages("session-1")
        assert len(messages) == 1
        assert messages[0].role == "user"
        assert messages[0].content == "Hello"


@pytest.mark.asyncio
async def test_redis_memory_clear():
    with patch("bedsheet.memory.redis.redis") as mock_redis:
        mock_client = AsyncMock()
        mock_redis.asyncio.from_url.return_value = mock_client

        mem = RedisMemory(url="redis://localhost:6379")
        await mem.clear("session-1")

        mock_client.delete.assert_called_once_with("bedsheet:session:session-1")


@pytest.mark.asyncio
async def test_redis_memory_ttl():
    with patch("bedsheet.memory.redis.redis") as mock_redis:
        mock_client = AsyncMock()
        mock_redis.asyncio.from_url.return_value = mock_client
        mock_client.get.return_value = None

        mem = RedisMemory(url="redis://localhost:6379", ttl=3600)
        msg = Message(role="user", content="Hello")
        await mem.add_message("session-1", msg)

        # Verify TTL was passed to set
        call_args = mock_client.set.call_args
        assert call_args.kwargs.get("ex") == 3600
