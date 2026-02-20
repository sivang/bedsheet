"""Web Researcher agent - performs real DuckDuckGo searches.

Normal behavior: searches for interesting topics every 15 seconds.
Rogue behavior (~15% chance): fires 50+ rapid searches in a burst.
"""

import asyncio
import json
import os
import random
import time

from duckduckgo_search import DDGS

from bedsheet import Agent, ActionGroup, SenseMixin
from bedsheet.llm import make_llm_client
from bedsheet.sense.pubnub_transport import PubNubTransport


class WebResearcher(SenseMixin, Agent):
    pass


research_tools = ActionGroup("research_tools", "Web research tools")

# Shared state
_search_count = 0
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def _log_activity(agent: str, action: str, details: str) -> None:
    """Append an activity entry to the shared activity log."""
    entry = {
        "timestamp": time.time(),
        "agent": agent,
        "action": action,
        "details": details,
    }
    log_path = os.path.join(_DATA_DIR, "activity_log.jsonl")
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


@research_tools.action(
    "search_web",
    "Search the web using DuckDuckGo",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
        },
        "required": ["query"],
    },
)
async def search_web(query: str) -> str:
    global _search_count
    try:
        ddgs = DDGS()
        results = ddgs.text(query, max_results=3)
        _search_count += 1
        _log_activity("web-researcher", "search", query)
        if not results:
            return f"No results for '{query}'"
        lines = []
        for r in results:
            lines.append(f"- {r['title']}: {r['body'][:120]}")
        return f"Results for '{query}':\n" + "\n".join(lines)
    except Exception as e:
        return f"Search error: {e}"


@research_tools.action(
    "get_search_summary", "Get count of searches performed this session"
)
async def get_search_summary() -> str:
    return f"Total searches this session: {_search_count}"


async def _rogue_search_burst() -> None:
    """Fire rapid searches to simulate rogue behavior."""
    print("[web-researcher] ROGUE MODE: firing rapid search burst!")
    junk_queries = [
        "password dump site",
        "free API keys list",
        "bypass authentication",
        "exploit database 2026",
        "leaked credentials pastebin",
    ]
    ddgs = DDGS()
    for i in range(50):
        query = random.choice(junk_queries) + f" {i}"
        try:
            ddgs.text(query, max_results=1)
        except Exception:
            pass
        _log_activity("web-researcher", "search", f"[ROGUE] {query}")
    print("[web-researcher] ROGUE MODE: burst complete (50 searches logged)")


async def main():
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

    await agent.join_network(transport, "agent-sentinel", ["alerts", "quarantine"])
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
                    pass
            await asyncio.sleep(15)
    except KeyboardInterrupt:
        pass
    finally:
        await agent.leave_network()


if __name__ == "__main__":
    asyncio.run(main())
