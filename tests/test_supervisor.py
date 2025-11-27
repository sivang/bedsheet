import pytest
from bedsheet.supervisor import Supervisor
from bedsheet.agent import Agent
from bedsheet.testing import MockLLMClient, MockResponse
from bedsheet.llm.base import ToolCall


def test_supervisor_creation():
    collaborator = Agent(
        name="FinanceAgent",
        instruction="You analyze financial data.",
        model_client=MockLLMClient(responses=[]),
    )

    supervisor = Supervisor(
        name="ProjectManager",
        instruction="You coordinate tasks.",
        model_client=MockLLMClient(responses=[]),
        collaborators=[collaborator],
    )

    assert supervisor.name == "ProjectManager"
    assert "FinanceAgent" in supervisor.collaborators


def test_supervisor_is_agent():
    supervisor = Supervisor(
        name="Manager",
        instruction="Coordinate.",
        model_client=MockLLMClient(responses=[]),
        collaborators=[],
    )

    assert isinstance(supervisor, Agent)


def test_supervisor_default_mode_is_supervisor():
    supervisor = Supervisor(
        name="Manager",
        instruction="Coordinate.",
        model_client=MockLLMClient(responses=[]),
        collaborators=[],
    )

    assert supervisor.collaboration_mode == "supervisor"


def test_supervisor_router_mode():
    supervisor = Supervisor(
        name="Router",
        instruction="Route requests.",
        model_client=MockLLMClient(responses=[]),
        collaborators=[],
        collaboration_mode="router",
    )

    assert supervisor.collaboration_mode == "router"


# Task 3: Supervisor Orchestration Templates
def test_supervisor_has_collaborators_in_template():
    collaborator = Agent(
        name="FinanceAgent",
        instruction="You analyze financial data.",
        model_client=MockLLMClient(responses=[]),
    )

    supervisor = Supervisor(
        name="Manager",
        instruction="You coordinate tasks.",
        model_client=MockLLMClient(responses=[]),
        collaborators=[collaborator],
    )

    system_prompt = supervisor._render_system_prompt()
    assert "FinanceAgent" in system_prompt
    assert "analyze financial data" in system_prompt


def test_supervisor_template_has_delegate_instruction():
    supervisor = Supervisor(
        name="Manager",
        instruction="Coordinate.",
        model_client=MockLLMClient(responses=[]),
        collaborators=[],
    )

    system_prompt = supervisor._render_system_prompt()
    assert "delegate" in system_prompt.lower()


def test_router_has_different_template():
    collaborator = Agent(
        name="Support",
        instruction="Handle support.",
        model_client=MockLLMClient(responses=[]),
    )

    router = Supervisor(
        name="Router",
        instruction="Route requests.",
        model_client=MockLLMClient(responses=[]),
        collaborators=[collaborator],
        collaboration_mode="router",
    )

    system_prompt = router._render_system_prompt()
    assert "route" in system_prompt.lower()


# Task 4: Built-in Delegate Action (Single Delegation)
def test_supervisor_has_delegate_tool():
    supervisor = Supervisor(
        name="Manager",
        instruction="Coordinate.",
        model_client=MockLLMClient(responses=[]),
        collaborators=[],
    )

    tools = supervisor.get_tool_definitions()
    tool_names = [t.name for t in tools]
    assert "delegate" in tool_names


def test_delegate_tool_schema():
    supervisor = Supervisor(
        name="Manager",
        instruction="Coordinate.",
        model_client=MockLLMClient(responses=[]),
        collaborators=[],
    )

    tools = supervisor.get_tool_definitions()
    delegate_tool = next(t for t in tools if t.name == "delegate")

    # Should have agent_name and task parameters
    props = delegate_tool.input_schema["properties"]
    assert "agent_name" in props
    assert "task" in props


# Task 5: Execute Single Delegation
@pytest.mark.asyncio
async def test_supervisor_delegates_to_collaborator():
    """Test supervisor successfully delegates to a collaborator."""
    # Collaborator will respond directly
    collaborator = Agent(
        name="FinanceAgent",
        instruction="You analyze financial data.",
        model_client=MockLLMClient(responses=[
            MockResponse(text="Revenue is $2.3M"),
        ]),
    )

    # Supervisor calls delegate, then synthesizes
    supervisor = Supervisor(
        name="Manager",
        instruction="Coordinate tasks.",
        model_client=MockLLMClient(responses=[
            MockResponse(tool_calls=[
                ToolCall(id="call_1", name="delegate", input={
                    "agent_name": "FinanceAgent",
                    "task": "Get Q3 revenue"
                })
            ]),
            MockResponse(text="Based on the finance team: Revenue is $2.3M"),
        ]),
        collaborators=[collaborator],
    )

    events = []
    async for event in supervisor.invoke(session_id="test", input_text="What's our revenue?"):
        events.append(event)

    # Should have delegation events
    from bedsheet.events import (
        CollaboratorStartEvent, CollaboratorCompleteEvent,
        ToolCallEvent, ToolResultEvent, CompletionEvent
    )

    collab_starts = [e for e in events if isinstance(e, CollaboratorStartEvent)]
    collab_completes = [e for e in events if isinstance(e, CollaboratorCompleteEvent)]
    completions = [e for e in events if isinstance(e, CompletionEvent)]

    assert len(collab_starts) == 1
    assert collab_starts[0].agent_name == "FinanceAgent"

    assert len(collab_completes) == 1
    assert collab_completes[0].agent_name == "FinanceAgent"
    assert "2.3M" in collab_completes[0].response

    assert len(completions) == 1
    assert "2.3M" in completions[0].response
