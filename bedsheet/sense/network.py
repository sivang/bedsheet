"""SenseNetwork - high-level API for managing a network of sense-aware agents."""

import logging
from typing import Any, Callable

from bedsheet.sense.mixin import SenseMixin
from bedsheet.sense.protocol import SenseTransport

logger = logging.getLogger(__name__)


class SenseNetwork:
    """Convenience wrapper for managing multiple agents on a sense network.

    Each agent gets its own transport instance. Provide either:
    - A transport_factory callable that creates a new transport per agent, or
    - A transport instance that has a create_peer() method (like MockSenseTransport).

    Usage:
        # With MockSenseTransport (testing)
        network = SenseNetwork(namespace="cloud-ops", transport=MockSenseTransport())

        # With PubNubTransport (production)
        network = SenseNetwork(
            namespace="cloud-ops",
            transport_factory=lambda: PubNubTransport(sub_key, pub_key),
        )

        await network.add(cpu_agent, channels=["alerts", "tasks"])
        await network.add(commander, channels=["alerts", "tasks"])
        await network.stop()
    """

    def __init__(
        self,
        namespace: str,
        transport: SenseTransport | None = None,
        transport_factory: Callable[[], SenseTransport] | None = None,
    ) -> None:
        self.namespace = namespace
        self._base_transport = transport
        self._transport_factory = transport_factory
        self._agents: list[SenseMixin] = []

        if transport is None and transport_factory is None:
            raise ValueError("Provide either transport or transport_factory")

    def _make_transport(self) -> SenseTransport:
        """Create a transport for a new agent."""
        if self._transport_factory:
            return self._transport_factory()
        # If the transport supports create_peer(), use it
        if hasattr(self._base_transport, "create_peer"):
            return self._base_transport.create_peer()  # type: ignore[union-attr]
        # Fallback: reuse the same transport (works for single-agent or separate processes)
        return self._base_transport  # type: ignore[return-value]

    async def add(
        self,
        agent: Any,
        channels: list[str] | None = None,
    ) -> None:
        """Add an agent to the network and connect it.

        The agent must be a SenseMixin (or subclass thereof).
        """
        if not isinstance(agent, SenseMixin):
            raise TypeError(
                f"Agent '{getattr(agent, 'name', agent)}' must inherit from SenseMixin. "
                "Use: class MyAgent(SenseMixin, Agent)"
            )

        transport = self._make_transport()
        await agent.join_network(transport, self.namespace, channels)
        self._agents.append(agent)
        logger.info("Added '%s' to network '%s'", agent.name, self.namespace)  # type: ignore[attr-defined]

    async def stop(self) -> None:
        """Disconnect all agents from the network."""
        for agent in self._agents:
            try:
                await agent.leave_network()
            except Exception:
                logger.exception("Error disconnecting '%s'", agent.name)  # type: ignore[attr-defined]
        self._agents.clear()
        logger.info("Network '%s' stopped", self.namespace)

    @property
    def agents(self) -> list[SenseMixin]:
        """Get all agents currently on the network."""
        return list(self._agents)
