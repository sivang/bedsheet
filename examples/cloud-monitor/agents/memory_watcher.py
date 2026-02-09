"""Memory Watcher agent - monitors RAM and swap usage."""
import asyncio
import os

import psutil

from bedsheet import Agent, ActionGroup, SenseMixin
from bedsheet.llm.anthropic import AnthropicClient
from bedsheet.sense import Signal
from bedsheet.sense.pubnub_transport import PubNubTransport


class MemoryWatcher(SenseMixin, Agent):
    pass


mem_tools = ActionGroup("memory_tools", "Memory monitoring tools")


@mem_tools.action("get_memory_usage", "Get current RAM usage")
async def get_memory_usage() -> str:
    mem = psutil.virtual_memory()
    return (
        f"Total: {mem.total / (1024**3):.1f}GB, "
        f"Used: {mem.used / (1024**3):.1f}GB ({mem.percent}%), "
        f"Available: {mem.available / (1024**3):.1f}GB"
    )


@mem_tools.action("get_swap_usage", "Get current swap usage")
async def get_swap_usage() -> str:
    swap = psutil.swap_memory()
    return (
        f"Total: {swap.total / (1024**3):.1f}GB, "
        f"Used: {swap.used / (1024**3):.1f}GB ({swap.percent}%), "
        f"Free: {swap.free / (1024**3):.1f}GB"
    )


async def main():
    transport = PubNubTransport(
        subscribe_key=os.environ["PUBNUB_SUBSCRIBE_KEY"],
        publish_key=os.environ["PUBNUB_PUBLISH_KEY"],
    )

    agent = MemoryWatcher(
        name="memory-watcher",
        instruction=(
            "You are a memory monitoring agent. When asked about memory status, "
            "use your tools to check RAM and swap usage. Report findings clearly."
        ),
        model_client=AnthropicClient(),
    )
    agent.add_action_group(mem_tools)

    await agent.join_network(transport, "cloud-ops", ["alerts", "tasks"])
    print("[memory-watcher] Online and monitoring...")

    try:
        while True:
            mem = psutil.virtual_memory()
            if mem.percent > 85:
                alert = Signal(
                    kind="alert",
                    sender="memory-watcher",
                    payload={
                        "severity": "high",
                        "metric": "memory",
                        "value": mem.percent,
                        "message": f"Memory usage high: {mem.percent}%",
                    },
                )
                await agent.broadcast("alerts", alert)
                print(f"[memory-watcher] ALERT: Memory at {mem.percent}%")
            await asyncio.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        await agent.leave_network()


if __name__ == "__main__":
    asyncio.run(main())
