import pytest
from bedsheet.agent import Agent
from bedsheet.action_group import ActionGroup
from bedsheet.memory.in_memory import InMemory
from bedsheet.testing import MockLLMClient, MockResponse


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
