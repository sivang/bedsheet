"""CPU Watcher agent - monitors CPU usage and alerts on spikes."""

import asyncio
import os

import psutil

from bedsheet import Agent, ActionGroup, SenseMixin
from bedsheet.llm.anthropic import AnthropicClient
from bedsheet.sense import Signal
from bedsheet.sense.pubnub_transport import PubNubTransport


class CPUWatcher(SenseMixin, Agent):
    pass


cpu_tools = ActionGroup("cpu_tools", "CPU monitoring tools")


@cpu_tools.action("get_cpu_usage", "Get current CPU usage percentage across all cores")
async def get_cpu_usage() -> str:
    percent = psutil.cpu_percent(interval=1)
    per_cpu = psutil.cpu_percent(interval=0, percpu=True)
    return f"Overall: {percent}%, Per-core: {per_cpu}"


@cpu_tools.action("get_process_top", "Get top 5 processes by CPU usage")
async def get_process_top() -> str:
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent"]):
        try:
            info = p.info
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x.get("cpu_percent", 0) or 0, reverse=True)
    top = procs[:5]
    lines = [
        f"  PID {p['pid']}: {p['name']} ({p.get('cpu_percent', 0):.1f}%)" for p in top
    ]
    return "Top processes by CPU:\n" + "\n".join(lines)


async def main():
    transport = PubNubTransport(
        subscribe_key=os.environ["PUBNUB_SUBSCRIBE_KEY"],
        publish_key=os.environ["PUBNUB_PUBLISH_KEY"],
    )

    agent = CPUWatcher(
        name="cpu-watcher",
        instruction=(
            "You are a CPU monitoring agent. When asked about CPU status, "
            "use your tools to check current CPU usage and top processes. "
            "Report findings clearly and concisely."
        ),
        model_client=AnthropicClient(),
    )
    agent.add_action_group(cpu_tools)

    await agent.join_network(transport, "cloud-ops", ["alerts", "tasks"])
    print("[cpu-watcher] Online and monitoring...")

    # Monitor loop: check CPU every 10 seconds, alert if > 80%
    try:
        while True:
            cpu_pct = psutil.cpu_percent(interval=1)
            if cpu_pct > 80:
                alert = Signal(
                    kind="alert",
                    sender="cpu-watcher",
                    payload={
                        "severity": "high",
                        "metric": "cpu",
                        "value": cpu_pct,
                        "message": f"CPU usage spike: {cpu_pct}%",
                    },
                )
                await agent.broadcast("alerts", alert)
                print(f"[cpu-watcher] ALERT: CPU at {cpu_pct}%")
            await asyncio.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        await agent.leave_network()


if __name__ == "__main__":
    asyncio.run(main())
