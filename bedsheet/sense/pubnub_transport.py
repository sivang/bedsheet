"""PubNub implementation of SenseTransport.

Bridges PubNub's threaded callbacks into asyncio via an asyncio.Queue.
Requires: pip install pubnub>=7.0.0  (or: pip install bedsheet[sense])
"""
import asyncio
import logging
from typing import Any, AsyncIterator

from bedsheet.sense.protocol import AgentPresence, SenseTransport
from bedsheet.sense.serialization import deserialize, serialize
from bedsheet.sense.signals import Signal

try:
    from pubnub.callbacks import SubscribeCallback
    from pubnub.enums import PNReconnectionPolicy, PNStatusCategory
    from pubnub.models.consumer.common import PNStatus
    from pubnub.models.consumer.pubsub import PNMessageResult, PNPresenceEventResult
    from pubnub.pnconfiguration import PNConfiguration
    from pubnub.pubnub_asyncio import PubNubAsyncio
except ImportError as e:
    raise ImportError(
        "PubNub transport requires the 'pubnub' package. "
        "Install it with: pip install bedsheet[sense]"
    ) from e

logger = logging.getLogger(__name__)


class _SignalListener(SubscribeCallback):
    """PubNub callback that routes messages into an asyncio.Queue."""

    def __init__(self, queue: asyncio.Queue[Signal], loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self._queue = queue
        self._loop = loop

    def status(self, pubnub: Any, status: PNStatus) -> None:
        if status.category == PNStatusCategory.PNConnectedCategory:
            logger.info("PubNub connected")
        elif status.category == PNStatusCategory.PNReconnectedCategory:
            logger.info("PubNub reconnected")
        elif status.category == PNStatusCategory.PNDisconnectedCategory:
            logger.warning("PubNub disconnected")

    def message(self, pubnub: Any, message: PNMessageResult) -> None:
        try:
            signal = deserialize(message.message, source_channel=message.channel)
            self._loop.call_soon_threadsafe(self._queue.put_nowait, signal)
        except Exception:
            logger.exception("Failed to deserialize PubNub message")

    def presence(self, pubnub: Any, presence: PNPresenceEventResult) -> None:
        if presence.event in ("join", "leave", "timeout"):
            logger.debug(
                "Presence %s: %s on %s", presence.event, presence.uuid, presence.channel
            )


class PubNubTransport:
    """SenseTransport backed by PubNub.

    Usage:
        transport = PubNubTransport(
            subscribe_key="sub-c-...",
            publish_key="pub-c-...",
        )
        await transport.connect("agent-1", "cloud-ops")
    """

    def __init__(
        self,
        subscribe_key: str,
        publish_key: str,
        secret_key: str | None = None,
    ) -> None:
        self._subscribe_key = subscribe_key
        self._publish_key = publish_key
        self._secret_key = secret_key
        self._pubnub: PubNubAsyncio | None = None
        self._queue: asyncio.Queue[Signal] = asyncio.Queue()
        self._agent_id: str = ""
        self._namespace: str = ""
        self._subscribed_channels: set[str] = set()

    def _full_channel(self, channel: str) -> str:
        """Expand short channel name to full namespaced channel."""
        if channel.startswith("bedsheet."):
            return channel
        return f"bedsheet.{self._namespace}.{channel}"

    async def connect(self, agent_id: str, namespace: str) -> None:
        self._agent_id = agent_id
        self._namespace = namespace

        config = PNConfiguration()
        config.subscribe_key = self._subscribe_key
        config.publish_key = self._publish_key
        if self._secret_key:
            config.secret_key = self._secret_key
        config.uuid = agent_id
        config.reconnect_policy = PNReconnectionPolicy.EXPONENTIAL

        self._pubnub = PubNubAsyncio(config)
        loop = asyncio.get_running_loop()
        listener = _SignalListener(self._queue, loop)
        self._pubnub.add_listener(listener)

    async def disconnect(self) -> None:
        if self._pubnub:
            if self._subscribed_channels:
                self._pubnub.unsubscribe().channels(
                    list(self._subscribed_channels)
                ).execute()
            self._pubnub.stop()
            self._pubnub = None
            self._subscribed_channels.clear()

    async def broadcast(self, channel: str, signal: Signal) -> None:
        if not self._pubnub:
            raise RuntimeError("Not connected. Call connect() first.")
        full_ch = self._full_channel(channel)
        data = serialize(signal)
        await self._pubnub.publish().channel(full_ch).message(data).future()

    async def subscribe(self, channel: str) -> None:
        if not self._pubnub:
            raise RuntimeError("Not connected. Call connect() first.")
        full_ch = self._full_channel(channel)
        self._pubnub.subscribe().channels([full_ch]).with_presence().execute()
        self._subscribed_channels.add(full_ch)

    async def unsubscribe(self, channel: str) -> None:
        if not self._pubnub:
            return
        full_ch = self._full_channel(channel)
        self._pubnub.unsubscribe().channels([full_ch]).execute()
        self._subscribed_channels.discard(full_ch)

    async def signals(self) -> AsyncIterator[Signal]:
        while True:
            signal = await self._queue.get()
            yield signal

    async def get_online_agents(self, channel: str) -> list[AgentPresence]:
        if not self._pubnub:
            raise RuntimeError("Not connected. Call connect() first.")
        full_ch = self._full_channel(channel)
        result = await self._pubnub.here_now().channels([full_ch]).include_uuids(True).future()

        agents: list[AgentPresence] = []
        for ch_data in result.result.channels:
            for occupant in ch_data.occupants:
                agents.append(
                    AgentPresence(
                        agent_id=occupant.uuid,
                        agent_name=occupant.uuid,
                        namespace=self._namespace,
                    )
                )
        return agents
