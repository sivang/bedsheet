import pytest
import asyncio
from bedsheet.agent import Agent
from bedsheet.action_group import ActionGroup
from bedsheet.memory.in_memory import InMemory
from bedsheet.testing import MockLLMClient, MockResponse
from bedsheet.events import CompletionEvent, ToolCallEvent, ToolResultEvent, ErrorEvent
from bedsheet.llm.base import ToolCall


def test_agent_creation():
    agent = Agent(
        name="TestAgent",
        instruction="You are a test agent.",
        model_client=MockLLMClient(responses=[]),
    )
    assert agent.name == "TestAgent"
    assert agent.instruction == "You are a test agent."


def test_agent_default_memory():
    agent = Agent(
        name="TestAgent",
        instruction="Test",
        model_client=MockLLMClient(responses=[]),
    )
    # Should have InMemory by default
    assert agent.memory is not None


def test_agent_default_orchestration_template():
    agent = Agent(
        name="TestAgent",
        instruction="Test",
        model_client=MockLLMClient(responses=[]),
    )
    # Should have default template
    assert "$instruction$" in agent.orchestration_template


def test_agent_custom_orchestration_template():
    agent = Agent(
        name="TestAgent",
        instruction="Be helpful.",
        orchestration_template="Custom: $instruction$ - $agent_name$",
        model_client=MockLLMClient(responses=[]),
    )
    assert agent.orchestration_template == "Custom: $instruction$ - $agent_name$"


def test_agent_custom_memory():
    memory = InMemory()
    agent = Agent(
        name="TestAgent",
        instruction="Test",
        model_client=MockLLMClient(responses=[]),
        memory=memory,
    )
    assert agent.memory is memory


def test_agent_add_action_group():
    agent = Agent(
        name="TestAgent",
        instruction="Test",
        model_client=MockLLMClient(responses=[]),
    )

    group = ActionGroup(name="TestActions")

    @group.action(name="greet", description="Greet")
    async def greet(name: str) -> str:
        return f"Hello, {name}!"

    agent.add_action_group(group)

    # Agent should have the action registered
    action = agent.get_action("greet")
    assert action is not None
    assert action.name == "greet"


def test_agent_get_action_not_found():
    agent = Agent(
        name="TestAgent",
        instruction="Test",
        model_client=MockLLMClient(responses=[]),
    )

    action = agent.get_action("nonexistent")
    assert action is None


@pytest.mark.asyncio
async def test_agent_invoke_simple_completion():
    """Test agent with LLM that returns text directly (no tool calls)."""
    mock = MockLLMClient(responses=[
        MockResponse(text="Hello! How can I help you?")
    ])

    agent = Agent(
        name="TestAgent",
        instruction="You are helpful.",
        model_client=mock,
    )

    events = []
    async for event in agent.invoke(session_id="test-123", input_text="Hi"):
        events.append(event)

    # Should have exactly one completion event
    assert len(events) == 1
    assert isinstance(events[0], CompletionEvent)
    assert events[0].response == "Hello! How can I help you?"


@pytest.mark.asyncio
async def test_agent_invoke_with_tool_call():
    """Test agent that calls a tool and then responds."""
    mock = MockLLMClient(responses=[
        MockResponse(tool_calls=[
            ToolCall(id="call_1", name="get_weather", input={"city": "SF"})
        ]),
        MockResponse(text="The weather in SF is sunny and 72°F."),
    ])

    agent = Agent(
        name="WeatherAgent",
        instruction="You help with weather.",
        model_client=mock,
    )

    group = ActionGroup(name="Weather")

    @group.action(name="get_weather", description="Get weather for a city")
    async def get_weather(city: str) -> dict:
        return {"city": city, "temp": 72, "condition": "sunny"}

    agent.add_action_group(group)

    events = []
    async for event in agent.invoke(session_id="test-123", input_text="Weather in SF?"):
        events.append(event)

    # Should have: ToolCallEvent, ToolResultEvent, CompletionEvent
    assert len(events) == 3

    assert isinstance(events[0], ToolCallEvent)
    assert events[0].tool_name == "get_weather"
    assert events[0].tool_input == {"city": "SF"}

    assert isinstance(events[1], ToolResultEvent)
    assert events[1].call_id == "call_1"
    assert events[1].result == {"city": "SF", "temp": 72, "condition": "sunny"}
    assert events[1].error is None

    assert isinstance(events[2], CompletionEvent)
    assert "sunny" in events[2].response


@pytest.mark.asyncio
async def test_agent_parallel_tool_calls():
    """Test agent executes multiple tool calls in parallel."""
    mock = MockLLMClient(responses=[
        MockResponse(tool_calls=[
            ToolCall(id="call_1", name="get_weather", input={"city": "SF"}),
            ToolCall(id="call_2", name="get_weather", input={"city": "NYC"}),
        ]),
        MockResponse(text="SF is sunny, NYC is cloudy."),
    ])

    agent = Agent(
        name="WeatherAgent",
        instruction="You help with weather.",
        model_client=mock,
    )

    execution_order = []

    group = ActionGroup(name="Weather")

    @group.action(name="get_weather", description="Get weather")
    async def get_weather(city: str) -> dict:
        execution_order.append(f"start_{city}")
        await asyncio.sleep(0.01)  # Small delay to verify parallel execution
        execution_order.append(f"end_{city}")
        return {"city": city, "temp": 72}

    agent.add_action_group(group)

    events = []
    async for event in agent.invoke(session_id="test", input_text="Weather?"):
        events.append(event)

    # Should have: 2 ToolCallEvents, 2 ToolResultEvents, 1 CompletionEvent
    tool_calls = [e for e in events if isinstance(e, ToolCallEvent)]
    tool_results = [e for e in events if isinstance(e, ToolResultEvent)]
    completions = [e for e in events if isinstance(e, CompletionEvent)]

    assert len(tool_calls) == 2
    assert len(tool_results) == 2
    assert len(completions) == 1

    # Verify parallel execution: both should start before either ends
    # If sequential, we'd see: start_SF, end_SF, start_NYC, end_NYC
    # If parallel, we'd see: start_SF, start_NYC, end_*, end_*
    assert execution_order[0].startswith("start_")
    assert execution_order[1].startswith("start_")


@pytest.mark.asyncio
async def test_agent_tool_error_recovery():
    """Test that tool errors are passed to LLM for recovery."""
    mock = MockLLMClient(responses=[
        MockResponse(tool_calls=[
            ToolCall(id="call_1", name="failing_tool", input={})
        ]),
        MockResponse(text="Sorry, the tool failed. Let me help another way."),
    ])

    agent = Agent(
        name="TestAgent",
        instruction="Be helpful.",
        model_client=mock,
    )

    group = ActionGroup(name="Tools")

    @group.action(name="failing_tool", description="A tool that fails")
    async def failing_tool() -> str:
        raise ValueError("Something went wrong!")

    agent.add_action_group(group)

    events = []
    async for event in agent.invoke(session_id="test", input_text="Do something"):
        events.append(event)

    # Should have ToolCallEvent, ToolResultEvent (with error), CompletionEvent
    tool_results = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(tool_results) == 1
    assert tool_results[0].error == "Something went wrong!"
    assert tool_results[0].result is None

    completions = [e for e in events if isinstance(e, CompletionEvent)]
    assert len(completions) == 1


@pytest.mark.asyncio
async def test_agent_unknown_action():
    """Test handling when LLM calls unknown action."""
    mock = MockLLMClient(responses=[
        MockResponse(tool_calls=[
            ToolCall(id="call_1", name="nonexistent", input={})
        ]),
        MockResponse(text="I apologize, that action isn't available."),
    ])

    agent = Agent(
        name="TestAgent",
        instruction="Be helpful.",
        model_client=mock,
    )

    events = []
    async for event in agent.invoke(session_id="test", input_text="Do something"):
        events.append(event)

    tool_results = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(tool_results) == 1
    assert "Unknown action: nonexistent" in tool_results[0].error


@pytest.mark.asyncio
async def test_agent_max_iterations():
    """Test that max iterations stops infinite loops."""
    # LLM always returns tool calls, never completes
    mock = MockLLMClient(responses=[
        MockResponse(tool_calls=[ToolCall(id=f"call_{i}", name="loop", input={})])
        for i in range(20)
    ])

    agent = Agent(
        name="TestAgent",
        instruction="Be helpful.",
        model_client=mock,
        max_iterations=3,
    )

    group = ActionGroup(name="Tools")

    @group.action(name="loop", description="Loops forever")
    async def loop() -> str:
        return "still going"

    agent.add_action_group(group)

    events = []
    async for event in agent.invoke(session_id="test", input_text="Loop"):
        events.append(event)

    # Should hit max iterations and yield ErrorEvent
    error_events = [e for e in events if isinstance(e, ErrorEvent)]
    assert len(error_events) == 1
    assert "Max iterations" in error_events[0].error
    assert error_events[0].recoverable is False
