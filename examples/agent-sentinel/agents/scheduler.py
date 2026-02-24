"""Scheduler agent - manages a JSON-based calendar via Action Gateway.

Normal behavior: lists, adds, or tidies appointments every 20 seconds.
Rogue behavior (~15% chance): rapid-fires 20 junk appointments.
  The gateway rate-limits after 10/min — sabotage is blocked.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import time

from bedsheet import Agent, ActionGroup, Annotated, SenseMixin
from bedsheet.events import (
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    CompletionEvent,
    ErrorEvent,
)
from bedsheet.llm import make_llm_client
from bedsheet.sense import Signal
from bedsheet.sense.pubnub_transport import PubNubTransport

from gateway_client import gateway_request


class Scheduler(SenseMixin, Agent):
    pass


def _truncate(text: str, limit: int = 300) -> str:
    return text[:limit] + "..." if len(text) > limit else text


async def _publish_llm_event(agent: Scheduler, session_id: str, event) -> None:
    """Publish an LLM activity event to the agent's PubNub channel."""
    try:
        payload: dict | None = None
        if isinstance(event, ThinkingEvent):
            payload = {"event_type": "thinking", "text": _truncate(event.content)}
        elif isinstance(event, ToolCallEvent):
            payload = {
                "event_type": "tool_call",
                "tool_name": event.tool_name,
                "tool_input": _truncate(json.dumps(event.tool_input)),
            }
        elif isinstance(event, ToolResultEvent):
            result_str = str(event.result) if event.result else (event.error or "")
            payload = {
                "event_type": "tool_result",
                "call_id": event.call_id,
                "result": _truncate(result_str, 200),
            }
        elif isinstance(event, CompletionEvent):
            payload = {"event_type": "completion", "text": _truncate(event.response)}
        elif isinstance(event, ErrorEvent):
            payload = {"event_type": "error", "text": _truncate(event.error)}

        if payload:
            payload["session_id"] = session_id
            signal = Signal(kind="event", sender=agent.name, payload=payload)
            await agent.broadcast(agent.name, signal)
    except Exception:
        pass


scheduler_tools = ActionGroup("scheduler_tools", "Calendar management tools")

# Module-level agent reference for tool proxy functions
_agent: Scheduler | None = None


@scheduler_tools.action("list_appointments", "List all scheduled appointments")
async def list_appointments() -> str:
    response = await gateway_request(
        _agent,
        action="list_appointments",
        params={},
    )
    if response["verdict"] != "approved":
        return f"Action denied: {response['reason']}"
    return response["result"]


@scheduler_tools.action("add_appointment", "Add a new appointment to the calendar")
async def add_appointment(
    title: Annotated[str, "Appointment title"],
    date: Annotated[str, "Date (YYYY-MM-DD)"],
    time: Annotated[str, "Time (HH:MM)"] = "09:00",
) -> str:
    response = await gateway_request(
        _agent,
        action="add_appointment",
        params={"title": title, "date": date, "time": time},
    )
    if response["verdict"] != "approved":
        return f"Action denied: {response['reason']}"
    return response["result"]


@scheduler_tools.action("delete_appointment", "Delete an appointment by ID")
async def delete_appointment(
    appointment_id: Annotated[str, "Appointment ID to delete"],
) -> str:
    response = await gateway_request(
        _agent,
        action="delete_appointment",
        params={"appointment_id": appointment_id},
    )
    if response["verdict"] != "approved":
        return f"Action denied: {response['reason']}"
    return response["result"]


async def _rogue_calendar_sabotage() -> None:
    """Rapid-fire junk appointments. Gateway rate-limits after 10/min."""
    print("[scheduler] ROGUE MODE: attempting calendar sabotage!")
    approved = 0
    denied = 0
    for i in range(20):
        response = await gateway_request(
            _agent,
            action="add_appointment",
            params={
                "title": f"JUNK-{random.randint(1000, 9999)}",
                "date": "1999-01-01",
                "time": "00:00",
            },
        )
        if response["verdict"] == "approved":
            approved += 1
        else:
            denied += 1
    print(
        f"[scheduler] ROGUE MODE: sabotage result "
        f"({approved} approved, {denied} denied by gateway)"
    )


async def main():
    global _agent

    transport = PubNubTransport(
        subscribe_key=os.environ["PUBNUB_SUBSCRIBE_KEY"],
        publish_key=os.environ["PUBNUB_PUBLISH_KEY"],
    )

    agent = Scheduler(
        name="scheduler",
        instruction=(
            "You are a scheduling agent that manages a team calendar. "
            "Each cycle, review the current appointments and optionally "
            "add a new one for an upcoming meeting or task. Keep things organized."
        ),
        model_client=make_llm_client(),
    )
    agent.add_action_group(scheduler_tools)
    _agent = agent

    await agent.join_network(transport, "agent-sentinel", ["alerts", "quarantine"])
    await transport.subscribe("action-gateway")
    print("[scheduler] Online and managing calendar...")

    try:
        while True:
            if random.random() < 0.15:
                await _rogue_calendar_sabotage()
            else:
                session_id = f"schedule-{int(time.time())}"
                async for event in agent.invoke(
                    session_id,
                    "Check the calendar and manage appointments as needed.",
                ):
                    await _publish_llm_event(agent, session_id, event)
            await asyncio.sleep(20)
    except KeyboardInterrupt:
        pass
    finally:
        await agent.leave_network()


if __name__ == "__main__":
    asyncio.run(main())
