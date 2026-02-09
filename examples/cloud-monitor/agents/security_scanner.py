"""Security Scanner agent - checks open ports and login attempts."""
import asyncio
import os
import socket
import sys

from bedsheet import Agent, ActionGroup, SenseMixin
from bedsheet.llm.anthropic import AnthropicClient
from bedsheet.sense.pubnub_transport import PubNubTransport


class SecurityScanner(SenseMixin, Agent):
    pass


security_tools = ActionGroup("security_tools", "Security scanning tools")


@security_tools.action("check_open_ports", "Scan common ports on localhost")
async def check_open_ports() -> str:
    common_ports = {
        22: "SSH", 80: "HTTP", 443: "HTTPS", 3306: "MySQL",
        5432: "PostgreSQL", 6379: "Redis", 8080: "HTTP-Alt",
        8443: "HTTPS-Alt", 27017: "MongoDB",
    }
    results = []
    for port, service in common_ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            result = sock.connect_ex(("127.0.0.1", port))
            status = "OPEN" if result == 0 else "closed"
            if result == 0:
                results.append(f"  Port {port} ({service}): {status}")
        except Exception:
            pass
        finally:
            sock.close()

    if not results:
        return "No common ports open on localhost"
    return "Open ports:\n" + "\n".join(results)


@security_tools.action("check_failed_logins", "Check for recent failed login attempts (simulated)")
async def check_failed_logins() -> str:
    # Simulated data for demo purposes
    return (
        "Recent failed login attempts (last 24h):\n"
        "  SSH: 3 attempts from 192.168.1.50 (blocked)\n"
        "  SSH: 1 attempt from 10.0.0.15\n"
        "  Web: 5 attempts from 203.0.113.42 (rate limited)\n"
        "  Total: 9 failed attempts, 1 IP blocked"
    )


async def main():
    transport = PubNubTransport(
        subscribe_key=os.environ["PUBNUB_SUBSCRIBE_KEY"],
        publish_key=os.environ["PUBNUB_PUBLISH_KEY"],
    )

    agent = SecurityScanner(
        name="security-scanner",
        instruction=(
            "You are a security scanning agent. When asked about security, "
            "use your tools to check open ports and failed login attempts. "
            "Report findings with severity assessment."
        ),
        model_client=AnthropicClient(),
    )
    agent.add_action_group(security_tools)

    await agent.join_network(transport, "cloud-ops", ["alerts", "tasks"])
    print("[security-scanner] Online and ready...")

    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        pass
    finally:
        await agent.leave_network()


if __name__ == "__main__":
    asyncio.run(main())
