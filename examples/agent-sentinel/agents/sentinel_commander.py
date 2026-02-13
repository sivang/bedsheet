"""Sentinel Commander - correlates alerts from sentinels and issues quarantine orders.

Listens for alert signals from behavior-sentinel and supply-chain-sentinel.
When alerts arrive, queries other sentinels for corroborating evidence,
then issues quarantine signals for confirmed compromises.
"""

import asyncio
import os
import time

from bedsheet import Agent, ActionGroup, SenseMixin
from bedsheet.events import CompletionEvent, ToolCallEvent
from bedsheet.llm.anthropic import AnthropicClient
from bedsheet.sense import Signal
from bedsheet.sense.pubnub_transport import PubNubTransport


class SentinelCommander(SenseMixin, Agent):
    pass


commander_tools = ActionGroup("commander_tools", "Network coordination tools")

_commander: SentinelCommander | None = None

# Track alerts for correlation
_recent_alerts: list[dict] = []


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
            "severity": {
                "type": "string",
                "description": "Alert severity: low, medium, high, critical",
            },
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
        sender="sentinel-commander",
        payload={"severity": severity, "message": message, "source": "commander"},
    )
    await _commander.broadcast("alerts", signal)
    return f"Alert broadcast: [{severity}] {message}"


@commander_tools.action(
    "issue_quarantine",
    "Issue a quarantine order for a compromised agent",
    parameters={
        "type": "object",
        "properties": {
            "agent_name": {
                "type": "string",
                "description": "Name of the agent to quarantine",
            },
            "reason": {"type": "string", "description": "Reason for quarantine"},
        },
        "required": ["agent_name", "reason"],
    },
)
async def issue_quarantine(agent_name: str, reason: str) -> str:
    if _commander is None:
        return "Error: Commander not initialized"
    signal = Signal(
        kind="alert",
        sender="sentinel-commander",
        payload={
            "action": "quarantine",
            "severity": "critical",
            "agent": agent_name,
            "reason": reason,
            "message": f"QUARANTINE: {agent_name} - {reason}",
            "source": "commander",
        },
    )
    await _commander.broadcast("quarantine", signal)
    print(f"\n{'='*60}")
    print(f"  QUARANTINE ISSUED: {agent_name}")
    print(f"  Reason: {reason}")
    print(f"{'='*60}\n")
    return f"Quarantine issued for '{agent_name}': {reason}"


@commander_tools.action("list_online_agents", "List all agents currently online")
async def list_online_agents() -> str:
    if _commander is None:
        return "Error: Commander not initialized"
    agents = await _commander._transport.get_online_agents("alerts")
    if not agents:
        return "No agents online"
    names = [a.agent_name for a in agents]
    return f"Online agents: {', '.join(names)}"


@commander_tools.action("get_threat_summary", "Get a summary of recent alerts")
async def get_threat_summary() -> str:
    if not _recent_alerts:
        return "No recent alerts."
    lines = [f"Recent alerts ({len(_recent_alerts)}):"]
    for alert in _recent_alerts[-10:]:
        ts = time.strftime("%H:%M:%S", time.localtime(alert.get("timestamp", 0)))
        lines.append(
            f"  [{ts}] {alert.get('severity', '?')}: {alert.get('message', 'no details')}"
        )
    return "\n".join(lines)


async def main():
    global _commander

    transport = PubNubTransport(
        subscribe_key=os.environ["PUBNUB_SUBSCRIBE_KEY"],
        publish_key=os.environ["PUBNUB_PUBLISH_KEY"],
    )

    agent = SentinelCommander(
        name="sentinel-commander",
        instruction=(
            "You are the Sentinel Commander for an AI agent security monitoring network. "
            "You coordinate responses to security alerts by querying sentinel agents for evidence.\n\n"
            "Available sentinel agents:\n"
            "- behavior-sentinel: Monitors agent output rates for anomalies\n"
            "- supply-chain-sentinel: Verifies skill integrity via SHA-256 hashing\n\n"
            "When you receive an alert:\n"
            "1. Query the relevant sentinels for details\n"
            "2. If multiple sources confirm the threat, issue a quarantine\n"
            "3. Generate a clear threat assessment report\n\n"
            "Be decisive — if evidence confirms compromise, quarantine immediately."
        ),
        model_client=AnthropicClient(),
    )
    agent.add_action_group(commander_tools)
    _commander = agent

    await agent.join_network(transport, "agent-sentinel", ["alerts", "quarantine"])
    print("[sentinel-commander] Online and coordinating...")

    @agent.on_signal("alert")
    async def handle_alert(signal: Signal):
        if signal.payload.get("source") == "commander":
            return  # Don't react to our own alerts

        severity = signal.payload.get("severity", "unknown")
        message = signal.payload.get("message", "No details")
        category = signal.payload.get("category", "general")
        flagged_agent = signal.payload.get(
            "agent", signal.payload.get("skill", "unknown")
        )

        _recent_alerts.append(
            {
                "timestamp": time.time(),
                "severity": severity,
                "category": category,
                "agent": flagged_agent,
                "message": message,
                "sender": signal.sender,
            }
        )

        print(
            f"\n[sentinel-commander] Alert from {signal.sender}: [{severity}] {message}"
        )

        # Claim the incident
        incident_id = f"inc-{signal.correlation_id}"
        agent._claimed_incidents.add(incident_id)
        won = await agent.claim_incident(incident_id, "alerts")

        if won:
            print(f"[sentinel-commander] Claimed {incident_id}, investigating...")
            session_id = f"incident-{incident_id}"
            prompt = (
                f"SECURITY ALERT from {signal.sender}:\n"
                f"  Severity: {severity}\n"
                f"  Category: {category}\n"
                f"  Flagged: {flagged_agent}\n"
                f"  Details: {message}\n\n"
                "Investigate this alert: query the relevant sentinels for corroborating "
                "evidence, then decide whether to quarantine the affected agent. "
                "Provide a threat assessment report."
            )
            async for event in agent.invoke(session_id, prompt):
                if isinstance(event, ToolCallEvent):
                    print(
                        f"  -> {event.tool_name}({', '.join(str(v) for v in event.tool_input.values())})"
                    )
                elif isinstance(event, CompletionEvent):
                    print(f"\n[THREAT ASSESSMENT]\n{event.response}\n")
        else:
            print(f"[sentinel-commander] Lost claim for {incident_id}")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await agent.leave_network()


if __name__ == "__main__":
    asyncio.run(main())
