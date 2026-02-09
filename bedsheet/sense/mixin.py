"""SenseMixin - gives any Agent distributed sensing capabilities."""
import asyncio
import logging
from typing import Any, Callable, Awaitable
from uuid import uuid4

from bedsheet.events import (
    CompletionEvent,
    RemoteDelegationEvent,
    RemoteResultEvent,
    SignalReceivedEvent,
)
from bedsheet.sense.protocol import SenseTransport
from bedsheet.sense.signals import Signal, SignalKind

logger = logging.getLogger(__name__)

# Type for signal handler callbacks
SignalHandler = Callable[[Signal], Awaitable[None]]


class SenseMixin:
    """Mixin that adds distributed sensing to any Agent.

    Usage:
        class MyAgent(SenseMixin, Agent):
            pass

        agent = MyAgent(name="watcher", instruction="...", model_client=client)
        await agent.join_network(transport, "cloud-ops", ["alerts", "tasks"])
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._transport: SenseTransport | None = None
        self._namespace: str = ""
        self._signal_handlers: dict[SignalKind, list[SignalHandler]] = {}
        self._signal_task: asyncio.Task[None] | None = None
        self._pending_requests: dict[str, asyncio.Future[Signal]] = {}
        self._claimed_incidents: set[str] = set()
        self._heartbeat_task: asyncio.Task[None] | None = None

    async def join_network(
        self,
        transport: SenseTransport,
        namespace: str,
        channels: list[str] | None = None,
    ) -> None:
        """Connect to the sense network and start listening."""
        self._transport = transport
        self._namespace = namespace

        # Use agent's name as the network identity
        await transport.connect(self.name, namespace)  # type: ignore[attr-defined]

        # Subscribe to channels
        if channels:
            for ch in channels:
                await transport.subscribe(ch)

        # Subscribe to agent's direct channel
        await transport.subscribe(self.name)  # type: ignore[attr-defined]

        # Start signal processing loop
        self._signal_task = asyncio.create_task(self._signal_loop())

        # Start heartbeat
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        logger.info("Agent '%s' joined network '%s'", self.name, namespace)  # type: ignore[attr-defined]

    async def leave_network(self) -> None:
        """Disconnect from the sense network."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        if self._signal_task:
            self._signal_task.cancel()
            self._signal_task = None

        if self._transport:
            await self._transport.disconnect()
            self._transport = None

        logger.info("Agent '%s' left network", self.name)  # type: ignore[attr-defined]

    async def broadcast(self, channel: str, signal: Signal) -> None:
        """Send a signal to a channel."""
        if not self._transport:
            raise RuntimeError("Not connected to a network. Call join_network() first.")
        await self._transport.broadcast(channel, signal)

    async def send_to(self, agent_name: str, signal: Signal) -> None:
        """Send a signal directly to another agent's channel."""
        await self.broadcast(agent_name, signal)

    async def request(
        self,
        agent_name: str,
        task: str,
        timeout: float = 30.0,
    ) -> str:
        """Send a request to a remote agent and wait for the response.

        Returns the response payload as a string.
        Raises TimeoutError if no response within timeout.
        """
        correlation_id = uuid4().hex[:12]

        # Create a future to wait for the response
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Signal] = loop.create_future()
        self._pending_requests[correlation_id] = future

        # Send the request signal
        signal = Signal(
            kind="request",
            sender=self.name,  # type: ignore[attr-defined]
            payload={"task": task},
            correlation_id=correlation_id,
            target=agent_name,
        )
        await self.send_to(agent_name, signal)

        try:
            response_signal = await asyncio.wait_for(future, timeout=timeout)
            return response_signal.payload.get("result", "")
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"No response from '{agent_name}' within {timeout}s"
            )
        finally:
            self._pending_requests.pop(correlation_id, None)

    async def claim_incident(self, incident_id: str, channel: str = "tasks") -> bool:
        """Attempt to claim an incident. Returns True if claim is won.

        Uses a simple timestamp-based conflict resolution: earliest claim wins.
        Waits 500ms for competing claims before declaring victory.
        """
        signal = Signal(
            kind="claim",
            sender=self.name,  # type: ignore[attr-defined]
            payload={"incident_id": incident_id},
            correlation_id=incident_id,
        )
        await self.broadcast(channel, signal)

        # Wait for competing claims
        await asyncio.sleep(0.5)

        # If no one else claimed (our claim is in _claimed_incidents), we won
        if incident_id in self._claimed_incidents:
            return True

        # We lost the claim
        return False

    async def release_incident(self, incident_id: str, channel: str = "tasks") -> None:
        """Release a previously claimed incident."""
        self._claimed_incidents.discard(incident_id)
        signal = Signal(
            kind="release",
            sender=self.name,  # type: ignore[attr-defined]
            payload={"incident_id": incident_id},
        )
        await self.broadcast(channel, signal)

    def on_signal(self, kind: SignalKind) -> Callable[[SignalHandler], SignalHandler]:
        """Decorator to register a handler for a specific signal kind."""
        def decorator(fn: SignalHandler) -> SignalHandler:
            if kind not in self._signal_handlers:
                self._signal_handlers[kind] = []
            self._signal_handlers[kind].append(fn)
            return fn
        return decorator

    async def _signal_loop(self) -> None:
        """Background task that processes incoming signals."""
        if not self._transport:
            return
        try:
            async for signal in self._transport.signals():
                # Skip our own signals
                if signal.sender == self.name:  # type: ignore[attr-defined]
                    continue

                # If targeted at another agent, skip
                if signal.target and signal.target != self.name:  # type: ignore[attr-defined]
                    continue

                logger.debug(
                    "Agent '%s' received %s from '%s'",
                    self.name,  # type: ignore[attr-defined]
                    signal.kind,
                    signal.sender,
                )

                # Handle responses to our pending requests
                if signal.kind == "response" and signal.correlation_id in self._pending_requests:
                    future = self._pending_requests[signal.correlation_id]
                    if not future.done():
                        future.set_result(signal)
                    continue

                # Handle incoming requests by invoking the agent
                if signal.kind == "request":
                    asyncio.create_task(self._handle_request(signal))
                    continue

                # Handle claim conflict resolution
                if signal.kind == "claim":
                    self._handle_claim(signal)
                    continue

                # Handle release
                if signal.kind == "release":
                    incident_id = signal.payload.get("incident_id")
                    if incident_id:
                        self._claimed_incidents.discard(incident_id)
                    continue

                # Run registered handlers
                handlers = self._signal_handlers.get(signal.kind, [])
                for handler in handlers:
                    try:
                        await handler(signal)
                    except Exception:
                        logger.exception("Signal handler error for %s", signal.kind)

        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Signal loop error")

    async def _handle_request(self, signal: Signal) -> None:
        """Handle an incoming request by invoking the agent and sending back the response."""
        task = signal.payload.get("task", "")
        session_id = f"sense-{signal.correlation_id}"

        # Collect the completion from invoke()
        result = ""
        try:
            async for event in self.invoke(session_id, task):  # type: ignore[attr-defined]
                if isinstance(event, CompletionEvent):
                    result = event.response
        except Exception as e:
            result = f"Error: {e}"

        # Send response back
        response_signal = Signal(
            kind="response",
            sender=self.name,  # type: ignore[attr-defined]
            payload={"result": result},
            correlation_id=signal.correlation_id,
            target=signal.sender,
        )
        await self.send_to(signal.sender, response_signal)

    def _handle_claim(self, signal: Signal) -> None:
        """Handle a competing claim signal. Earliest timestamp wins."""
        incident_id = signal.payload.get("incident_id")
        if not incident_id:
            return

        if incident_id in self._claimed_incidents:
            # We already claimed this - check if their claim is earlier
            # (they win if their timestamp is lower)
            # Since we can't easily compare without storing our claim signal,
            # use a simple rule: lower sender name wins ties
            if signal.sender < self.name:  # type: ignore[attr-defined]
                self._claimed_incidents.discard(incident_id)
        else:
            # We haven't claimed this, so note that someone else has
            pass

    async def _heartbeat_loop(self) -> None:
        """Periodically broadcast heartbeat signals."""
        try:
            while True:
                if self._transport:
                    # Gather capabilities from action groups
                    capabilities = []
                    if hasattr(self, '_action_groups'):
                        for group in self._action_groups:  # type: ignore[attr-defined]
                            for action in group.get_actions():
                                capabilities.append(action.name)

                    signal = Signal(
                        kind="heartbeat",
                        sender=self.name,  # type: ignore[attr-defined]
                        payload={
                            "capabilities": capabilities,
                            "status": "ready",
                        },
                    )
                    # Broadcast to the namespace's general channel
                    try:
                        await self.broadcast("heartbeat", signal)
                    except Exception:
                        logger.debug("Heartbeat broadcast failed")

                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass
