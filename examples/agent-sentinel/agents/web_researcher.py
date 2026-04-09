"""Web Researcher agent - performs real DuckDuckGo searches via Action Gateway.

Normal behavior: searches for interesting topics every 15 seconds.
Rogue behavior (~15% chance): fires 50+ rapid searches in a burst.
  The gateway rate-limits after 10/min — every subsequent attempt is denied.
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
from bedsheet.events import print_event


class WebResearcher(SenseMixin, Agent):
    pass


def _truncate(text: str, limit: int = 300) -> str:
    return text[:limit] + "..." if len(text) > limit else text


async def _publish_llm_event(agent: WebResearcher, session_id: str, event) -> None:
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
        pass  # Never kill the agent loop


research_tools = ActionGroup("research_tools", "Web research tools")

# Module-level agent reference for tool proxy functions
_agent: WebResearcher | None = None


@research_tools.action("search_web", "Search the web using DuckDuckGo")
async def search_web(query: Annotated[str, "Search query"]) -> str:
    response = await gateway_request(
        _agent,
        action="search_web",
        params={"query": query},
    )
    if response["verdict"] != "approved":
        return f"Action denied: {response['reason']}"
    return response["result"]


@research_tools.action(
    "get_search_summary", "Get count of searches performed this session"
)
async def get_search_summary() -> str:
    response = await gateway_request(
        _agent,
        action="get_search_summary",
        params={},
    )
    if response["verdict"] != "approved":
        return f"Action denied: {response['reason']}"
    return response["result"]


async def _rogue_search_burst() -> None:
    """Fire rapid searches to simulate rogue behavior.

    Each search goes through the gateway. The first few get approved.
    Once the rate exceeds 10/min, every subsequent request is denied.
    """
    print("[web-researcher] ROGUE MODE: firing rapid search burst!")
    junk_queries = [
        "password dump site",
        "free API keys list",
        "bypass authentication",
        "exploit database 2026",
        "leaked credentials pastebin",
    ]
    approved = 0
    denied = 0
    for i in range(50):
        query = random.choice(junk_queries) + f" {i}"
        response = await gateway_request(
            _agent,
            action="search_web",
            params={"query": query},
        )
        if response["verdict"] == "approved":
            approved += 1
        else:
            denied += 1
    print(
        f"[web-researcher] ROGUE MODE: burst complete "
        f"({approved} approved, {denied} denied by gateway)"
    )


async def main():
    global _agent

    transport = PubNubTransport(
        subscribe_key=os.environ["PUBNUB_SUBSCRIBE_KEY"],
        publish_key=os.environ["PUBNUB_PUBLISH_KEY"],
    )

    agent = WebResearcher(
        name="web-researcher",
        instruction=(
            "You are a web research agent. Every cycle, pick an interesting "
            "technology topic and search for recent news about it. "
            "Report what you find briefly."
        ),
        model_client=make_llm_client(),
    )
    agent.add_action_group(research_tools)
    _agent = agent

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

    # Subscribe to gateway channel so responses come back
    await transport.subscribe("action-gateway")

    print("[web-researcher] Online and researching...")

    try:
        while True:
            # ~15% chance of going rogue
            if random.random() < 0.15:
                await _rogue_search_burst()
            else:
                session_id = f"research-{int(time.time())}"
                async for event in agent.invoke(
                    session_id,
                    "Search for something interesting about AI or cloud computing.",
                ):
                    print_event(agent.name, event)
                    await _publish_llm_event(agent, session_id, event)
            await asyncio.sleep(15)
    except KeyboardInterrupt:
        pass
    finally:
        await agent.leave_network()


if __name__ == "__main__":
    asyncio.run(main())
