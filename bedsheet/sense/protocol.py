"""SenseTransport protocol for distributed agent communication."""

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol, runtime_checkable

from bedsheet.sense.signals import Signal


@dataclass
class AgentPresence:
    """Represents a remote agent's presence on the network."""

    agent_id: str
    agent_name: str
    namespace: str
    capabilities: list[str] = field(default_factory=list)
    status: str = "online"
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class SenseTransport(Protocol):
    """Protocol for sense network transports.

    Follows the same structural subtyping pattern as LLMClient and Memory.
    Any class implementing these methods satisfies the protocol.
    """

    async def connect(self, agent_id: str, namespace: str) -> None:
        """Connect to the network with a given agent identity."""
        ...

    async def disconnect(self) -> None:
        """Disconnect from the network."""
        ...

    async def broadcast(self, channel: str, signal: Signal) -> None:
        """Publish a signal to a channel."""
        ...

    async def subscribe(self, channel: str) -> None:
        """Subscribe to a channel to receive signals."""
        ...

    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel."""
        ...

    def signals(self) -> AsyncIterator[Signal]:
        """Async iterator of incoming signals from subscribed channels."""
        ...

    async def get_online_agents(self, channel: str) -> list[AgentPresence]:
        """Get agents currently present on a channel."""
        ...
