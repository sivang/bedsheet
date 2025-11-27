import pytest
from bedsheet.supervisor import Supervisor
from bedsheet.agent import Agent
from bedsheet.testing import MockLLMClient, MockResponse


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
