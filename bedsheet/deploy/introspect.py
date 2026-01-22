"""Agent introspection module for extracting metadata from agents."""
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from bedsheet.agent import Agent
from bedsheet.supervisor import Supervisor
from bedsheet.deploy.source_extractor import SourceExtractor, ParameterInfo


@dataclass
class ToolMetadata:
    """Metadata for a single tool/action."""
    # Original fields (backward compatible)
    name: str
    description: str
    parameters_schema: dict[str, Any]
    # New fields for source extraction
    parameters: list[ParameterInfo] = field(default_factory=list)
    source_code: str = ""
    is_async: bool = False
    imports: list[str] = field(default_factory=list)
    return_type: str = "Any"


@dataclass
class AgentMetadata:
    """Metadata extracted from an agent."""
    name: str
    instruction: str
    tools: list[ToolMetadata]
    collaborators: list["AgentMetadata"]
    is_supervisor: bool


def extract_agent_metadata(agent: Agent, target: Literal["local", "gcp", "aws"] = "local") -> AgentMetadata:
    """Extract metadata from an agent.

    Args:
        agent: The agent to extract metadata from (Agent or Supervisor).
        target: Deployment target for code transformation ("local", "gcp", "aws").
                Defaults to "local".

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
            # Extract source code and metadata using SourceExtractor
            source_code = ""
            parameters: list[ParameterInfo] = []
            is_async = False
            imports: list[str] = []
            return_type = "Any"

            try:
                extractor = SourceExtractor(action.fn)
                source_info = extractor.extract()

                source_code = source_info.source_code
                parameters = source_info.parameters
                is_async = source_info.is_async
                imports = source_info.imports
                return_type = source_info.return_type

                # Transform source code for target if CodeTransformer is available
                try:
                    from bedsheet.deploy.code_transformer import CodeTransformer
                    transformer = CodeTransformer(target=target)
                    transformed_info = transformer.transform(source_info)
                    source_code = transformed_info.source_code
                    is_async = transformed_info.is_async
                except ImportError:
                    # CodeTransformer not available yet, use raw source
                    pass

            except (OSError, ValueError):
                # Source extraction failed (e.g., built-in function or dynamic code)
                pass

            tool = ToolMetadata(
                name=action.name,
                description=action.description,
                parameters_schema=action.input_schema,
                parameters=parameters,
                source_code=source_code,
                is_async=is_async,
                imports=imports,
                return_type=return_type,
            )
            tools.append(tool)

    # Extract collaborators if this is a Supervisor
    collaborators: list[AgentMetadata] = []
    if is_supervisor:
        # Supervisor stores collaborators in a dict {name: agent}
        supervisor = cast(Supervisor, agent)
        for collaborator_agent in supervisor.collaborators.values():
            # Recursively extract metadata from each collaborator
            collaborator_metadata = extract_agent_metadata(collaborator_agent, target=target)
            collaborators.append(collaborator_metadata)

    return AgentMetadata(
        name=name,
        instruction=instruction,
        tools=tools,
        collaborators=collaborators,
        is_supervisor=is_supervisor,
    )
