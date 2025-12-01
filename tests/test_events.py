# tests/test_events.py
from bedsheet.events import (
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    CompletionEvent,
    ErrorEvent,
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


def test_routing_event():
    from bedsheet.events import RoutingEvent
    event = RoutingEvent(agent_name="FinanceAgent", task="Analyze revenue")
    assert event.agent_name == "FinanceAgent"
    assert event.task == "Analyze revenue"
    assert event.type == "routing"


def test_delegation_event():
    from bedsheet.events import DelegationEvent
    delegations = [
        {"agent_name": "FinanceAgent", "task": "Get revenue"},
        {"agent_name": "ResearchAgent", "task": "Get competitors"},
    ]
    event = DelegationEvent(delegations=delegations)
    assert event.delegations == delegations
    assert event.type == "delegation"


def test_collaborator_start_event():
    from bedsheet.events import CollaboratorStartEvent
    event = CollaboratorStartEvent(agent_name="FinanceAgent", task="Analyze Q3")
    assert event.agent_name == "FinanceAgent"
    assert event.task == "Analyze Q3"
    assert event.type == "collaborator_start"


def test_collaborator_event():
    from bedsheet.events import CollaboratorEvent, ToolCallEvent
    inner = ToolCallEvent(tool_name="get_data", tool_input={}, call_id="123")
    event = CollaboratorEvent(agent_name="FinanceAgent", inner_event=inner)
    assert event.agent_name == "FinanceAgent"
    assert event.inner_event == inner
    assert event.type == "collaborator"


def test_collaborator_complete_event():
    from bedsheet.events import CollaboratorCompleteEvent
    event = CollaboratorCompleteEvent(agent_name="FinanceAgent", response="Revenue is $2.3M")
    assert event.agent_name == "FinanceAgent"
    assert event.response == "Revenue is $2.3M"
    assert event.type == "collaborator_complete"
