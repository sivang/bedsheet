"""Supervisor agent for multi-agent collaboration."""
import json
from typing import AsyncIterator, Literal

from bedsheet.agent import Agent
from bedsheet.action_group import ActionGroup
from bedsheet.events import (
    Event, CompletionEvent, ErrorEvent, ToolCallEvent, ToolResultEvent,
    CollaboratorStartEvent, CollaboratorEvent, CollaboratorCompleteEvent,
)
from bedsheet.llm.base import LLMClient
from bedsheet.memory.base import Memory, Message


class Supervisor(Agent):
    """An agent that can delegate tasks to collaborator agents."""

    SUPERVISOR_ORCHESTRATION_TEMPLATE = """$instruction$

You have access to tools and collaborator agents to help answer the user's question.
Current date: $current_datetime$

## Available Collaborators
$collaborators_summary$

Use the delegate tool to assign tasks to collaborators.
For simple requests, delegate to one agent.
For complex requests, you may delegate to multiple agents in parallel.
"""

    ROUTER_ORCHESTRATION_TEMPLATE = """$instruction$

Route the user's request to the most appropriate agent:
$collaborators_summary$

Use the delegate tool to route to exactly one agent.
If no agent is appropriate, respond directly.
"""

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
        # Choose default template based on mode
        if orchestration_template is None:
            if collaboration_mode == "router":
                orchestration_template = self.ROUTER_ORCHESTRATION_TEMPLATE
            else:
                orchestration_template = self.SUPERVISOR_ORCHESTRATION_TEMPLATE

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

        # Register built-in delegate action
        self._register_delegate_action()

    def _register_delegate_action(self) -> None:
        """Register the built-in delegate tool."""
        delegate_group = ActionGroup(
            name="Delegation",
            description="Tools for delegating to collaborator agents",
        )

        @delegate_group.action(
            name="delegate",
            description="Delegate a task to a collaborator agent",
        )
        async def delegate(agent_name: str, task: str) -> str:
            return await self._execute_delegation(agent_name, task)

        self.add_action_group(delegate_group)

    async def _execute_delegation(self, agent_name: str, task: str) -> str:
        """Execute a single delegation to a collaborator."""
        collaborator = self.collaborators.get(agent_name)
        if collaborator is None:
            return f"Unknown agent: {agent_name}. Available: {list(self.collaborators.keys())}"

        # For now, just return a placeholder
        return f"Delegated to {agent_name}"

    async def _execute_single_delegation(
        self,
        agent_name: str,
        task: str,
        session_id: str,
    ) -> AsyncIterator[Event]:
        """Execute delegation to a single collaborator, yielding events."""
        collaborator = self.collaborators.get(agent_name)
        if collaborator is None:
            # Return error as a fake completion for the tool result
            return

        yield CollaboratorStartEvent(agent_name=agent_name, task=task)

        result = ""
        async for event in collaborator.invoke(session_id=f"{session_id}:{agent_name}", input_text=task):
            yield CollaboratorEvent(agent_name=agent_name, inner_event=event)
            if isinstance(event, CompletionEvent):
                result = event.response
            elif isinstance(event, ErrorEvent):
                result = f"Error: {event.error}"

        yield CollaboratorCompleteEvent(agent_name=agent_name, response=result)

    async def invoke(
        self,
        session_id: str,
        input_text: str,
    ) -> AsyncIterator[Event]:
        """Invoke the supervisor, handling delegations specially."""
        messages = await self.memory.get_messages(session_id)

        user_message = Message(role="user", content=input_text)
        messages.append(user_message)
        new_messages = [user_message]

        tools = self.get_tool_definitions() or None

        for iteration in range(self.max_iterations):
            response = await self.model_client.chat(
                messages=messages,
                system=self._render_system_prompt(),
                tools=tools,
            )

            if response.text and not response.tool_calls:
                assistant_message = Message(role="assistant", content=response.text)
                messages.append(assistant_message)
                new_messages.append(assistant_message)

                await self.memory.add_messages(session_id, new_messages)

                yield CompletionEvent(response=response.text)
                return

            if response.tool_calls:
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

                for tool_call in response.tool_calls:
                    yield ToolCallEvent(
                        tool_name=tool_call.name,
                        tool_input=tool_call.input,
                        call_id=tool_call.id,
                    )

                # Process tool calls
                for tool_call in response.tool_calls:
                    if tool_call.name == "delegate":
                        # Handle delegation specially
                        agent_name = tool_call.input.get("agent_name")
                        task = tool_call.input.get("task")

                        if agent_name not in self.collaborators:
                            content = f"Unknown agent: {agent_name}. Available: {list(self.collaborators.keys())}"
                            error = content
                        else:
                            result = ""
                            async for event in self._execute_single_delegation(agent_name, task, session_id):
                                yield event
                                if isinstance(event, CollaboratorCompleteEvent):
                                    result = event.response

                            content = result
                            error = None

                        yield ToolResultEvent(
                            call_id=tool_call.id,
                            result=content if not error else None,
                            error=error,
                        )

                        tool_result_message = Message(
                            role="tool_result",
                            content=content,
                            tool_call_id=tool_call.id,
                        )
                        messages.append(tool_result_message)
                        new_messages.append(tool_result_message)
                    else:
                        # Handle regular tool calls
                        action = self.get_action(tool_call.name)
                        if action is None:
                            error = f"Unknown action: {tool_call.name}"
                            result = None
                        else:
                            try:
                                result = await action.fn(**tool_call.input)
                                error = None
                            except Exception as e:
                                result = None
                                error = str(e)

                        yield ToolResultEvent(
                            call_id=tool_call.id,
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
                            tool_call_id=tool_call.id,
                        )
                        messages.append(tool_result_message)
                        new_messages.append(tool_result_message)

        yield ErrorEvent(
            error=f"Max iterations ({self.max_iterations}) exceeded",
            recoverable=False,
        )

    def _render_collaborators_summary(self) -> str:
        """Render collaborator list for system prompt."""
        if not self.collaborators:
            return "No collaborators available."

        lines = []
        for name, agent in self.collaborators.items():
            lines.append(f"- {name}: {agent.instruction}")
        return "\n".join(lines)

    def _render_system_prompt(self) -> str:
        """Render the orchestration template with variable substitution."""
        # Get base rendering from parent
        prompt = super()._render_system_prompt()
        # Add collaborators summary
        prompt = prompt.replace("$collaborators_summary$", self._render_collaborators_summary())
        return prompt
