"""Agent class - the main orchestrator."""
from typing import AsyncIterator

from bedsheet.action_group import ActionGroup, Action
from bedsheet.events import Event, CompletionEvent
from bedsheet.llm.base import LLMClient, ToolDefinition
from bedsheet.memory.base import Memory, Message
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

    async def invoke(
        self,
        session_id: str,
        input_text: str,
    ) -> AsyncIterator[Event]:
        """Invoke the agent with user input, yielding events as execution progresses."""
        # 1. Load history from memory
        messages = await self.memory.get_messages(session_id)

        # 2. Append user message
        user_message = Message(role="user", content=input_text)
        messages.append(user_message)

        # 3. Get tool definitions
        tools = self.get_tool_definitions() or None

        # 4. Call LLM
        response = await self.model_client.chat(
            messages=messages,
            system=self._render_system_prompt(),
            tools=tools,
        )

        # 5. If text response, yield completion
        if response.text and not response.tool_calls:
            # Save messages to memory
            assistant_message = Message(role="assistant", content=response.text)
            await self.memory.add_messages(session_id, [user_message, assistant_message])

            yield CompletionEvent(response=response.text)
