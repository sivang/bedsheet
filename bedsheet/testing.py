"""Testing utilities for Bedsheet Agents."""
import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from bedsheet.llm.base import LLMResponse, OutputSchema, ToolCall, ToolDefinition
from bedsheet.memory.base import Message
from bedsheet.sense.protocol import AgentPresence
from bedsheet.sense.signals import Signal


@dataclass
class MockResponse:
    """A mock response for testing."""
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    thinking: str | None = None
    parsed_output: Any = None  # For structured output testing


class MockLLMClient:
    """Mock LLM client for testing agent logic without API calls."""

    def __init__(self, responses: list[MockResponse]) -> None:
        self._responses = iter(responses)

    def _get_next_response(self) -> MockResponse:
        """Get the next mock response from the queue."""
        return next(self._responses)

    async def chat(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
        output_schema: OutputSchema | None = None,
    ) -> LLMResponse:
        """Return the next mock response."""
        response = self._get_next_response()

        stop_reason = "tool_use" if response.tool_calls else "end_turn"

        return LLMResponse(
            text=response.text,
            tool_calls=response.tool_calls,
            stop_reason=stop_reason,
            thinking=response.thinking,
            parsed_output=response.parsed_output,
        )

    async def chat_stream(
        self,
        messages: list,
        system: str,
        tools: list | None = None,
        output_schema: OutputSchema | None = None,
    ) -> AsyncIterator[str | LLMResponse]:
        """Stream mock response - yields tokens then final LLMResponse."""
        response = self._get_next_response()

        # Stream text tokens (word by word for readability)
        if response.text:
            words = response.text.split(' ')
            for i, word in enumerate(words):
                if i > 0:
                    yield ' '
                yield word

        # Yield final response for tool calls
        yield LLMResponse(
            text=response.text,
            tool_calls=response.tool_calls or [],
            stop_reason="end_turn",
            parsed_output=response.parsed_output,
        )


class _MockSenseHub:
    """Shared in-memory signal routing hub.

    Multiple MockSenseTransport instances connect to the same hub.
    The hub manages queues and subscriptions for all agents.
    """

    def __init__(self) -> None:
        self.queues: dict[str, asyncio.Queue[Signal]] = {}
        self.subscriptions: dict[str, set[str]] = {}  # channel -> set of agent_ids

    async def broadcast(self, channel: str, signal: Signal) -> None:
        subscribers = self.subscriptions.get(channel, set())
        for agent_id in subscribers:
            queue = self.queues.get(agent_id)
            if queue:
                await queue.put(signal)


class MockSenseTransport:
    """In-memory SenseTransport for testing.

    Each agent gets its own MockSenseTransport instance that shares
    a common _MockSenseHub for signal routing.

    Usage:
        hub = _MockSenseHub()
        transport1 = MockSenseTransport(hub)
        transport2 = MockSenseTransport(hub)
        # Or use the convenience constructor:
        transport = MockSenseTransport()  # creates its own hub
    """

    def __init__(self, hub: _MockSenseHub | None = None) -> None:
        self._hub = hub or _MockSenseHub()
        self._agent_id: str = ""
        self._namespace: str = ""
        self._connected: bool = False

    @property
    def hub(self) -> _MockSenseHub:
        """Access the shared hub (useful for creating sibling transports)."""
        return self._hub

    def create_peer(self) -> "MockSenseTransport":
        """Create another transport sharing the same hub."""
        return MockSenseTransport(self._hub)

    async def connect(self, agent_id: str, namespace: str) -> None:
        self._agent_id = agent_id
        self._namespace = namespace
        self._hub.queues[agent_id] = asyncio.Queue()
        self._connected = True

    async def disconnect(self) -> None:
        for channel, subscribers in self._hub.subscriptions.items():
            subscribers.discard(self._agent_id)
        self._hub.queues.pop(self._agent_id, None)
        self._connected = False

    async def broadcast(self, channel: str, signal: Signal) -> None:
        full_ch = self._full_channel(channel)
        await self._hub.broadcast(full_ch, signal)

    async def subscribe(self, channel: str) -> None:
        full_ch = self._full_channel(channel)
        if full_ch not in self._hub.subscriptions:
            self._hub.subscriptions[full_ch] = set()
        self._hub.subscriptions[full_ch].add(self._agent_id)

    async def unsubscribe(self, channel: str) -> None:
        full_ch = self._full_channel(channel)
        if full_ch in self._hub.subscriptions:
            self._hub.subscriptions[full_ch].discard(self._agent_id)

    async def signals(self) -> AsyncIterator[Signal]:
        queue = self._hub.queues.get(self._agent_id)
        if not queue:
            return
        while True:
            signal = await queue.get()
            yield signal

    async def get_online_agents(self, channel: str) -> list[AgentPresence]:
        full_ch = self._full_channel(channel)
        subscribers = self._hub.subscriptions.get(full_ch, set())
        return [
            AgentPresence(
                agent_id=aid,
                agent_name=aid,
                namespace=self._namespace,
            )
            for aid in subscribers
        ]

    def _full_channel(self, channel: str) -> str:
        if channel.startswith("bedsheet."):
            return channel
        return f"bedsheet.{self._namespace}.{channel}"
