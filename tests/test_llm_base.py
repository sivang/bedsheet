"""Tests for LLM base protocol and response types."""
from bedsheet.llm.base import LLMClient, LLMResponse, ToolCall
from typing import runtime_checkable


def test_tool_call():
    tc = ToolCall(id="call_1", name="get_weather", input={"city": "SF"})
    assert tc.id == "call_1"
    assert tc.name == "get_weather"
    assert tc.input == {"city": "SF"}


def test_llm_response_text_only():
    resp = LLMResponse(text="Hello!", tool_calls=[])
    assert resp.text == "Hello!"
    assert resp.tool_calls == []
    assert resp.stop_reason == "end_turn"


def test_llm_response_with_tool_calls():
    resp = LLMResponse(
        text=None,
        tool_calls=[ToolCall(id="call_1", name="get_weather", input={"city": "SF"})],
        stop_reason="tool_use"
    )
    assert resp.text is None
    assert len(resp.tool_calls) == 1
    assert resp.stop_reason == "tool_use"


def test_llm_client_is_protocol():
    assert runtime_checkable(LLMClient)
