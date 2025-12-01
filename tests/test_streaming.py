"""Tests for token streaming functionality."""
import pytest
from bedsheet import Agent, Supervisor
from bedsheet.testing import MockLLMClient, MockResponse
from bedsheet.llm.base import ToolCall
from bedsheet.events import TextTokenEvent, CollaboratorEvent, CompletionEvent


@pytest.mark.asyncio
async def test_mock_client_chat_stream_yields_tokens():
    """Test that MockLLMClient.chat_stream yields tokens then LLMResponse."""
    mock = MockLLMClient(responses=[
        MockResponse(text="Hello world"),
    ])

    tokens = []
    final_response = None

    async for chunk in mock.chat_stream([], "system"):
        if isinstance(chunk, str):
            tokens.append(chunk)
        else:
            final_response = chunk

    # Should have yielded tokens
    assert len(tokens) > 0
    assert "".join(tokens).replace(" ", "") == "Helloworld"

    # Should have yielded final LLMResponse
    assert final_response is not None
    assert final_response.text == "Hello world"


@pytest.mark.asyncio
async def test_agent_yields_text_token_events_when_streaming():
    """Test that Agent yields TextTokenEvent when stream=True."""
    mock = MockLLMClient(responses=[
        MockResponse(text="Hi there"),
    ])

    agent = Agent(
        name="TestAgent",
        instruction="Test",
        model_client=mock,
    )

    events = []
    async for event in agent.invoke("session", "test", stream=True):
        events.append(event)

    # Should have TextTokenEvents
    token_events = [e for e in events if isinstance(e, TextTokenEvent)]
    assert len(token_events) > 0

    # Should end with CompletionEvent
    assert isinstance(events[-1], CompletionEvent)


@pytest.mark.asyncio
async def test_supervisor_wraps_collaborator_token_events():
    """Test that Supervisor wraps collaborator TextTokenEvents in CollaboratorEvent."""
    mock = MockLLMClient(responses=[
        # Supervisor delegates
        MockResponse(tool_calls=[
            ToolCall(id="d1", name="delegate", input={
                "delegations": [{"agent_name": "Worker", "task": "Do work"}]
            })
        ]),
        # Supervisor synthesizes
        MockResponse(text="Done"),
    ])

    worker_mock = MockLLMClient(responses=[
        MockResponse(text="Working"),
    ])

    worker = Agent(
        name="Worker",
        instruction="Work",
        model_client=worker_mock,
    )

    supervisor = Supervisor(
        name="Boss",
        instruction="Manage",
        model_client=mock,
        collaborators=[worker],
    )

    events = []
    async for event in supervisor.invoke("session", "test", stream=True):
        events.append(event)

    # Should have CollaboratorEvents wrapping TextTokenEvents
    collab_token_events = [
        e for e in events
        if isinstance(e, CollaboratorEvent) and isinstance(e.inner_event, TextTokenEvent)
    ]
    assert len(collab_token_events) > 0
    assert collab_token_events[0].agent_name == "Worker"
