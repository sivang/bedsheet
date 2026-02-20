"""Tests for the Sense distributed communication module."""

import asyncio
import pytest

from bedsheet import Agent, SenseMixin, SenseNetwork
from bedsheet.events import (
    SignalReceivedEvent,
    AgentConnectedEvent,
    AgentDisconnectedEvent,
    RemoteDelegationEvent,
    RemoteResultEvent,
)
from bedsheet.sense.signals import Signal
from bedsheet.sense.serialization import serialize, deserialize, MAX_MESSAGE_BYTES
from bedsheet.sense.protocol import AgentPresence
from bedsheet.testing import (
    MockLLMClient,
    MockResponse,
    MockSenseTransport,
    _MockSenseHub,
)


# ---------- Signal dataclass tests ----------


class TestSignal:
    def test_signal_creation(self):
        signal = Signal(kind="alert", sender="agent-1")
        assert signal.kind == "alert"
        assert signal.sender == "agent-1"
        assert signal.payload == {}
        assert signal.target is None
        assert signal.timestamp > 0
        assert len(signal.correlation_id) == 12

    def test_signal_with_payload(self):
        signal = Signal(
            kind="request",
            sender="commander",
            payload={"task": "check cpu"},
            target="cpu-watcher",
        )
        assert signal.payload == {"task": "check cpu"}
        assert signal.target == "cpu-watcher"

    def test_signal_kinds(self):
        for kind in (
            "request",
            "response",
            "alert",
            "heartbeat",
            "claim",
            "release",
            "event",
        ):
            signal = Signal(kind=kind, sender="test")
            assert signal.kind == kind


# ---------- Serialization tests ----------


class TestSerialization:
    def test_serialize_minimal(self):
        signal = Signal(kind="alert", sender="agent-1")
        data = serialize(signal)
        assert data["k"] == "alert"
        assert data["s"] == "agent-1"
        assert "ts" in data
        # No payload -> no "p" key
        assert "p" not in data

    def test_serialize_with_payload(self):
        signal = Signal(
            kind="request",
            sender="commander",
            payload={"task": "check cpu", "priority": "high"},
            target="cpu-watcher",
        )
        data = serialize(signal)
        assert data["p"] == {"task": "check cpu", "priority": "high"}
        assert data["t"] == "cpu-watcher"
        assert data["c"] == signal.correlation_id

    def test_roundtrip(self):
        original = Signal(
            kind="response",
            sender="cpu-watcher",
            payload={"result": "CPU at 45%"},
            correlation_id="abc123",
            target="commander",
        )
        data = serialize(original)
        restored = deserialize(data, source_channel="bedsheet.ops.tasks")

        assert restored.kind == original.kind
        assert restored.sender == original.sender
        assert restored.payload == original.payload
        assert restored.correlation_id == original.correlation_id
        assert restored.target == original.target
        assert restored.source_channel == "bedsheet.ops.tasks"

    def test_truncation_on_large_payload(self):
        # Create a payload that exceeds the limit
        large_payload = {"data": "x" * (MAX_MESSAGE_BYTES + 1000)}
        signal = Signal(kind="event", sender="test", payload=large_payload)
        data = serialize(signal)

        # Payload should be truncated
        assert data["p"]["_truncated"] is True
        assert "summary" in data["p"]

    def test_deserialize_minimal(self):
        data = {"k": "heartbeat", "s": "agent-2", "ts": 1234567890.0}
        signal = deserialize(data)
        assert signal.kind == "heartbeat"
        assert signal.sender == "agent-2"
        assert signal.payload == {}
        assert signal.correlation_id == ""


# ---------- Protocol tests ----------


class TestProtocol:
    def test_mock_transport_satisfies_protocol(self):
        """MockSenseTransport should satisfy the SenseTransport protocol."""
        transport = MockSenseTransport()
        # Check that the protocol methods exist
        assert hasattr(transport, "connect")
        assert hasattr(transport, "disconnect")
        assert hasattr(transport, "broadcast")
        assert hasattr(transport, "subscribe")
        assert hasattr(transport, "unsubscribe")
        assert hasattr(transport, "signals")
        assert hasattr(transport, "get_online_agents")

    def test_agent_presence_creation(self):
        presence = AgentPresence(
            agent_id="agent-1",
            agent_name="CPU Watcher",
            namespace="cloud-ops",
            capabilities=["get_cpu_usage", "get_process_top"],
        )
        assert presence.agent_id == "agent-1"
        assert presence.capabilities == ["get_cpu_usage", "get_process_top"]
        assert presence.status == "online"


# ---------- MockSenseTransport tests ----------


class TestMockSenseTransport:
    async def test_connect_disconnect(self):
        transport = MockSenseTransport()
        await transport.connect("agent-1", "test-ns")
        assert transport._connected
        await transport.disconnect()
        assert not transport._connected

    async def test_subscribe_and_broadcast(self):
        hub = _MockSenseHub()
        transport1 = MockSenseTransport(hub)
        transport2 = MockSenseTransport(hub)

        # Agent 1 subscribes
        await transport1.connect("agent-1", "test-ns")
        await transport1.subscribe("alerts")

        # Agent 2 subscribes
        await transport2.connect("agent-2", "test-ns")
        await transport2.subscribe("alerts")

        # Agent 2 broadcasts
        signal = Signal(kind="alert", sender="agent-2", payload={"msg": "cpu high"})
        await transport2.broadcast("alerts", signal)

        # Agent 1 should receive it
        queue = hub.queues["agent-1"]
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received.kind == "alert"
        assert received.payload == {"msg": "cpu high"}

    async def test_get_online_agents(self):
        transport = MockSenseTransport()
        await transport.connect("agent-1", "test-ns")
        await transport.subscribe("alerts")

        agents = await transport.get_online_agents("alerts")
        assert len(agents) == 1
        assert agents[0].agent_id == "agent-1"

    async def test_create_peer(self):
        t1 = MockSenseTransport()
        t2 = t1.create_peer()
        assert t1.hub is t2.hub


# ---------- SenseMixin tests ----------


class SenseAgent(SenseMixin, Agent):
    """Agent with sensing capabilities for testing."""

    pass


class TestSenseMixin:
    def _make_agent(self, name: str, response_text: str = "Done") -> SenseAgent:
        """Create a sense agent with a mock LLM client."""
        client = MockLLMClient([MockResponse(text=response_text)])
        agent = SenseAgent(
            name=name,
            instruction=f"You are {name}.",
            model_client=client,
        )
        return agent

    async def test_join_and_leave_network(self):
        transport = MockSenseTransport()
        agent = self._make_agent("watcher")

        await agent.join_network(transport, "test-ns", ["alerts"])
        assert agent._transport is not None
        assert agent._signal_task is not None

        await agent.leave_network()
        assert agent._transport is None

    async def test_broadcast_signal(self):
        hub = _MockSenseHub()
        t1 = MockSenseTransport(hub)
        t2 = MockSenseTransport(hub)

        sender = self._make_agent("sender")
        receiver = self._make_agent("receiver")

        received_signals: list[Signal] = []

        @receiver.on_signal("alert")
        async def handle_alert(signal: Signal):
            received_signals.append(signal)

        await sender.join_network(t1, "test-ns", ["alerts"])
        await receiver.join_network(t2, "test-ns", ["alerts"])

        signal = Signal(kind="alert", sender="sender", payload={"cpu": 95})
        await sender.broadcast("alerts", signal)

        # Give signal loop time to process
        await asyncio.sleep(0.3)

        assert len(received_signals) == 1
        assert received_signals[0].kind == "alert"
        assert received_signals[0].payload == {"cpu": 95}

        await sender.leave_network()
        await receiver.leave_network()

    async def test_request_response(self):
        """Test request/response pattern between two agents."""
        hub = _MockSenseHub()
        t1 = MockSenseTransport(hub)
        t2 = MockSenseTransport(hub)

        # Worker agent that responds with "CPU at 45%"
        worker = self._make_agent("cpu-watcher", response_text="CPU at 45%")
        await worker.join_network(t1, "test-ns", ["tasks"])

        # Commander agent
        commander = self._make_agent("commander", response_text="Analysis complete")
        await commander.join_network(t2, "test-ns", ["tasks"])

        # Commander requests work from worker
        result = await commander.request(
            "cpu-watcher", "What is the CPU usage?", timeout=5.0
        )
        assert result == "CPU at 45%"

        await worker.leave_network()
        await commander.leave_network()

    async def test_request_timeout(self):
        """Test that request times out when no agent responds."""
        transport = MockSenseTransport()
        agent = self._make_agent("lonely-agent")
        await agent.join_network(transport, "test-ns", ["tasks"])

        with pytest.raises(TimeoutError, match="No response"):
            await agent.request("nonexistent-agent", "hello?", timeout=0.5)

        await agent.leave_network()

    async def test_on_signal_handler(self):
        """Test custom signal handler registration."""
        transport = MockSenseTransport()
        agent = self._make_agent("handler-agent")

        received_signals: list[Signal] = []

        @agent.on_signal("alert")
        async def handle_alert(signal: Signal):
            received_signals.append(signal)

        await agent.join_network(transport, "test-ns", ["alerts"])

        # Simulate receiving an alert from another agent
        alert = Signal(kind="alert", sender="other-agent", payload={"severity": "high"})
        queue = transport.hub.queues.get("handler-agent")
        if queue:
            await queue.put(alert)

        # Give signal loop time to process
        await asyncio.sleep(0.2)

        assert len(received_signals) == 1
        assert received_signals[0].payload["severity"] == "high"

        await agent.leave_network()

    async def test_skip_own_signals(self):
        """Agents should not process their own signals."""
        transport = MockSenseTransport()
        agent = self._make_agent("self-talker")

        received_signals: list[Signal] = []

        @agent.on_signal("alert")
        async def handle_alert(signal: Signal):
            received_signals.append(signal)

        await agent.join_network(transport, "test-ns", ["alerts"])

        # Put our own signal in the queue
        own_signal = Signal(kind="alert", sender="self-talker", payload={})
        queue = transport.hub.queues.get("self-talker")
        if queue:
            await queue.put(own_signal)

        await asyncio.sleep(0.2)

        # Should not have processed our own signal
        assert len(received_signals) == 0

        await agent.leave_network()

    async def test_targeted_signal_filtering(self):
        """Agents should skip signals targeted at other agents."""
        transport = MockSenseTransport()
        agent = self._make_agent("agent-a")

        received_signals: list[Signal] = []

        @agent.on_signal("request")
        async def handle_request(signal: Signal):
            received_signals.append(signal)

        await agent.join_network(transport, "test-ns", ["tasks"])

        # Signal targeted at another agent
        signal = Signal(
            kind="request",
            sender="commander",
            payload={"task": "check logs"},
            target="agent-b",
        )
        queue = transport.hub.queues.get("agent-a")
        if queue:
            await queue.put(signal)

        await asyncio.sleep(0.2)

        # Should not have processed it
        assert len(received_signals) == 0

        await agent.leave_network()


# ---------- Claim protocol tests ----------


class TestClaimProtocol:
    async def test_claim_incident(self):
        """Test basic incident claiming."""
        hub = _MockSenseHub()
        transport = MockSenseTransport(hub)
        agent = SenseAgent(
            name="commander",
            instruction="Incident commander",
            model_client=MockLLMClient([MockResponse(text="claimed")]),
        )
        await agent.join_network(transport, "test-ns", ["tasks"])

        # Mark ourselves as having claimed (simulate winning)
        agent._claimed_incidents.add("incident-001")
        won = await agent.claim_incident("incident-001", "tasks")
        assert won is True

        await agent.leave_network()

    async def test_release_incident(self):
        """Test releasing a claimed incident."""
        hub = _MockSenseHub()
        transport = MockSenseTransport(hub)
        agent = SenseAgent(
            name="commander",
            instruction="Incident commander",
            model_client=MockLLMClient([MockResponse(text="released")]),
        )
        await agent.join_network(transport, "test-ns", ["tasks"])

        agent._claimed_incidents.add("incident-001")
        await agent.release_incident("incident-001", "tasks")
        assert "incident-001" not in agent._claimed_incidents

        await agent.leave_network()


# ---------- SenseNetwork tests ----------


class TestSenseNetwork:
    async def test_add_agent(self):
        transport = MockSenseTransport()
        network = SenseNetwork(namespace="test-ns", transport=transport)

        agent = SenseAgent(
            name="watcher",
            instruction="Watch things",
            model_client=MockLLMClient([MockResponse(text="ok")]),
        )
        await network.add(agent, channels=["alerts"])
        assert len(network.agents) == 1

        await network.stop()

    async def test_add_non_sense_agent_raises(self):
        transport = MockSenseTransport()
        network = SenseNetwork(namespace="test-ns", transport=transport)

        agent = Agent(
            name="plain-agent",
            instruction="I am plain",
            model_client=MockLLMClient([MockResponse(text="ok")]),
        )
        with pytest.raises(TypeError, match="must inherit from SenseMixin"):
            await network.add(agent)

    async def test_stop_disconnects_all(self):
        transport = MockSenseTransport()
        network = SenseNetwork(namespace="test-ns", transport=transport)

        agent1 = SenseAgent(
            name="agent-1",
            instruction="Agent 1",
            model_client=MockLLMClient([MockResponse(text="ok")]),
        )
        agent2 = SenseAgent(
            name="agent-2",
            instruction="Agent 2",
            model_client=MockLLMClient([MockResponse(text="ok")]),
        )

        await network.add(agent1, channels=["alerts"])
        await network.add(agent2, channels=["alerts"])
        assert len(network.agents) == 2

        await network.stop()
        assert len(network.agents) == 0
        assert agent1._transport is None
        assert agent2._transport is None


# ---------- Event dataclass tests ----------


class TestSenseEvents:
    def test_signal_received_event(self):
        event = SignalReceivedEvent(
            sender="agent-1",
            kind="alert",
            channel="bedsheet.ops.alerts",
            payload={"cpu": 95},
        )
        assert event.type == "signal_received"

    def test_agent_connected_event(self):
        event = AgentConnectedEvent(
            agent_id="agent-1",
            agent_name="CPU Watcher",
            namespace="cloud-ops",
        )
        assert event.type == "agent_connected"

    def test_agent_disconnected_event(self):
        event = AgentDisconnectedEvent(
            agent_id="agent-1",
            agent_name="CPU Watcher",
            namespace="cloud-ops",
        )
        assert event.type == "agent_disconnected"

    def test_remote_delegation_event(self):
        event = RemoteDelegationEvent(
            agent_name="cpu-watcher",
            task="Check CPU",
            correlation_id="abc123",
        )
        assert event.type == "remote_delegation"

    def test_remote_result_event(self):
        event = RemoteResultEvent(
            agent_name="cpu-watcher",
            result="CPU at 45%",
            correlation_id="abc123",
        )
        assert event.type == "remote_result"
