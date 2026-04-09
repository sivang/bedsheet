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
    mock = MockLLMClient(responses=[MockResponse(text="Hello! How can I help you?")])

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
    mock = MockLLMClient(
        responses=[
            MockResponse(
                tool_calls=[
                    ToolCall(id="call_1", name="get_weather", input={"city": "SF"})
                ]
            ),
            MockResponse(text="The weather in SF is sunny and 72°F."),
        ]
    )

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


async def test_agent_preserves_gemini_raw_parts_on_tool_call_message():
    """REGRESSION TEST for the thought-signature middle hop.

    For Gemini 3.x, the SDK requires that on every multi-turn conversation
    the assistant's previous parts (including thought_signature) be echoed
    back exactly as received — otherwise the next turn errors with 400.

    The two halves of the round-trip are tested separately:
      - GeminiClient._parse_response stashes raw parts on
        LLMResponse._gemini_raw_parts (test_gemini.py)
      - GeminiClient._convert_messages echoes them back from
        Message._gemini_parts (test_gemini.py)

    But the middle hop — the agent loop copying the stash from the
    LLMResponse onto the persisted assistant Message — was uncovered.
    If anyone removes those two lines (currently bedsheet/agent.py:190-192),
    both Gemini tests still pass and Gemini 3.x silently breaks at runtime.

    This test uses a stub LLM client that returns an LLMResponse with
    _gemini_raw_parts set, runs one ReAct iteration through the agent
    loop, and asserts the persisted assistant Message carries the
    stash on _gemini_parts.
    """
    from bedsheet.llm.base import LLMResponse, ToolCall as LLMToolCall

    sentinel_parts = ["raw-part-with-thought-signature"]

    class StashingClient:
        def __init__(self):
            self._call = 0

        async def chat(self, messages, system, tools=None, output_schema=None):
            self._call += 1
            if self._call == 1:
                # First call: return a tool-call response with raw parts stashed
                response = LLMResponse(
                    text=None,
                    tool_calls=[LLMToolCall(id="c1", name="echo", input={"x": 1})],
                    stop_reason="tool_use",
                )
                response._gemini_raw_parts = sentinel_parts
                return response
            # Second call: complete the turn (after tool result is fed back)
            return LLMResponse(text="done", tool_calls=[], stop_reason="end_turn")

        async def chat_stream(self, messages, system, tools=None, output_schema=None):
            response = await self.chat(messages, system, tools, output_schema)
            yield response

    agent = Agent(
        name="ThoughtSigAgent",
        instruction="Test agent",
        model_client=StashingClient(),
    )

    group = ActionGroup(name="Tools")

    @group.action(name="echo", description="Echo a value")
    async def echo(x: int) -> int:
        return x

    agent.add_action_group(group)

    events = []
    async for event in agent.invoke(session_id="thought-sig", input_text="Go"):
        events.append(event)

    # The assistant tool-call message should now be in memory
    persisted = await agent.memory.get_messages("thought-sig")

    # Find the assistant message that carries the tool call
    assistant_msgs = [m for m in persisted if m.role == "assistant" and m.tool_calls]
    assert len(assistant_msgs) == 1, (
        f"Expected exactly 1 persisted assistant tool-call message, "
        f"got {len(assistant_msgs)}"
    )

    # THE invariant: the raw parts must have been copied from the
    # LLMResponse to the persisted Message. If this fails, the agent loop's
    # _gemini_parts copy step is missing, and Gemini 3.x will get 400 errors
    # on the next turn because the thought_signature didn't round-trip.
    assert assistant_msgs[0]._gemini_parts is sentinel_parts, (
        "Agent loop did not copy _gemini_raw_parts from LLMResponse onto "
        "the persisted assistant Message. Gemini 3.x will fail on the next "
        "turn because the thought_signature is missing from the echoed-back "
        "parts. See bedsheet/agent.py around the assistant_message construction."
    )


@pytest.mark.asyncio
async def test_agent_parallel_tool_calls():
    """Test agent executes multiple tool calls in parallel."""
    mock = MockLLMClient(
        responses=[
            MockResponse(
                tool_calls=[
                    ToolCall(id="call_1", name="get_weather", input={"city": "SF"}),
                    ToolCall(id="call_2", name="get_weather", input={"city": "NYC"}),
                ]
            ),
            MockResponse(text="SF is sunny, NYC is cloudy."),
        ]
    )

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
    mock = MockLLMClient(
        responses=[
            MockResponse(
                tool_calls=[ToolCall(id="call_1", name="failing_tool", input={})]
            ),
            MockResponse(text="Sorry, the tool failed. Let me help another way."),
        ]
    )

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
    mock = MockLLMClient(
        responses=[
            MockResponse(
                tool_calls=[ToolCall(id="call_1", name="nonexistent", input={})]
            ),
            MockResponse(text="I apologize, that action isn't available."),
        ]
    )

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
    mock = MockLLMClient(
        responses=[
            MockResponse(tool_calls=[ToolCall(id=f"call_{i}", name="loop", input={})])
            for i in range(20)
        ]
    )

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


async def test_agent_invoke_handles_empty_response():
    """REGRESSION TEST for H1: when an LLM returns a response with no text
    AND no tool calls (e.g. an empty Gemini stream after content filtering),
    the agent loop must terminate cleanly with an ErrorEvent on the FIRST
    iteration — not silently retry max_iterations times before yielding a
    generic 'max iterations exceeded' error.

    The previous Gemini chat_stream code accidentally hid this by issuing a
    second non-streaming chat() call on stream end, which usually returned
    non-empty text on the second sample. After the B1 fix correctly stopped
    double-calling, this latent agent-loop gap became reachable.
    """
    # A client that ALWAYS returns empty. If the agent loop is correct, it
    # exits on iteration 1; if it's broken, it'll call this client
    # max_iterations times and we want each call to succeed cleanly so the
    # failure mode is "wrong event count", not StopIteration from a
    # exhausted MockLLMClient response queue.
    from bedsheet.llm.base import LLMResponse

    call_count = {"n": 0}

    class AlwaysEmptyClient:
        async def chat(self, messages, system, tools=None, output_schema=None):
            call_count["n"] += 1
            return LLMResponse(text=None, tool_calls=[], stop_reason="end_turn")

        async def chat_stream(self, messages, system, tools=None, output_schema=None):
            response = await self.chat(messages, system, tools, output_schema)
            yield response

    agent = Agent(
        name="TestAgent",
        instruction="Be helpful.",
        model_client=AlwaysEmptyClient(),
        max_iterations=10,
    )

    events = []
    async for event in agent.invoke(session_id="test", input_text="Hi"):
        events.append(event)

    # The agent must call the LLM exactly once and then bail out — not
    # repeat the call max_iterations times.
    assert call_count["n"] == 1, (
        f"Agent called LLM {call_count['n']} times for an empty response — "
        f"expected exactly 1 (terminate on first empty)."
    )

    # Must yield exactly one ErrorEvent that explains the empty response,
    # NOT a max-iterations error.
    error_events = [e for e in events if isinstance(e, ErrorEvent)]
    assert len(error_events) == 1, (
        f"Expected exactly 1 ErrorEvent, got {len(error_events)}: "
        f"{[e.error for e in error_events]}"
    )
    assert "Max iterations" not in error_events[0].error, (
        "Agent looped max_iterations times instead of catching the empty "
        "response on the first iteration — this is the H1 bug."
    )
    assert (
        "empty" in error_events[0].error.lower()
        or "no" in error_events[0].error.lower()
    )
    assert error_events[0].recoverable is False

    # Must NOT yield CompletionEvent — there's nothing to complete with
    completion_events = [e for e in events if isinstance(e, CompletionEvent)]
    assert len(completion_events) == 0
