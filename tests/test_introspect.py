"""Tests for agent introspection module."""
import pytest

from bedsheet import Agent, ActionGroup, Supervisor
from bedsheet.deploy import extract_agent_metadata, AgentMetadata
from bedsheet.testing import MockLLMClient, MockResponse


@pytest.mark.asyncio
async def test_extract_simple_agent_metadata():
    """Test extracting metadata from a simple agent."""
    mock = MockLLMClient([MockResponse(text="ok")])

    agent = Agent(
        name="TestAgent",
        instruction="Test agent for unit testing",
        model_client=mock,
    )

    group = ActionGroup(name="TestGroup", description="Test actions")

    @group.action(name="test_action", description="A test action")
    async def test_fn(arg: str) -> str:
        return arg

    agent.add_action_group(group)

    metadata = extract_agent_metadata(agent)

    assert isinstance(metadata, AgentMetadata)
    assert metadata.name == "TestAgent"
    assert metadata.instruction == "Test agent for unit testing"
    assert metadata.is_supervisor is False
    assert len(metadata.collaborators) == 0
    assert len(metadata.tools) == 1

    tool = metadata.tools[0]
    assert tool.name == "test_action"
    assert tool.description == "A test action"
    assert tool.parameters_schema["type"] == "object"
    assert "arg" in tool.parameters_schema["properties"]


@pytest.mark.asyncio
async def test_extract_agent_with_multiple_tools():
    """Test extracting metadata from agent with multiple tools."""
    mock = MockLLMClient([MockResponse(text="ok")])

    agent = Agent(
        name="MathAgent",
        instruction="Perform math operations",
        model_client=mock,
    )

    group = ActionGroup(name="Math", description="Math operations")

    @group.action(name="add", description="Add two numbers")
    async def add(a: int, b: int) -> int:
        return a + b

    @group.action(name="subtract", description="Subtract two numbers")
    async def subtract(x: int, y: int) -> int:
        return x - y

    agent.add_action_group(group)

    metadata = extract_agent_metadata(agent)

    assert len(metadata.tools) == 2
    tool_names = [t.name for t in metadata.tools]
    assert "add" in tool_names
    assert "subtract" in tool_names


@pytest.mark.asyncio
async def test_extract_supervisor_metadata():
    """Test extracting metadata from a supervisor with collaborators."""
    mock = MockLLMClient([MockResponse(text="ok")])

    # Create collaborator 1
    agent1 = Agent(
        name="Agent1",
        instruction="First collaborator",
        model_client=mock,
    )

    group1 = ActionGroup(name="Group1", description="Group 1 actions")

    @group1.action(name="action1", description="Action 1")
    async def action1(param: str) -> str:
        return param

    agent1.add_action_group(group1)

    # Create collaborator 2
    agent2 = Agent(
        name="Agent2",
        instruction="Second collaborator",
        model_client=mock,
    )

    group2 = ActionGroup(name="Group2", description="Group 2 actions")

    @group2.action(name="action2", description="Action 2")
    async def action2(value: int) -> int:
        return value

    agent2.add_action_group(group2)

    # Create supervisor
    supervisor = Supervisor(
        name="MainSupervisor",
        instruction="Coordinate agents",
        model_client=mock,
        collaborators=[agent1, agent2],
    )

    metadata = extract_agent_metadata(supervisor)

    assert metadata.is_supervisor is True
    assert metadata.name == "MainSupervisor"
    assert metadata.instruction == "Coordinate agents"

    # Supervisor has delegate tool
    assert len(metadata.tools) == 1
    assert metadata.tools[0].name == "delegate"

    # Check collaborators
    assert len(metadata.collaborators) == 2
    collab_names = [c.name for c in metadata.collaborators]
    assert "Agent1" in collab_names
    assert "Agent2" in collab_names

    # Verify collaborator metadata
    for collab in metadata.collaborators:
        assert isinstance(collab, AgentMetadata)
        assert collab.is_supervisor is False
        assert len(collab.tools) == 1


@pytest.mark.asyncio
async def test_extract_nested_supervisor_metadata():
    """Test extracting metadata from a supervisor with nested supervisors."""
    mock = MockLLMClient([MockResponse(text="ok")])

    # Create leaf agent
    leaf = Agent(
        name="LeafAgent",
        instruction="Leaf agent",
        model_client=mock,
    )

    group = ActionGroup(name="LeafGroup", description="Leaf actions")

    @group.action(name="leaf_action", description="Leaf action")
    async def leaf_action() -> str:
        return "done"

    leaf.add_action_group(group)

    # Create sub-supervisor
    sub_supervisor = Supervisor(
        name="SubSupervisor",
        instruction="Sub-level supervisor",
        model_client=mock,
        collaborators=[leaf],
    )

    # Create top-level supervisor
    top_supervisor = Supervisor(
        name="TopSupervisor",
        instruction="Top-level supervisor",
        model_client=mock,
        collaborators=[sub_supervisor],
    )

    metadata = extract_agent_metadata(top_supervisor)

    assert metadata.is_supervisor is True
    assert len(metadata.collaborators) == 1

    sub_metadata = metadata.collaborators[0]
    assert sub_metadata.name == "SubSupervisor"
    assert sub_metadata.is_supervisor is True
    assert len(sub_metadata.collaborators) == 1

    leaf_metadata = sub_metadata.collaborators[0]
    assert leaf_metadata.name == "LeafAgent"
    assert leaf_metadata.is_supervisor is False
    assert len(leaf_metadata.tools) == 1
    assert leaf_metadata.tools[0].name == "leaf_action"


@pytest.mark.asyncio
async def test_tool_metadata_includes_schema():
    """Test that tool metadata includes parameter schema."""
    mock = MockLLMClient([MockResponse(text="ok")])

    agent = Agent(
        name="SchemaAgent",
        instruction="Agent to test schemas",
        model_client=mock,
    )

    group = ActionGroup(name="SchemaGroup", description="Schema testing")

    @group.action(name="complex_action", description="Action with complex params")
    async def complex_action(
        name: str,
        age: int,
        active: bool = True,
        score: float = 0.0,
    ) -> dict:
        return {}

    agent.add_action_group(group)

    metadata = extract_agent_metadata(agent)
    tool = metadata.tools[0]

    schema = tool.parameters_schema
    assert schema["type"] == "object"

    props = schema["properties"]
    assert props["name"]["type"] == "string"
    assert props["age"]["type"] == "integer"
    assert props["active"]["type"] == "boolean"
    assert props["score"]["type"] == "number"

    # Check required vs optional
    required = schema["required"]
    assert "name" in required
    assert "age" in required
    assert "active" not in required  # Has default
    assert "score" not in required  # Has default
