"""Log Analyzer agent - analyzes system logs for errors and patterns."""
import asyncio
import io
import os
import re
from collections import Counter

from bedsheet import Agent, ActionGroup, SenseMixin
from bedsheet.llm.anthropic import AnthropicClient
from bedsheet.sense.pubnub_transport import PubNubTransport


class LogAnalyzer(SenseMixin, Agent):
    pass


log_tools = ActionGroup("log_tools", "Log analysis tools")

# Simulated log buffer for demo purposes
_LOG_BUFFER = io.StringIO(
    "2024-01-15 10:00:01 INFO Server started\n"
    "2024-01-15 10:00:05 INFO Request received: GET /api/health\n"
    "2024-01-15 10:00:10 WARN High latency on /api/users: 2500ms\n"
    "2024-01-15 10:00:15 ERROR Connection timeout to database\n"
    "2024-01-15 10:00:20 ERROR Failed to process request: timeout\n"
    "2024-01-15 10:00:25 INFO Request received: GET /api/health\n"
    "2024-01-15 10:00:30 WARN Memory pressure detected\n"
    "2024-01-15 10:00:35 ERROR Connection refused: redis://localhost:6379\n"
    "2024-01-15 10:00:40 INFO Auto-scaling triggered\n"
    "2024-01-15 10:00:45 INFO Request received: POST /api/data\n"
)


@log_tools.action("tail_log", "Get the last N lines from the log")
async def tail_log(lines: int = 10) -> str:
    _LOG_BUFFER.seek(0)
    all_lines = _LOG_BUFFER.readlines()
    return "".join(all_lines[-lines:])


@log_tools.action("search_log", "Search logs for a pattern (regex supported)")
async def search_log(pattern: str) -> str:
    _LOG_BUFFER.seek(0)
    matches = [
        line.strip()
        for line in _LOG_BUFFER
        if re.search(pattern, line, re.IGNORECASE)
    ]
    if not matches:
        return f"No matches for '{pattern}'"
    return f"Found {len(matches)} matches:\n" + "\n".join(matches[:20])


@log_tools.action("get_error_rate", "Calculate the error rate from recent logs")
async def get_error_rate() -> str:
    _LOG_BUFFER.seek(0)
    levels = Counter()
    for line in _LOG_BUFFER:
        for level in ("INFO", "WARN", "ERROR"):
            if f" {level} " in line:
                levels[level] += 1
                break
    total = sum(levels.values())
    if total == 0:
        return "No log entries found"
    error_rate = (levels.get("ERROR", 0) / total) * 100
    return (
        f"Log summary: {total} entries, "
        f"INFO: {levels['INFO']}, WARN: {levels['WARN']}, ERROR: {levels['ERROR']}, "
        f"Error rate: {error_rate:.1f}%"
    )


async def main():
    transport = PubNubTransport(
        subscribe_key=os.environ["PUBNUB_SUBSCRIBE_KEY"],
        publish_key=os.environ["PUBNUB_PUBLISH_KEY"],
    )

    agent = LogAnalyzer(
        name="log-analyzer",
        instruction=(
            "You are a log analysis agent. When asked about logs, use your tools "
            "to search, tail, and analyze log entries. Report error rates, patterns, "
            "and notable events clearly."
        ),
        model_client=AnthropicClient(),
    )
    agent.add_action_group(log_tools)

    await agent.join_network(transport, "cloud-ops", ["alerts", "tasks"])
    print("[log-analyzer] Online and ready...")

    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        pass
    finally:
        await agent.leave_network()


if __name__ == "__main__":
    asyncio.run(main())
