import pytest
from bedsheet.memory.in_memory import InMemory
from bedsheet.memory.base import Message, Memory


def test_in_memory_implements_protocol():
    mem = InMemory()
    assert isinstance(mem, Memory)


@pytest.mark.asyncio
async def test_get_messages_empty_session():
    mem = InMemory()
    messages = await mem.get_messages("session-1")
    assert messages == []


@pytest.mark.asyncio
async def test_add_and_get_message():
    mem = InMemory()
    msg = Message(role="user", content="Hello")
    await mem.add_message("session-1", msg)

    messages = await mem.get_messages("session-1")
    assert len(messages) == 1
    assert messages[0].content == "Hello"


@pytest.mark.asyncio
async def test_add_messages_batch():
    mem = InMemory()
    msgs = [
        Message(role="user", content="Hi"),
        Message(role="assistant", content="Hello!"),
    ]
    await mem.add_messages("session-1", msgs)

    messages = await mem.get_messages("session-1")
    assert len(messages) == 2


@pytest.mark.asyncio
async def test_sessions_are_isolated():
    mem = InMemory()
    await mem.add_message("session-1", Message(role="user", content="A"))
    await mem.add_message("session-2", Message(role="user", content="B"))

    msgs1 = await mem.get_messages("session-1")
    msgs2 = await mem.get_messages("session-2")

    assert len(msgs1) == 1
    assert msgs1[0].content == "A"
    assert len(msgs2) == 1
    assert msgs2[0].content == "B"


@pytest.mark.asyncio
async def test_clear_session():
    mem = InMemory()
    await mem.add_message("session-1", Message(role="user", content="Hello"))
    await mem.clear("session-1")

    messages = await mem.get_messages("session-1")
    assert messages == []
