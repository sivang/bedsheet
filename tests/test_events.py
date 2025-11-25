# tests/test_events.py
from bedsheet.events import (
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    CompletionEvent,
    ErrorEvent,
    Event,
)


def test_thinking_event():
    event = ThinkingEvent(content="planning next step")
    assert event.type == "thinking"
    assert event.content == "planning next step"


def test_tool_call_event():
    event = ToolCallEvent(
        tool_name="get_weather",
        tool_input={"city": "SF"},
        call_id="call_123"
    )
    assert event.type == "tool_call"
    assert event.tool_name == "get_weather"
    assert event.tool_input == {"city": "SF"}
    assert event.call_id == "call_123"


def test_tool_result_event_success():
    event = ToolResultEvent(
        call_id="call_123",
        result={"temp": 72}
    )
    assert event.type == "tool_result"
    assert event.result == {"temp": 72}
    assert event.error is None


def test_tool_result_event_error():
    event = ToolResultEvent(
        call_id="call_123",
        result=None,
        error="Connection failed"
    )
    assert event.error == "Connection failed"


def test_completion_event():
    event = CompletionEvent(response="The weather is sunny.")
    assert event.type == "completion"
    assert event.response == "The weather is sunny."


def test_error_event():
    event = ErrorEvent(error="Max iterations exceeded", recoverable=False)
    assert event.type == "error"
    assert event.error == "Max iterations exceeded"
    assert event.recoverable is False
