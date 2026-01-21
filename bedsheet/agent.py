"""Agent class - the main orchestrator."""
import asyncio
import json
from typing import AsyncIterator

from bedsheet.action_group import ActionGroup, Action
from bedsheet.events import Event, CompletionEvent, ErrorEvent, ToolCallEvent, ToolResultEvent, TextTokenEvent
from bedsheet.llm.base import LLMClient, ToolDefinition
from bedsheet.memory.base import Memory, Message
from bedsheet.memory.in_memory import InMemory


class Agent:
    """An agent that orchestrates LLM calls and tool execution.

    The model_client parameter is optional to support target-agnostic agent definitions.
    When model_client is None, the agent can be introspected for metadata (tools,
    instruction, etc.) but cannot be invoked. The bedsheet CLI will inject the
    appropriate client based on the deployment target:
      - local: AnthropicClient (Claude)
      - gcp: Translated to ADK LlmAgent (Gemini via Vertex AI)
      - aws: Bedrock client
    """

    DEFAULT_ORCHESTRATION_TEMPLATE = """$instruction$

You have access to tools to help answer the user's question.
Current date: $current_datetime$
"""

    def __init__(
        self,
        name: str,
        instruction: str,
        model_client: LLMClient | None = None,
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
        stream: bool = False,
    ) -> AsyncIterator[Event]:
        """Invoke the agent with user input, yielding events as execution progresses.

        Raises:
            RuntimeError: If model_client is None. Use bedsheet CLI to inject the
                         appropriate client for your deployment target.
        """
        # Check that model_client is configured
        if self.model_client is None:
            raise RuntimeError(
                f"Agent '{self.name}' has no model_client configured. "
                "Either pass a model_client when creating the agent, or use "
                "'bedsheet deploy --target <target>' to inject the appropriate client."
            )

        # 1. Load history from memory
        messages = await self.memory.get_messages(session_id)

        # 2. Append user message
        user_message = Message(role="user", content=input_text)
        messages.append(user_message)
        new_messages = [user_message]

        # 3. Get tool definitions
        tools = self.get_tool_definitions() or None

        # 4. Main loop
        for iteration in range(self.max_iterations):
            # Call LLM (with streaming if requested and supported)
            if stream and hasattr(self.model_client, 'chat_stream'):
                response = None
                async for chunk in self.model_client.chat_stream(
                    messages=messages,
                    system=self._render_system_prompt(),
                    tools=tools,
                ):
                    if isinstance(chunk, str):
                        yield TextTokenEvent(token=chunk)
                    else:
                        response = chunk  # LLMResponse
            else:
                response = await self.model_client.chat(
                    messages=messages,
                    system=self._render_system_prompt(),
                    tools=tools,
                )

            # Ensure we have a response (streaming should always end with LLMResponse)
            if response is None:
                yield ErrorEvent(error="No response from LLM", recoverable=False)
                return

            # If text response with no tool calls, we're done
            if response.text and not response.tool_calls:
                assistant_message = Message(role="assistant", content=response.text)
                messages.append(assistant_message)
                new_messages.append(assistant_message)

                # Save all new messages to memory
                await self.memory.add_messages(session_id, new_messages)

                yield CompletionEvent(response=response.text)
                return

            # Handle tool calls
            if response.tool_calls:
                # Record assistant message with tool calls
                assistant_message = Message(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        {"id": tc.id, "name": tc.name, "input": tc.input}
                        for tc in response.tool_calls
                    ]
                )
                messages.append(assistant_message)
                new_messages.append(assistant_message)

                # Yield all tool call events first
                for tool_call in response.tool_calls:
                    yield ToolCallEvent(
                        tool_name=tool_call.name,
                        tool_input=tool_call.input,
                        call_id=tool_call.id,
                    )

                # Execute all tool calls in parallel
                async def execute_tool(tool_call):
                    action = self.get_action(tool_call.name)
                    if action is None:
                        return tool_call.id, None, f"Unknown action: {tool_call.name}"
                    try:
                        result = await action.fn(**tool_call.input)
                        return tool_call.id, result, None
                    except Exception as e:
                        return tool_call.id, None, str(e)

                results = await asyncio.gather(*[
                    execute_tool(tc) for tc in response.tool_calls
                ])

                # Yield results and build messages
                for call_id, result, error in results:
                    yield ToolResultEvent(
                        call_id=call_id,
                        result=result,
                        error=error,
                    )

                    if error:
                        content = f"Error: {error}"
                    else:
                        content = json.dumps(result) if not isinstance(result, str) else result

                    tool_result_message = Message(
                        role="tool_result",
                        content=content,
                        tool_call_id=call_id,
                    )
                    messages.append(tool_result_message)
                    new_messages.append(tool_result_message)

        # Max iterations reached
        yield ErrorEvent(
            error=f"Max iterations ({self.max_iterations}) exceeded",
            recoverable=False,
        )
