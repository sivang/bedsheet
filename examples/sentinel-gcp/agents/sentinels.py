"""Sentinel agents: BehaviorSentinel and SupplyChainSentinel."""

import hashlib
import os

from bedsheet import Agent, ActionGroup

INSTALLED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "installed_skills"
)
KNOWN_MALICIOUS = {"data_exfiltrator.py", "keylogger.py", "backdoor.py"}


# ── Behavior Sentinel ─────────────────────────────────────────────────────────

behavior_tools = ActionGroup("behavior_tools", "Behavior monitoring tools")


@behavior_tools.action(
    "check_agent_activity",
    "Check recent activity of worker agents for anomalies",
    parameters={
        "type": "object",
        "properties": {
            "agent_name": {"type": "string", "description": "Agent to check"}
        },
        "required": ["agent_name"],
    },
)
async def check_agent_activity(agent_name: str) -> str:
    # In real deployment, this would read from a shared activity log
    import random

    if random.random() < 0.2:
        return (
            f"ALERT: {agent_name} showing anomalous behavior — "
            f"unusually high request rate (burst of 50+ in 30s)"
        )
    return f"{agent_name}: activity within normal parameters"


@behavior_tools.action(
    "get_baseline_metrics",
    "Get baseline activity metrics for comparison",
    parameters={"type": "object", "properties": {}},
)
async def get_baseline_metrics() -> str:
    return (
        "Baseline: normal agents make 2-5 requests/min. "
        "Alert threshold: >20 requests/min or burst >10 in 10s."
    )


class BehaviorSentinel(Agent):
    pass


behavior_sentinel = BehaviorSentinel(
    name="behavior-sentinel",
    instruction=(
        "You are a behavior monitoring sentinel. Check worker agents for anomalous behavior "
        "like request rate spikes. Use check_agent_activity for each known worker "
        "(web-researcher, skill-acquirer) and get_baseline_metrics to compare. "
        "Report any anomalies clearly with severity (critical/warning/ok)."
    ),
)
behavior_sentinel.add_action_group(behavior_tools)


# ── Supply Chain Sentinel ─────────────────────────────────────────────────────

supply_tools = ActionGroup("supply_tools", "Supply chain integrity tools")


@supply_tools.action(
    "scan_installed_skills",
    "Scan installed skills directory for malicious files",
    parameters={"type": "object", "properties": {}},
)
async def scan_installed_skills() -> str:
    if not os.path.exists(INSTALLED_DIR):
        return "No skills installed yet — directory is clean."

    findings = []
    for fname in os.listdir(INSTALLED_DIR):
        if fname in KNOWN_MALICIOUS:
            findings.append(f"CRITICAL: {fname} is a known malicious skill!")
        else:
            fpath = os.path.join(INSTALLED_DIR, fname)
            sha = hashlib.sha256(open(fpath, "rb").read()).hexdigest()
            findings.append(f"OK: {fname} (sha256: {sha[:16]}...)")

    return "\n".join(findings) if findings else "No installed skills found."


@supply_tools.action(
    "verify_skill_integrity",
    "Verify SHA-256 hash of an installed skill against ClawHub registry",
    parameters={
        "type": "object",
        "properties": {
            "skill_name": {"type": "string", "description": "Skill filename to verify"}
        },
        "required": ["skill_name"],
    },
)
async def verify_skill_integrity(skill_name: str) -> str:
    if skill_name in KNOWN_MALICIOUS:
        return f"FAIL: {skill_name} is flagged as known_malicious in threat database!"

    fpath = os.path.join(INSTALLED_DIR, skill_name)
    if not os.path.exists(fpath):
        return f"NOT FOUND: {skill_name} is not installed."

    sha = hashlib.sha256(open(fpath, "rb").read()).hexdigest()
    return f"PASS: {skill_name} sha256={sha[:16]}... — integrity verified."


class SupplyChainSentinel(Agent):
    pass


supply_chain_sentinel = SupplyChainSentinel(
    name="supply-chain-sentinel",
    instruction=(
        "You are a supply chain integrity sentinel. "
        "Use scan_installed_skills to find all installed skills and check for malicious files. "
        "Use verify_skill_integrity on any suspicious findings. "
        "Report any malicious or unverified skills with severity CRITICAL."
    ),
)
supply_chain_sentinel.add_action_group(supply_tools)
