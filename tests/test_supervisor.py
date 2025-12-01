import pytest
from bedsheet.supervisor import Supervisor
from bedsheet.agent import Agent
from bedsheet.action_group import ActionGroup
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
        CollaboratorStartEvent, CollaboratorCompleteEvent, CompletionEvent
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


# Task 6: Collaborator Events Streaming
@pytest.mark.asyncio
async def test_supervisor_streams_collaborator_events():
    """Test that collaborator tool events are wrapped and streamed."""
    # Collaborator uses a tool, then responds
    collab_group = ActionGroup(name="Data")

    @collab_group.action(name="get_data", description="Get data")
    async def get_data() -> dict:
        return {"value": 123}

    collaborator = Agent(
        name="DataAgent",
        instruction="You fetch data.",
        model_client=MockLLMClient(responses=[
            MockResponse(tool_calls=[
                ToolCall(id="collab_call_1", name="get_data", input={})
            ]),
            MockResponse(text="The value is 123"),
        ]),
    )
    collaborator.add_action_group(collab_group)

    supervisor = Supervisor(
        name="Manager",
        instruction="Coordinate.",
        model_client=MockLLMClient(responses=[
            MockResponse(tool_calls=[
                ToolCall(id="call_1", name="delegate", input={
                    "agent_name": "DataAgent",
                    "task": "Get the value"
                })
            ]),
            MockResponse(text="Got it: 123"),
        ]),
        collaborators=[collaborator],
    )

    events = []
    async for event in supervisor.invoke(session_id="test", input_text="Get data"):
        events.append(event)

    from bedsheet.events import CollaboratorEvent, ToolCallEvent, ToolResultEvent

    # Find wrapped collaborator events
    collab_events = [e for e in events if isinstance(e, CollaboratorEvent)]

    # Should have wrapped ToolCallEvent and ToolResultEvent from collaborator
    inner_tool_calls = [e for e in collab_events if isinstance(e.inner_event, ToolCallEvent)]
    inner_tool_results = [e for e in collab_events if isinstance(e.inner_event, ToolResultEvent)]

    assert len(inner_tool_calls) >= 1
    assert inner_tool_calls[0].agent_name == "DataAgent"
    assert inner_tool_calls[0].inner_event.tool_name == "get_data"

    assert len(inner_tool_results) >= 1


# Task 7: Delegation Error Handling
@pytest.mark.asyncio
async def test_supervisor_handles_unknown_agent():
    """Test supervisor handles delegation to unknown agent."""
    supervisor = Supervisor(
        name="Manager",
        instruction="Coordinate.",
        model_client=MockLLMClient(responses=[
            MockResponse(tool_calls=[
                ToolCall(id="call_1", name="delegate", input={
                    "agent_name": "NonexistentAgent",
                    "task": "Do something"
                })
            ]),
            MockResponse(text="Sorry, that agent doesn't exist."),
        ]),
        collaborators=[],  # No collaborators
    )

    events = []
    async for event in supervisor.invoke(session_id="test", input_text="Help"):
        events.append(event)

    from bedsheet.events import ToolResultEvent, CompletionEvent

    tool_results = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(tool_results) == 1
    assert "Unknown agent" in tool_results[0].error

    # Supervisor should still complete
    completions = [e for e in events if isinstance(e, CompletionEvent)]
    assert len(completions) == 1


@pytest.mark.asyncio
async def test_supervisor_handles_collaborator_error():
    """Test supervisor handles collaborator that hits max iterations."""
    # Collaborator that never completes
    collaborator = Agent(
        name="BrokenAgent",
        instruction="You are broken.",
        model_client=MockLLMClient(responses=[
            MockResponse(tool_calls=[ToolCall(id=f"c_{i}", name="loop", input={})])
            for i in range(10)
        ]),
        max_iterations=2,
    )

    loop_group = ActionGroup(name="Loop")

    @loop_group.action(name="loop", description="Loop")
    async def loop() -> str:
        return "looping"

    collaborator.add_action_group(loop_group)

    supervisor = Supervisor(
        name="Manager",
        instruction="Coordinate.",
        model_client=MockLLMClient(responses=[
            MockResponse(tool_calls=[
                ToolCall(id="call_1", name="delegate", input={
                    "agent_name": "BrokenAgent",
                    "task": "Do something"
                })
            ]),
            MockResponse(text="The agent had an error."),
        ]),
        collaborators=[collaborator],
    )

    events = []
    async for event in supervisor.invoke(session_id="test", input_text="Help"):
        events.append(event)

    from bedsheet.events import CollaboratorCompleteEvent, CompletionEvent

    # Collaborator should complete with error
    collab_completes = [e for e in events if isinstance(e, CollaboratorCompleteEvent)]
    assert len(collab_completes) == 1
    assert "Error" in collab_completes[0].response or "Max iterations" in collab_completes[0].response

    # Supervisor should still complete
    completions = [e for e in events if isinstance(e, CompletionEvent)]
    assert len(completions) == 1


# Task 8: Parallel Delegation
@pytest.mark.asyncio
async def test_supervisor_parallel_delegation():
    """Test supervisor delegates to multiple agents in parallel."""
    finance = Agent(
        name="FinanceAgent",
        instruction="Finance.",
        model_client=MockLLMClient(responses=[
            MockResponse(text="Revenue: $2M"),
        ]),
    )

    research = Agent(
        name="ResearchAgent",
        instruction="Research.",
        model_client=MockLLMClient(responses=[
            MockResponse(text="Competitor: $1.5M"),
        ]),
    )

    supervisor = Supervisor(
        name="Manager",
        instruction="Coordinate.",
        model_client=MockLLMClient(responses=[
            MockResponse(tool_calls=[
                ToolCall(id="call_1", name="delegate", input={
                    "delegations": [
                        {"agent_name": "FinanceAgent", "task": "Get revenue"},
                        {"agent_name": "ResearchAgent", "task": "Get competitor data"},
                    ]
                })
            ]),
            MockResponse(text="We have $2M vs competitor $1.5M"),
        ]),
        collaborators=[finance, research],
    )

    events = []
    async for event in supervisor.invoke(session_id="test", input_text="Compare"):
        events.append(event)

    from bedsheet.events import CollaboratorStartEvent, CollaboratorCompleteEvent, DelegationEvent

    # Should have DelegationEvent
    delegation_events = [e for e in events if isinstance(e, DelegationEvent)]
    assert len(delegation_events) == 1
    assert len(delegation_events[0].delegations) == 2

    # Should have 2 collaborator starts and completes
    starts = [e for e in events if isinstance(e, CollaboratorStartEvent)]
    completes = [e for e in events if isinstance(e, CollaboratorCompleteEvent)]

    assert len(starts) == 2
    assert len(completes) == 2

    agent_names = {s.agent_name for s in starts}
    assert agent_names == {"FinanceAgent", "ResearchAgent"}


# Task 9: Router Mode
@pytest.mark.asyncio
async def test_router_mode_direct_handoff():
    """Test router mode hands off entirely to one agent."""
    technical = Agent(
        name="TechnicalSupport",
        instruction="Handle technical issues.",
        model_client=MockLLMClient(responses=[
            MockResponse(text="Have you tried turning it off and on again?"),
        ]),
    )

    router = Supervisor(
        name="Router",
        instruction="Route requests.",
        model_client=MockLLMClient(responses=[
            MockResponse(tool_calls=[
                ToolCall(id="call_1", name="delegate", input={
                    "agent_name": "TechnicalSupport",
                    "task": "User can't log in"
                })
            ]),
            # In router mode, after delegation the router should just pass through
            # the collaborator's response without synthesis
        ]),
        collaborators=[technical],
        collaboration_mode="router",
    )

    events = []
    async for event in router.invoke(session_id="test", input_text="I can't log in"):
        events.append(event)

    from bedsheet.events import RoutingEvent, CompletionEvent

    # Should have RoutingEvent (not DelegationEvent in router mode)
    routing_events = [e for e in events if isinstance(e, RoutingEvent)]
    assert len(routing_events) == 1
    assert routing_events[0].agent_name == "TechnicalSupport"

    # Final completion should be collaborator's response directly
    completions = [e for e in events if isinstance(e, CompletionEvent)]
    assert len(completions) == 1
    assert "turning it off and on" in completions[0].response
