"""Integration tests with real Claude API.

Run with: pytest tests/integration/ -v
Requires: ANTHROPIC_API_KEY environment variable
"""
import os
import pytest

from bedsheet import Agent, ActionGroup
from bedsheet.llm import AnthropicClient
from bedsheet.memory import InMemory
from bedsheet.events import CompletionEvent, ToolCallEvent, ToolResultEvent


pytestmark = pytest.mark.skipif(
    os.getenv("ANTHROPIC_API_KEY") is None,
    reason="ANTHROPIC_API_KEY not set"
)


@pytest.mark.asyncio
async def test_real_simple_chat():
    """Test simple chat with real Claude API."""
    client = AnthropicClient()
    agent = Agent(
        name="TestAgent",
        instruction="You are a helpful assistant. Respond briefly.",
        model_client=client,
        memory=InMemory(),
    )

    events = []
    async for event in agent.invoke(
        session_id="integration-test",
        input_text="Say 'hello' and nothing else."
    ):
        events.append(event)

    assert len(events) >= 1
    assert isinstance(events[-1], CompletionEvent)
    assert "hello" in events[-1].response.lower()


@pytest.mark.asyncio
async def test_real_tool_call():
    """Test tool calling with real Claude API."""
    client = AnthropicClient()
    agent = Agent(
        name="WeatherAgent",
        instruction="You help with weather. Use the get_weather tool when asked about weather.",
        model_client=client,
        memory=InMemory(),
    )

    group = ActionGroup(name="Weather")

    @group.action(name="get_weather", description="Get weather for a city")
    async def get_weather(city: str) -> dict:
        return {"city": city, "temp": 72, "condition": "sunny"}

    agent.add_action_group(group)

    events = []
    async for event in agent.invoke(
        session_id="integration-test",
        input_text="What's the weather in San Francisco?"
    ):
        events.append(event)

    # Should have tool call, result, and completion
    tool_calls = [e for e in events if isinstance(e, ToolCallEvent)]
    tool_results = [e for e in events if isinstance(e, ToolResultEvent)]
    completions = [e for e in events if isinstance(e, CompletionEvent)]

    assert len(tool_calls) >= 1
    assert len(tool_results) >= 1
    assert len(completions) == 1
