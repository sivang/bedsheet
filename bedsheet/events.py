"""Event types for streaming agent execution."""
from dataclasses import dataclass, field
from typing import Any, Literal, Union


@dataclass
class ThinkingEvent:
    """Emitted when the LLM is thinking (extended thinking mode)."""
    content: str
    type: Literal["thinking"] = field(default="thinking", init=False)


@dataclass
class ToolCallEvent:
    """Emitted when the LLM requests a tool call."""
    tool_name: str
    tool_input: dict[str, Any]
    call_id: str
    type: Literal["tool_call"] = field(default="tool_call", init=False)


@dataclass
class ToolResultEvent:
    """Emitted after a tool call completes."""
    call_id: str
    result: Any
    error: str | None = None
    type: Literal["tool_result"] = field(default="tool_result", init=False)


@dataclass
class CompletionEvent:
    """Emitted when the agent produces a final response."""
    response: str
    type: Literal["completion"] = field(default="completion", init=False)


@dataclass
class ErrorEvent:
    """Emitted when an error occurs during execution."""
    error: str
    recoverable: bool = False
    type: Literal["error"] = field(default="error", init=False)


@dataclass
class TextTokenEvent:
    """Emitted when a text token arrives from the LLM (streaming mode)."""
    token: str
    type: Literal["text_token"] = field(default="text_token", init=False)


@dataclass
class RoutingEvent:
    """Router mode: supervisor picked an agent to route to."""
    agent_name: str
    task: str
    type: Literal["routing"] = field(default="routing", init=False)


@dataclass
class DelegationEvent:
    """Supervisor mode: supervisor is delegating task(s)."""
    delegations: list[dict]
    type: Literal["delegation"] = field(default="delegation", init=False)


@dataclass
class CollaboratorStartEvent:
    """A collaborator agent is starting work."""
    agent_name: str
    task: str
    type: Literal["collaborator_start"] = field(default="collaborator_start", init=False)


@dataclass
class CollaboratorEvent:
    """Wraps any event from a collaborator for visibility."""
    agent_name: str
    inner_event: "Event"
    type: Literal["collaborator"] = field(default="collaborator", init=False)


@dataclass
class CollaboratorCompleteEvent:
    """A collaborator agent has finished."""
    agent_name: str
    response: str
    type: Literal["collaborator_complete"] = field(default="collaborator_complete", init=False)


@dataclass
class SignalReceivedEvent:
    """A signal arrived from the sense network."""
    sender: str
    kind: str
    channel: str
    payload: dict[str, Any]
    type: Literal["signal_received"] = field(default="signal_received", init=False)


@dataclass
class AgentConnectedEvent:
    """A remote agent came online on the sense network."""
    agent_id: str
    agent_name: str
    namespace: str
    type: Literal["agent_connected"] = field(default="agent_connected", init=False)


@dataclass
class AgentDisconnectedEvent:
    """A remote agent went offline on the sense network."""
    agent_id: str
    agent_name: str
    namespace: str
    type: Literal["agent_disconnected"] = field(default="agent_disconnected", init=False)


@dataclass
class RemoteDelegationEvent:
    """A task was sent to a remote agent via the sense network."""
    agent_name: str
    task: str
    correlation_id: str
    type: Literal["remote_delegation"] = field(default="remote_delegation", init=False)


@dataclass
class RemoteResultEvent:
    """A result was received from a remote agent via the sense network."""
    agent_name: str
    result: str
    correlation_id: str
    type: Literal["remote_result"] = field(default="remote_result", init=False)


Event = Union[
    ThinkingEvent,
    TextTokenEvent,
    ToolCallEvent,
    ToolResultEvent,
    CompletionEvent,
    ErrorEvent,
    RoutingEvent,
    DelegationEvent,
    CollaboratorStartEvent,
    CollaboratorEvent,
    CollaboratorCompleteEvent,
    SignalReceivedEvent,
    AgentConnectedEvent,
    AgentDisconnectedEvent,
    RemoteDelegationEvent,
    RemoteResultEvent,
]
