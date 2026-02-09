"""Supply Chain Sentinel - verifies installed skill integrity via SHA-256.

Scans data/installed_skills/ and compares file hashes against the ClawHub
registry. Detects hash mismatches and known-malicious skill installations.
"""

import asyncio
import hashlib
import json
import os

from bedsheet import Agent, ActionGroup, SenseMixin
from bedsheet.llm.anthropic import AnthropicClient
from bedsheet.sense import Signal
from bedsheet.sense.pubnub_transport import PubNubTransport


class SupplyChainSentinel(SenseMixin, Agent):
    pass


supply_chain_tools = ActionGroup("supply_chain_tools", "Supply chain monitoring tools")

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_CLAWHUB_DIR = os.path.join(_BASE_DIR, "clawhub")
_DATA_DIR = os.path.join(_BASE_DIR, "data")
_INSTALLED_DIR = os.path.join(_DATA_DIR, "installed_skills")
_REGISTRY_PATH = os.path.join(_CLAWHUB_DIR, "registry.json")


def _load_registry() -> dict:
    with open(_REGISTRY_PATH) as f:
        return json.load(f)


def _sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


@supply_chain_tools.action(
    "audit_installed_skills", "Audit all installed skills against the ClawHub registry"
)
async def audit_installed_skills() -> str:
    if not os.path.exists(_INSTALLED_DIR):
        return "No skills installed yet — nothing to audit."

    registry = _load_registry()
    files = [f for f in os.listdir(_INSTALLED_DIR) if f.endswith(".py")]
    if not files:
        return "No skills installed yet — nothing to audit."

    issues = []
    clean = []
    for f in sorted(files):
        path = os.path.join(_INSTALLED_DIR, f)
        actual_hash = _sha256(path)
        info = registry.get(f)

        if info is None:
            issues.append(f"  {f}: NOT IN REGISTRY (unknown origin)")
            continue

        if info.get("malicious"):
            issues.append(f"  {f}: KNOWN MALICIOUS (flagged in registry)")
            continue

        expected_hash = info["sha256"]
        if actual_hash != expected_hash:
            issues.append(
                f"  {f}: HASH MISMATCH (expected {expected_hash[:12]}..., got {actual_hash[:12]}...)"
            )
        else:
            clean.append(f"  {f}: OK (hash verified)")

    lines = [f"Audit of {len(files)} installed skills:"]
    if issues:
        lines.append(f"\nISSUES ({len(issues)}):")
        lines.extend(issues)
    if clean:
        lines.append(f"\nCLEAN ({len(clean)}):")
        lines.extend(clean)
    return "\n".join(lines)


@supply_chain_tools.action(
    "check_known_malicious", "Check if any installed skill is flagged as malicious"
)
async def check_known_malicious() -> str:
    if not os.path.exists(_INSTALLED_DIR):
        return "No skills installed."

    registry = _load_registry()
    files = [f for f in os.listdir(_INSTALLED_DIR) if f.endswith(".py")]
    malicious = [f for f in files if registry.get(f, {}).get("malicious")]

    if not malicious:
        return "No known-malicious skills installed."
    return (
        f"ALERT: {len(malicious)} malicious skill(s) installed: {', '.join(malicious)}"
    )


@supply_chain_tools.action(
    "verify_skill_integrity",
    "Verify a specific installed skill's hash against the registry",
    parameters={
        "type": "object",
        "properties": {
            "skill_name": {"type": "string", "description": "Skill filename to verify"},
        },
        "required": ["skill_name"],
    },
)
async def verify_skill_integrity(skill_name: str) -> str:
    path = os.path.join(_INSTALLED_DIR, skill_name)
    if not os.path.exists(path):
        return f"Skill '{skill_name}' is not installed."

    registry = _load_registry()
    info = registry.get(skill_name)
    if not info:
        return f"Skill '{skill_name}' is not in the registry (unknown origin)."

    actual_hash = _sha256(path)
    if info.get("malicious"):
        return f"CRITICAL: '{skill_name}' is a KNOWN MALICIOUS skill (hash: {actual_hash[:16]}...)"

    expected = info["sha256"]
    if actual_hash == expected:
        return f"'{skill_name}': integrity verified (SHA-256 match)"
    return f"'{skill_name}': INTEGRITY FAILURE (expected {expected[:16]}..., got {actual_hash[:16]}...)"


def _scan_for_issues() -> list[dict]:
    """Scan installed skills and return a list of issues found."""
    if not os.path.exists(_INSTALLED_DIR):
        return []

    registry = _load_registry()
    files = [f for f in os.listdir(_INSTALLED_DIR) if f.endswith(".py")]
    issues = []

    for f in files:
        path = os.path.join(_INSTALLED_DIR, f)
        actual_hash = _sha256(path)
        info = registry.get(f)

        if info is None:
            issues.append({"skill": f, "type": "unknown_origin", "hash": actual_hash})
        elif info.get("malicious"):
            issues.append({"skill": f, "type": "known_malicious", "hash": actual_hash})
        elif actual_hash != info["sha256"]:
            issues.append(
                {
                    "skill": f,
                    "type": "hash_mismatch",
                    "hash": actual_hash,
                    "expected": info["sha256"],
                }
            )

    return issues


async def main():
    transport = PubNubTransport(
        subscribe_key=os.environ["PUBNUB_SUBSCRIBE_KEY"],
        publish_key=os.environ["PUBNUB_PUBLISH_KEY"],
    )

    agent = SupplyChainSentinel(
        name="supply-chain-sentinel",
        instruction=(
            "You are a supply chain security sentinel. You verify the integrity "
            "of installed skills by checking their SHA-256 hashes against the "
            "ClawHub registry. Report any mismatches or malicious installs."
        ),
        model_client=AnthropicClient(),
    )
    agent.add_action_group(supply_chain_tools)

    await agent.join_network(transport, "agent-sentinel", ["alerts", "quarantine"])
    print("[supply-chain-sentinel] Online and monitoring skill integrity...")

    try:
        while True:
            issues = _scan_for_issues()
            for issue in issues:
                severity = "critical" if issue["type"] == "known_malicious" else "high"
                print(
                    f"[supply-chain-sentinel] ALERT: {issue['type']} - {issue['skill']}"
                )
                alert = Signal(
                    kind="alert",
                    sender="supply-chain-sentinel",
                    payload={
                        "severity": severity,
                        "category": "supply_chain",
                        "issue_type": issue["type"],
                        "skill": issue["skill"],
                        "hash": issue["hash"],
                        "message": f"Supply chain issue: {issue['type']} for {issue['skill']}",
                    },
                )
                await agent.broadcast("alerts", alert)

            await asyncio.sleep(15)
    except KeyboardInterrupt:
        pass
    finally:
        await agent.leave_network()


if __name__ == "__main__":
    asyncio.run(main())
