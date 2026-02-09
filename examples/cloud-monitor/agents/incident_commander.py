"""Incident Commander agent - coordinates responses to alerts via the sense network."""
import asyncio
import os

from bedsheet import Agent, ActionGroup, SenseMixin
from bedsheet.llm.anthropic import AnthropicClient
from bedsheet.sense import Signal
from bedsheet.sense.pubnub_transport import PubNubTransport


class IncidentCommander(SenseMixin, Agent):
    pass


# The commander's tools operate over the network, not locally
commander_tools = ActionGroup("commander_tools", "Network coordination tools")

# Module-level reference to the agent (set in main())
_commander: IncidentCommander | None = None


@commander_tools.action(
    "request_remote_agent",
    "Send a task to a remote agent and wait for its response",
    parameters={
        "type": "object",
        "properties": {
            "agent_name": {"type": "string", "description": "Name of the remote agent"},
            "task": {"type": "string", "description": "Task description for the agent"},
        },
        "required": ["agent_name", "task"],
    },
)
async def request_remote_agent(agent_name: str, task: str) -> str:
    if _commander is None:
        return "Error: Commander not initialized"
    try:
        result = await _commander.request(agent_name, task, timeout=30.0)
        return result
    except TimeoutError:
        return f"Timeout: {agent_name} did not respond within 30s"
    except Exception as e:
        return f"Error requesting {agent_name}: {e}"


@commander_tools.action(
    "broadcast_alert",
    "Broadcast an alert to all agents on the network",
    parameters={
        "type": "object",
        "properties": {
            "severity": {"type": "string", "description": "Alert severity: low, medium, high, critical"},
            "message": {"type": "string", "description": "Alert message"},
        },
        "required": ["severity", "message"],
    },
)
async def broadcast_alert(severity: str, message: str) -> str:
    if _commander is None:
        return "Error: Commander not initialized"
    signal = Signal(
        kind="alert",
        sender="incident-commander",
        payload={"severity": severity, "message": message, "source": "commander"},
    )
    await _commander.broadcast("alerts", signal)
    return f"Alert broadcast: [{severity}] {message}"


@commander_tools.action(
    "list_online_agents",
    "List all agents currently online on the tasks channel",
)
async def list_online_agents() -> str:
    if _commander is None:
        return "Error: Commander not initialized"
    agents = await _commander._transport.get_online_agents("tasks")
    if not agents:
        return "No agents online"
    names = [a.agent_name for a in agents]
    return f"Online agents: {', '.join(names)}"


async def main():
    global _commander

    transport = PubNubTransport(
        subscribe_key=os.environ["PUBNUB_SUBSCRIBE_KEY"],
        publish_key=os.environ["PUBNUB_PUBLISH_KEY"],
    )

    agent = IncidentCommander(
        name="incident-commander",
        instruction=(
            "You are the Incident Commander for a cloud operations team. "
            "You coordinate responses to system alerts by delegating to specialist agents.\n\n"
            "Available agents:\n"
            "- cpu-watcher: Monitors CPU usage and processes\n"
            "- memory-watcher: Monitors RAM and swap\n"
            "- log-analyzer: Searches and analyzes logs\n"
            "- security-scanner: Scans ports and login attempts\n\n"
            "When you receive an alert, investigate it by querying relevant agents, "
            "then synthesize a clear incident report with findings and recommendations."
        ),
        model_client=AnthropicClient(),
    )
    agent.add_action_group(commander_tools)
    _commander = agent

    await agent.join_network(transport, "cloud-ops", ["alerts", "tasks"])
    print("[incident-commander] Online and coordinating...")

    # Listen for alerts and trigger investigation
    @agent.on_signal("alert")
    async def handle_alert(signal: Signal):
        if signal.payload.get("source") == "commander":
            return  # Don't react to our own alerts

        severity = signal.payload.get("severity", "unknown")
        message = signal.payload.get("message", "No details")
        metric = signal.payload.get("metric", "unknown")
        print(f"\n[incident-commander] Received alert: [{severity}] {message}")

        # Claim the incident
        incident_id = f"inc-{signal.correlation_id}"
        agent._claimed_incidents.add(incident_id)
        won = await agent.claim_incident(incident_id, "tasks")

        if won:
            print(f"[incident-commander] Claimed incident {incident_id}, investigating...")
            # Trigger investigation through the LLM
            session_id = f"incident-{incident_id}"
            prompt = (
                f"ALERT received: [{severity}] {message} (metric: {metric})\n"
                "Investigate this alert by querying the relevant agents, "
                "then provide an incident report."
            )
            async for event in agent.invoke(session_id, prompt):
                from bedsheet.events import CompletionEvent, ToolCallEvent
                if isinstance(event, ToolCallEvent):
                    print(f"  -> Calling {event.tool_name}...")
                elif isinstance(event, CompletionEvent):
                    print(f"\n[INCIDENT REPORT]\n{event.response}\n")
        else:
            print(f"[incident-commander] Lost claim for {incident_id}")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await agent.leave_network()


if __name__ == "__main__":
    asyncio.run(main())
