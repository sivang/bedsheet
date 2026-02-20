"""Sentinel Commander — supervisor that orchestrates all agents."""

from bedsheet import ActionGroup, Supervisor

from agents.sentinels import behavior_sentinel, supply_chain_sentinel
from agents.workers import skill_acquirer, web_researcher

commander_tools = ActionGroup("commander_tools", "Incident response tools")


@commander_tools.action(
    "issue_quarantine",
    "Issue a quarantine order for a compromised agent",
    parameters={
        "type": "object",
        "properties": {
            "agent_name": {"type": "string", "description": "Agent to quarantine"},
            "reason": {"type": "string", "description": "Reason for quarantine"},
        },
        "required": ["agent_name", "reason"],
    },
)
async def issue_quarantine(agent_name: str, reason: str) -> str:
    return (
        f"QUARANTINE ORDER ISSUED: {agent_name} has been isolated.\n"
        f"Reason: {reason}\n"
        f"All network access revoked. Incident logged for review."
    )


@commander_tools.action(
    "correlate_alerts",
    "Correlate alerts from multiple sentinels into a unified incident report",
    parameters={
        "type": "object",
        "properties": {
            "alerts": {
                "type": "string",
                "description": "Comma-separated list of alert descriptions from sentinels",
            }
        },
        "required": ["alerts"],
    },
)
async def correlate_alerts(alerts: str) -> str:
    alert_list = [a.strip() for a in alerts.split(",") if a.strip()]
    critical = [a for a in alert_list if "CRITICAL" in a.upper()]
    warnings = [a for a in alert_list if "WARN" in a.upper() or "ALERT" in a.upper()]

    if critical:
        severity = "CRITICAL"
        action = "Immediate quarantine and investigation required."
    elif warnings:
        severity = "WARNING"
        action = "Elevated monitoring. Prepare containment if escalates."
    else:
        severity = "OK"
        action = "No action required. Continue routine monitoring."

    return (
        f"Incident Severity: {severity}\n"
        f"Critical alerts: {len(critical)}\n"
        f"Warnings: {len(warnings)}\n"
        f"Recommended action: {action}"
    )


class _SentinelCommander(Supervisor):
    pass


# Named to match class_name in bedsheet.yaml so the CLI detects it as an instance
SentinelCommander = _SentinelCommander(
    name="sentinel-commander",
    instruction=(
        "You are the Sentinel Commander, coordinating AI agent security monitoring. "
        "You have 4 sub-agents: web-researcher (worker), skill-acquirer (worker), "
        "behavior-sentinel (monitors request rates), supply-chain-sentinel (checks installed skills). "
        "\n\n"
        "Your mission when invoked:\n"
        "1. Delegate to all 4 sub-agents in parallel to assess the current state\n"
        "2. Use correlate_alerts to unify their findings\n"
        "3. If any CRITICAL issues found, use issue_quarantine on the compromised agent\n"
        "4. Produce a concise security situation report\n\n"
        "Be decisive. Agent security threats require immediate response."
    ),
    collaborators=[
        web_researcher,
        skill_acquirer,
        behavior_sentinel,
        supply_chain_sentinel,
    ],
)
SentinelCommander.add_action_group(commander_tools)

agent = SentinelCommander
