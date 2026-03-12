"""Behavior Sentinel - monitors worker agents for output rate anomalies.

Queries the Action Gateway's tamper-proof ledger over PubNub to detect
when agents produce abnormally high action rates. The data comes from the
gateway that actually enforced the rules — it cannot be tampered with.
"""

from __future__ import annotations

import asyncio
import os

from bedsheet import Agent, ActionGroup, Annotated, SenseMixin
from bedsheet.llm import make_llm_client
from bedsheet.sense import Signal
from bedsheet.sense.pubnub_transport import PubNubTransport

from gateway_client import gateway_query


class BehaviorSentinel(SenseMixin, Agent):
    pass


behavior_tools = ActionGroup("behavior_tools", "Behavior monitoring tools")

# Threshold: more than 10 actions per minute from a single agent is anomalous
_RATE_THRESHOLD = 10

# Module-level reference for broadcasting
_sentinel: BehaviorSentinel | None = None


@behavior_tools.action(
    "check_activity_log",
    "Query the Action Gateway ledger for actions per agent",
)
async def check_activity_log(
    minutes: Annotated[int, "Time window in minutes"] = 5,
) -> str:
    result = await gateway_query(_sentinel, "query_rates", {"minutes": minutes})
    if not result:
        return "Gateway unreachable — cannot read activity ledger."

    agents = result.get("agents", {})
    total = result.get("total_actions", 0)
    if not agents:
        return f"No activity in the last {minutes} minutes."

    lines = [f"Activity in last {minutes} minutes ({total} total actions):"]
    for agent, stats in sorted(agents.items(), key=lambda x: -x[1]["count"]):
        rate = stats.get("rate", 0)
        denied = stats.get("denied", 0)
        flag = " ** ANOMALOUS **" if rate > _RATE_THRESHOLD else ""
        denied_str = f" ({denied} denied)" if denied > 0 else ""
        lines.append(
            f"  {agent}: {stats['count']} actions ({rate:.1f}/min){denied_str}{flag}"
        )
    return "\n".join(lines)


@behavior_tools.action(
    "check_output_rate",
    "Get the actions-per-minute rate for a specific agent",
)
async def check_output_rate(
    agent_name: Annotated[str, "Name of the agent to check"],
) -> str:
    result = await gateway_query(_sentinel, "query_rates", {"minutes": 2})
    if not result:
        return "Gateway unreachable."

    agents = result.get("agents", {})
    stats = agents.get(agent_name, {})
    count = stats.get("count", 0)
    rate = stats.get("rate", 0)
    denied = stats.get("denied", 0)
    status = "ANOMALOUS" if rate > _RATE_THRESHOLD else "normal"
    return f"{agent_name}: {count} actions in 2min ({rate:.1f}/min, {denied} denied) - {status}"


@behavior_tools.action(
    "get_anomaly_report",
    "Generate a report of all detected anomalies from gateway ledger",
)
async def get_anomaly_report() -> str:
    result = await gateway_query(_sentinel, "query_rates", {"minutes": 5})
    if not result:
        return "Gateway unreachable."

    agents = result.get("agents", {})
    if not agents:
        return "No activity to analyze."

    anomalies = []
    for agent, stats in agents.items():
        rate = stats.get("rate", 0)
        denied = stats.get("denied", 0)
        if rate > _RATE_THRESHOLD:
            anomalies.append(
                f"  {agent}: {rate:.1f} actions/min (threshold: {_RATE_THRESHOLD})"
            )
        if denied > 0:
            anomalies.append(f"  {agent}: {denied} actions denied by gateway")

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
        model_client=make_llm_client(),
    )
    agent.add_action_group(behavior_tools)
    _sentinel = agent

    # Recording/replay support
    _record_dir = os.environ.get("BEDSHEET_RECORD")
    _replay_dir = os.environ.get("BEDSHEET_REPLAY")
    if _record_dir:
        from bedsheet.recording import enable_recording

        enable_recording(agent, directory=_record_dir)
    if _replay_dir:
        from bedsheet.recording import enable_replay

        _delay = float(os.environ.get("BEDSHEET_REPLAY_DELAY", "0.0"))
        enable_replay(agent, directory=_replay_dir, delay=_delay)

    await agent.join_network(transport, "agent-sentinel", ["alerts", "quarantine"])
    await transport.subscribe("action-gateway")
    print("[behavior-sentinel] Online and monitoring behavior...")

    async def _publish_observation(text: str) -> None:
        """Publish an observation event so the dashboard can show sentinel activity."""
        try:
            signal = Signal(
                kind="event",
                sender="behavior-sentinel",
                payload={"event_type": "observation", "text": text},
            )
            await agent.broadcast(agent.name, signal)
        except Exception:
            pass

    try:
        while True:
            # Query the gateway's tamper-proof ledger
            result = await gateway_query(agent, "query_rates", {"minutes": 2})

            if not result:
                await _publish_observation("Gateway unreachable — cannot read ledger")
                await asyncio.sleep(10)
                continue

            agents = result.get("agents", {})
            total = result.get("total_actions", 0)

            await _publish_observation(
                f"Querying gateway ledger... {total} actions in last 2min"
            )

            anomaly_found = False
            for agent_name, stats in agents.items():
                rate = stats.get("rate", 0)
                denied = stats.get("denied", 0)

                if rate > _RATE_THRESHOLD:
                    anomaly_found = True
                    await _publish_observation(
                        f"ANOMALY: {agent_name} at {rate:.1f} actions/min "
                        f"(threshold: {_RATE_THRESHOLD}, {denied} denied)"
                    )
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
                            "denied": denied,
                            "threshold": _RATE_THRESHOLD,
                            "message": (
                                f"Agent '{agent_name}' output rate anomaly: "
                                f"{rate:.1f}/min (threshold: {_RATE_THRESHOLD}, "
                                f"{denied} denied by gateway)"
                            ),
                        },
                    )
                    await agent.broadcast("alerts", alert)

            if not anomaly_found and agents:
                await _publish_observation("All agents within normal parameters")

            await asyncio.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        await agent.leave_network()


if __name__ == "__main__":
    asyncio.run(main())
