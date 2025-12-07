"""Agent introspection module for extracting metadata from agents."""
from dataclasses import dataclass
from typing import Any

from bedsheet.agent import Agent
from bedsheet.supervisor import Supervisor


@dataclass
class ToolMetadata:
    """Metadata for a single tool/action."""
    name: str
    description: str
    parameters_schema: dict[str, Any]


@dataclass
class AgentMetadata:
    """Metadata extracted from an agent."""
    name: str
    instruction: str
    tools: list[ToolMetadata]
    collaborators: list["AgentMetadata"]
    is_supervisor: bool


def extract_agent_metadata(agent: Agent) -> AgentMetadata:
    """Extract metadata from an agent.

    Args:
        agent: The agent to extract metadata from (Agent or Supervisor).

    Returns:
        AgentMetadata containing the agent's name, instruction, tools,
        and collaborators (if it's a Supervisor).
    """
    # Extract basic info
    name = agent.name
    instruction = agent.instruction
    is_supervisor = isinstance(agent, Supervisor)

    # Extract tool definitions from all action groups
    tools: list[ToolMetadata] = []
    for action_group in agent._action_groups:
        for action in action_group.get_actions():
            tool = ToolMetadata(
                name=action.name,
                description=action.description,
                parameters_schema=action.input_schema,
            )
            tools.append(tool)

    # Extract collaborators if this is a Supervisor
    collaborators: list[AgentMetadata] = []
    if is_supervisor:
        # Supervisor stores collaborators in a dict {name: agent}
        supervisor = agent  # type: Supervisor
        for collaborator_agent in supervisor.collaborators.values():
            # Recursively extract metadata from each collaborator
            collaborator_metadata = extract_agent_metadata(collaborator_agent)
            collaborators.append(collaborator_metadata)

    return AgentMetadata(
        name=name,
        instruction=instruction,
        tools=tools,
        collaborators=collaborators,
        is_supervisor=is_supervisor,
    )
