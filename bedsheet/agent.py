"""Agent class - the main orchestrator."""
from bedsheet.action_group import ActionGroup, Action
from bedsheet.llm.base import LLMClient, ToolDefinition
from bedsheet.memory.base import Memory
from bedsheet.memory.in_memory import InMemory


class Agent:
    """An agent that orchestrates LLM calls and tool execution."""

    DEFAULT_ORCHESTRATION_TEMPLATE = """$instruction$

You have access to tools to help answer the user's question.
Current date: $current_datetime$
"""

    def __init__(
        self,
        name: str,
        instruction: str,
        model_client: LLMClient,
        orchestration_template: str | None = None,
        memory: Memory | None = None,
        max_iterations: int = 10,
    ) -> None:
        self.name = name
        self.instruction = instruction
        self.orchestration_template = orchestration_template or self.DEFAULT_ORCHESTRATION_TEMPLATE
        self.model_client = model_client
        self.memory = memory if memory is not None else InMemory()
        self.max_iterations = max_iterations
        self._action_groups: list[ActionGroup] = []

    def _render_system_prompt(self) -> str:
        """Render the orchestration template with variable substitution."""
        from datetime import datetime, timezone

        tools_summary = ", ".join(
            action.name for group in self._action_groups for action in group.get_actions()
        ) or "none"

        return (
            self.orchestration_template
            .replace("$instruction$", self.instruction)
            .replace("$agent_name$", self.name)
            .replace("$current_datetime$", datetime.now(timezone.utc).isoformat())
            .replace("$tools_summary$", tools_summary)
        )

    def add_action_group(self, group: ActionGroup) -> None:
        """Add an action group to the agent."""
        self._action_groups.append(group)

    def get_action(self, name: str) -> Action | None:
        """Get an action by name from all action groups."""
        for group in self._action_groups:
            action = group.get_action(name)
            if action is not None:
                return action
        return None

    def get_tool_definitions(self) -> list[ToolDefinition]:
        """Get all tool definitions from all action groups."""
        tools: list[ToolDefinition] = []
        for group in self._action_groups:
            tools.extend(group.get_tool_definitions())
        return tools
