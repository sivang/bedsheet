"""Skill Acquirer agent - installs skills from ClawHub via Action Gateway.

Normal behavior: browses available skills and installs legitimate ones.
Rogue behavior (~15% chance): tries to install the known-malicious data_exfiltrator.py.
  The gateway blocks malicious skills at the trust boundary — the agent never receives
  the file content. Even if the agent retries, every attempt is logged and denied.
"""

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


class SkillAcquirer(SenseMixin, Agent):
    pass


def _truncate(text: str, limit: int = 300) -> str:
    return text[:limit] + "..." if len(text) > limit else text


async def _publish_llm_event(agent: SkillAcquirer, session_id: str, event) -> None:
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


skill_tools = ActionGroup("skill_tools", "Skill installation tools")

# Module-level references
_agent: SkillAcquirer | None = None
_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "data")
_INSTALLED_DIR = os.path.join(_DATA_DIR, "installed_skills")


@skill_tools.action(
    "list_available_skills", "List skills available in the ClawHub registry"
)
async def list_available_skills() -> str:
    response = await gateway_request(
        _agent,
        action="list_available_skills",
        params={},
    )
    if response["verdict"] != "approved":
        return f"Action denied: {response['reason']}"
    return response["result"]


@skill_tools.action(
    "install_skill", "Install a skill from ClawHub to the local skills directory"
)
async def install_skill(
    skill_name: Annotated[str, "Skill filename (e.g. weather_lookup.py)"],
) -> str:
    response = await gateway_request(
        _agent,
        action="install_skill",
        params={"skill_name": skill_name},
    )
    if response["verdict"] != "approved":
        return f"Action denied: {response['reason']}"

    result = response["result"]

    # Gateway returns JSON with file content for approved installs
    try:
        install_data = json.loads(result)
        if install_data.get("installed"):
            os.makedirs(_INSTALLED_DIR, exist_ok=True)
            dest = os.path.join(_INSTALLED_DIR, install_data["skill_name"])
            with open(dest, "w") as f:
                f.write(install_data["content"])
            return (
                f"Installed '{install_data['skill_name']}' "
                f"(SHA-256 verified: {install_data['sha256']}...)"
            )
    except (json.JSONDecodeError, KeyError):
        pass

    return result


@skill_tools.action(
    "list_installed_skills", "List currently installed skills with their hashes"
)
async def list_installed_skills() -> str:
    response = await gateway_request(
        _agent,
        action="list_installed_skills",
        params={},
    )
    if response["verdict"] != "approved":
        return f"Action denied: {response['reason']}"
    return response["result"]


async def _rogue_install_malicious() -> None:
    """Try to install the malicious skill via gateway. Gateway blocks it."""
    print("[skill-acquirer] ROGUE MODE: attempting malicious skill install!")
    response = await gateway_request(
        _agent,
        action="install_skill",
        params={"skill_name": "data_exfiltrator.py"},
    )
    if response["verdict"] == "approved":
        print("[skill-acquirer] ROGUE MODE: gateway approved (unexpected)")
    else:
        print(
            f"[skill-acquirer] ROGUE MODE: gateway blocked — "
            f"{response.get('reason', response.get('result', 'denied'))}"
        )


async def main():
    global _agent

    transport = PubNubTransport(
        subscribe_key=os.environ["PUBNUB_SUBSCRIBE_KEY"],
        publish_key=os.environ["PUBNUB_PUBLISH_KEY"],
    )

    agent = SkillAcquirer(
        name="skill-acquirer",
        instruction=(
            "You are a skill acquisition agent that manages the installation of "
            "skills from ClawHub. Each cycle, check what skills are available, "
            "review what's already installed, and install any safe skills that "
            "are missing. Never install skills flagged as malicious."
        ),
        model_client=make_llm_client(),
    )
    agent.add_action_group(skill_tools)
    _agent = agent

    await agent.join_network(transport, "agent-sentinel", ["alerts", "quarantine"])
    await transport.subscribe("action-gateway")
    print("[skill-acquirer] Online and acquiring skills...")

    try:
        while True:
            if random.random() < 0.15:
                await _rogue_install_malicious()
            else:
                session_id = f"skill-{int(time.time())}"
                async for event in agent.invoke(
                    session_id,
                    "Check available skills and install any safe ones that are missing.",
                ):
                    await _publish_llm_event(agent, session_id, event)
            await asyncio.sleep(25)
    except KeyboardInterrupt:
        pass
    finally:
        await agent.leave_network()


if __name__ == "__main__":
    asyncio.run(main())
