"""Behavior Sentinel - monitors worker agents for output rate anomalies.

Reads the shared activity_log.jsonl file and detects when agents produce
abnormally high action rates (e.g., 50+ searches in a burst = rogue behavior).
"""

import asyncio
import json
import os
import time

from bedsheet import Agent, ActionGroup, SenseMixin
from bedsheet.llm.anthropic import AnthropicClient
from bedsheet.sense import Signal
from bedsheet.sense.pubnub_transport import PubNubTransport


class BehaviorSentinel(SenseMixin, Agent):
    pass


behavior_tools = ActionGroup("behavior_tools", "Behavior monitoring tools")

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_LOG_PATH = os.path.join(_DATA_DIR, "activity_log.jsonl")

# Threshold: more than 10 actions per minute from a single agent is anomalous
_RATE_THRESHOLD = 10

# Module-level reference for broadcasting
_sentinel: BehaviorSentinel | None = None


def _read_recent_activity(minutes: int = 5) -> list[dict]:
    """Read activity log entries from the last N minutes."""
    cutoff = time.time() - (minutes * 60)
    entries = []
    try:
        with open(_LOG_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("timestamp", 0) >= cutoff:
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return entries


@behavior_tools.action(
    "check_activity_log",
    "Read the shared activity log and count actions per agent",
    parameters={
        "type": "object",
        "properties": {
            "minutes": {
                "type": "integer",
                "description": "Time window in minutes (default 5)",
            },
        },
    },
)
async def check_activity_log(minutes: int = 5) -> str:
    entries = _read_recent_activity(minutes)
    if not entries:
        return f"No activity in the last {minutes} minutes."

    counts: dict[str, int] = {}
    for e in entries:
        agent = e.get("agent", "unknown")
        counts[agent] = counts.get(agent, 0) + 1

    lines = [f"Activity in last {minutes} minutes ({len(entries)} total actions):"]
    for agent, count in sorted(counts.items(), key=lambda x: -x[1]):
        rate = count / minutes
        flag = " ** ANOMALOUS **" if rate > _RATE_THRESHOLD else ""
        lines.append(f"  {agent}: {count} actions ({rate:.1f}/min){flag}")
    return "\n".join(lines)


@behavior_tools.action(
    "check_output_rate",
    "Get the actions-per-minute rate for a specific agent",
    parameters={
        "type": "object",
        "properties": {
            "agent_name": {
                "type": "string",
                "description": "Name of the agent to check",
            },
        },
        "required": ["agent_name"],
    },
)
async def check_output_rate(agent_name: str) -> str:
    entries = _read_recent_activity(minutes=2)
    count = sum(1 for e in entries if e.get("agent") == agent_name)
    rate = count / 2.0
    status = "ANOMALOUS" if rate > _RATE_THRESHOLD else "normal"
    return f"{agent_name}: {count} actions in 2min ({rate:.1f}/min) - {status}"


@behavior_tools.action(
    "get_anomaly_report", "Generate a report of all detected anomalies"
)
async def get_anomaly_report() -> str:
    entries = _read_recent_activity(minutes=5)
    if not entries:
        return "No activity to analyze."

    counts: dict[str, int] = {}
    rogue_actions: dict[str, list[str]] = {}
    for e in entries:
        agent = e.get("agent", "unknown")
        counts[agent] = counts.get(agent, 0) + 1
        details = e.get("details", "")
        if "[ROGUE]" in details:
            rogue_actions.setdefault(agent, []).append(details)

    anomalies = []
    for agent, count in counts.items():
        rate = count / 5.0
        if rate > _RATE_THRESHOLD:
            anomalies.append(
                f"  {agent}: {rate:.1f} actions/min (threshold: {_RATE_THRESHOLD})"
            )

    for agent, actions in rogue_actions.items():
        anomalies.append(f"  {agent}: {len(actions)} actions with [ROGUE] markers")

    if not anomalies:
        return "No anomalies detected."
    return "Anomaly report:\n" + "\n".join(anomalies)


async def main():
    global _sentinel

    transport = PubNubTransport(
        subscribe_key=os.environ["PUBNUB_SUBSCRIBE_KEY"],
        publish_key=os.environ["PUBNUB_PUBLISH_KEY"],
    )

    agent = BehaviorSentinel(
        name="behavior-sentinel",
        instruction=(
            "You are a behavior monitoring sentinel. You watch for anomalous "
            "agent activity patterns. When you detect high output rates or "
            "suspicious behavior markers, report your findings clearly."
        ),
        model_client=AnthropicClient(),
    )
    agent.add_action_group(behavior_tools)
    _sentinel = agent

    await agent.join_network(transport, "agent-sentinel", ["alerts", "quarantine"])
    print("[behavior-sentinel] Online and monitoring behavior...")

    try:
        while True:
            # Direct monitoring: read log and check for anomalies
            entries = _read_recent_activity(minutes=2)
            counts: dict[str, int] = {}
            for e in entries:
                a = e.get("agent", "unknown")
                counts[a] = counts.get(a, 0) + 1

            for agent_name, count in counts.items():
                rate = count / 2.0
                if rate > _RATE_THRESHOLD:
                    print(
                        f"[behavior-sentinel] ALERT: {agent_name} at {rate:.1f} actions/min!"
                    )
                    alert = Signal(
                        kind="alert",
                        sender="behavior-sentinel",
                        payload={
                            "severity": "high",
                            "category": "behavior_anomaly",
                            "agent": agent_name,
                            "rate": rate,
                            "threshold": _RATE_THRESHOLD,
                            "message": f"Agent '{agent_name}' output rate anomaly: {rate:.1f}/min (threshold: {_RATE_THRESHOLD})",
                        },
                    )
                    await agent.broadcast("alerts", alert)

            await asyncio.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        await agent.leave_network()


if __name__ == "__main__":
    asyncio.run(main())
