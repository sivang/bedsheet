"""Supervisor agent for multi-agent collaboration."""
from typing import Literal

from bedsheet.agent import Agent
from bedsheet.llm.base import LLMClient
from bedsheet.memory.base import Memory


class Supervisor(Agent):
    """An agent that can delegate tasks to collaborator agents."""

    def __init__(
        self,
        name: str,
        instruction: str,
        model_client: LLMClient,
        collaborators: list[Agent],
        collaboration_mode: Literal["supervisor", "router"] = "supervisor",
        orchestration_template: str | None = None,
        memory: Memory | None = None,
        max_iterations: int = 10,
    ) -> None:
        super().__init__(
            name=name,
            instruction=instruction,
            model_client=model_client,
            orchestration_template=orchestration_template,
            memory=memory,
            max_iterations=max_iterations,
        )
        self.collaborators = {agent.name: agent for agent in collaborators}
        self.collaboration_mode = collaboration_mode
