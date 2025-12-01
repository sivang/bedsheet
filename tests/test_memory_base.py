from bedsheet.memory.base import Message, Memory
from typing import runtime_checkable


def test_message_user():
    msg = Message(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_message_assistant():
    msg = Message(role="assistant", content="Hi there!")
    assert msg.role == "assistant"
    assert msg.content == "Hi there!"


def test_message_with_tool_calls():
    msg = Message(
        role="assistant",
        content=None,
        tool_calls=[{"id": "call_1", "name": "get_weather", "input": {"city": "SF"}}]
    )
    assert msg.tool_calls is not None
    assert len(msg.tool_calls) == 1


def test_message_tool_result():
    msg = Message(
        role="tool_result",
        content='{"temp": 72}',
        tool_call_id="call_1"
    )
    assert msg.role == "tool_result"
    assert msg.tool_call_id == "call_1"


def test_memory_is_protocol():
    assert runtime_checkable(Memory)
