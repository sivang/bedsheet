"""Action Gateway — tamper-proof tool execution layer.

A standalone asyncio process (NOT a Bedsheet agent) that owns all tool
execution for the Sentinel Network. Workers send tool requests over PubNub;
the gateway validates, executes, logs to an append-only ledger, and responds.

A poisoned agent literally cannot search, install skills, or modify the
calendar — those capabilities only exist inside this process.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from collections import deque
from dataclasses import dataclass

from bedsheet.sense import Signal, SenseTransport, make_sense_transport

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "data")
_CLAWHUB_DIR = os.path.join(_BASE_DIR, "clawhub")
_INSTALLED_DIR = os.path.join(_DATA_DIR, "installed_skills")
_CALENDAR_PATH = os.path.join(_DATA_DIR, "calendar.json")
_REGISTRY_PATH = os.path.join(_CLAWHUB_DIR, "registry.json")


# ── ActionRecord & Ledger ──────────────────────────────────────────────


@dataclass
class ActionRecord:
    timestamp: float
    agent: str
    action: str
    params: dict
    verdict: str  # "approved", "denied", "rate_limited", "error"
    reason: str = ""
    result_summary: str = ""


class ActionLedger:
    """Append-only, time-windowed action log. Auto-prunes records >10 min old."""

    def __init__(self, max_age_seconds: float = 600.0) -> None:
        self._records: deque[ActionRecord] = deque()
        self._max_age = max_age_seconds

    def append(self, record: ActionRecord) -> None:
        self._prune()
        self._records.append(record)

    def query(self, minutes: float) -> list[ActionRecord]:
        self._prune()
        cutoff = time.time() - (minutes * 60)
        return [r for r in self._records if r.timestamp >= cutoff]

    def agent_stats(self, minutes: float) -> dict[str, dict]:
        records = self.query(minutes)
        stats: dict[str, dict] = {}
        for r in records:
            if r.agent not in stats:
                stats[r.agent] = {"count": 0, "denied": 0, "approved": 0}
            stats[r.agent]["count"] += 1
            if r.verdict == "approved":
                stats[r.agent]["approved"] += 1
            else:
                stats[r.agent]["denied"] += 1
        for agent, s in stats.items():
            s["rate"] = round(s["count"] / minutes, 1) if minutes > 0 else 0
        return stats

    def agent_log(self, agent: str, minutes: float) -> list[dict]:
        records = self.query(minutes)
        return [
            {
                "timestamp": r.timestamp,
                "action": r.action,
                "verdict": r.verdict,
                "reason": r.reason,
            }
            for r in records
            if r.agent == agent
        ]

    def _prune(self) -> None:
        cutoff = time.time() - self._max_age
        while self._records and self._records[0].timestamp < cutoff:
            self._records.popleft()


# ── Anomaly Detector ───────────────────────────────────────────────────

_SUSPICIOUS_KEYWORDS = {
    "password",
    "exploit",
    "bypass",
    "credential",
    "dump",
    "exfiltrat",
    "inject",
    "hack",
    "leaked",
    "pastebin",
}

_RATE_LIMIT = 10  # actions per minute per agent


class AnomalyDetector:
    """Stateless evaluator. Checks rate limits and suspicious patterns."""

    def evaluate(
        self, agent: str, action: str, params: dict, ledger: ActionLedger
    ) -> tuple[str, str]:
        """Returns (verdict, reason). verdict is 'approved', 'denied', or 'rate_limited'."""
        # Rate limit check
        recent = ledger.query(minutes=1)
        agent_count = sum(1 for r in recent if r.agent == agent)
        if agent_count >= _RATE_LIMIT:
            return (
                "rate_limited",
                f"Rate exceeded: {agent_count} actions in last 1min (limit {_RATE_LIMIT})",
            )

        # Suspicious keyword check
        param_str = json.dumps(params).lower()
        for keyword in _SUSPICIOUS_KEYWORDS:
            if keyword in param_str:
                return "denied", f"Suspicious parameter content: '{keyword}'"

        return "approved", ""


# ── Tool Executor ──────────────────────────────────────────────────────


class ToolExecutor:
    """Holds the actual tool implementations that moved out of workers."""

    def __init__(self) -> None:
        self._search_count = 0

    async def execute(self, action: str, params: dict) -> str:
        """Execute an action handler. Raises on unknown action or handler error.

        IMPORTANT: this used to catch all exceptions and return them as result
        strings, which made the audit ledger log failed executions as
        verdict='approved'. Errors must propagate so the caller can record an
        explicit 'error' verdict.
        """
        handler = getattr(self, f"_do_{action}", None)
        if handler is None:
            raise ValueError(f"Unknown action: {action}")
        return await handler(params)

    # ── Web search ──

    async def _do_search_web(self, params: dict) -> str:
        query = params.get("query", "")
        from ddgs import DDGS

        ddgs = DDGS()
        results = ddgs.text(query, max_results=3)
        self._search_count += 1
        if not results:
            return f"No results for '{query}'"
        lines = []
        for r in results:
            lines.append(f"- {r['title']}: {r['body'][:120]}")
        return f"Results for '{query}':\n" + "\n".join(lines)

    async def _do_get_search_summary(self, params: dict) -> str:
        return f"Total searches this session: {self._search_count}"

    # ── Calendar ──

    def _read_calendar(self) -> list[dict]:
        try:
            with open(_CALENDAR_PATH) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write_calendar(self, appointments: list[dict]) -> None:
        with open(_CALENDAR_PATH, "w") as f:
            json.dump(appointments, f, indent=2)

    async def _do_list_appointments(self, params: dict) -> str:
        appointments = self._read_calendar()
        if not appointments:
            return "No appointments scheduled."
        lines = []
        for apt in appointments:
            lines.append(
                f"  [{apt['id']}] {apt['title']} - {apt['date']} at {apt['time']}"
            )
        return f"Appointments ({len(appointments)}):\n" + "\n".join(lines)

    async def _do_add_appointment(self, params: dict) -> str:
        title = params.get("title", "Untitled")
        date = params.get("date", "TBD")
        time_str = params.get("time", "09:00")
        appointments = self._read_calendar()
        new_apt = {
            "id": f"apt-{uuid.uuid4().hex[:6]}",
            "title": title,
            "date": date,
            "time": time_str,
        }
        appointments.append(new_apt)
        self._write_calendar(appointments)
        return f"Added: {title} on {date} at {time_str}"

    async def _do_delete_appointment(self, params: dict) -> str:
        appointment_id = params.get("appointment_id", "")
        appointments = self._read_calendar()
        before = len(appointments)
        appointments = [a for a in appointments if a["id"] != appointment_id]
        self._write_calendar(appointments)
        removed = before - len(appointments)
        if removed:
            return f"Deleted appointment {appointment_id}"
        return f"No appointment found with ID {appointment_id}"

    # ── Skill management ──

    def _load_registry(self) -> dict:
        with open(_REGISTRY_PATH) as f:
            return json.load(f)

    def _sha256(self, path: str) -> str:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()

    async def _do_list_available_skills(self, params: dict) -> str:
        registry = self._load_registry()
        lines = []
        for name, info in registry.items():
            status = "MALICIOUS" if info.get("malicious") else "safe"
            lines.append(f"  {name}: {info['description']} [{status}]")
        return f"Available skills ({len(registry)}):\n" + "\n".join(lines)

    async def _do_install_skill(self, params: dict) -> str:
        skill_name = params.get("skill_name", "")
        registry = self._load_registry()

        if skill_name not in registry:
            return f"Skill '{skill_name}' not found in ClawHub registry"

        info = registry[skill_name]
        if info.get("malicious"):
            return f"BLOCKED: '{skill_name}' is flagged as malicious in the registry"

        source = os.path.join(_CLAWHUB_DIR, skill_name)
        if not os.path.exists(source):
            return f"Skill file '{skill_name}' not found in ClawHub directory"

        actual_hash = self._sha256(source)
        expected_hash = info["sha256"]
        if actual_hash != expected_hash:
            return (
                f"INTEGRITY ERROR: {skill_name} hash mismatch "
                f"(expected {expected_hash[:12]}..., got {actual_hash[:12]}...)"
            )

        # Read the file content — we return it to the agent, who writes it
        with open(source) as f:
            content = f.read()

        return json.dumps(
            {
                "installed": True,
                "skill_name": skill_name,
                "sha256": actual_hash[:12],
                "content": content,
            }
        )

    async def _do_list_installed_skills(self, params: dict) -> str:
        if not os.path.exists(_INSTALLED_DIR):
            return "No skills installed yet."
        files = [f for f in os.listdir(_INSTALLED_DIR) if f.endswith(".py")]
        if not files:
            return "No skills installed yet."
        registry = self._load_registry()
        lines = []
        for f in sorted(files):
            path = os.path.join(_INSTALLED_DIR, f)
            h = self._sha256(path)
            info = registry.get(f, {})
            expected = info.get("sha256", "unknown")
            match = "OK" if h == expected else "MISMATCH"
            malicious = " [MALICIOUS]" if info.get("malicious") else ""
            lines.append(f"  {f}: {h[:16]}... ({match}){malicious}")
        return f"Installed skills ({len(files)}):\n" + "\n".join(lines)


# ── Action Gateway ─────────────────────────────────────────────────────


class ActionGateway:
    """Main gateway process. PubNub listener + processor loop.

    Subscribes to its own channel, receives tool requests from workers,
    validates with AnomalyDetector, executes with ToolExecutor, logs to
    ActionLedger, and responds.
    """

    GATEWAY_NAME = "action-gateway"

    def __init__(self, transport: SenseTransport) -> None:
        self._transport = transport
        self._ledger = ActionLedger()
        self._detector = AnomalyDetector()
        self._executor = ToolExecutor()
        self._denial_counts: dict[str, list[float]] = {}  # agent -> denial timestamps
        self._quarantined: set[str] = set()  # agents revoked from gateway access

    async def start(self) -> None:
        await self._transport.connect(self.GATEWAY_NAME, "agent-sentinel")
        await self._transport.subscribe(self.GATEWAY_NAME)
        await self._transport.subscribe("alerts")
        await self._transport.subscribe("quarantine")
        print(f"[{self.GATEWAY_NAME}] Online — owning all tool execution")

        async for signal in self._transport.signals():
            if signal.sender == self.GATEWAY_NAME:
                continue
            # Let broadcast signals through (quarantine alerts have no target)
            if signal.target and signal.target != self.GATEWAY_NAME:
                continue
            try:
                await self._handle_signal(signal)
            except Exception:
                logger.exception("Error handling signal from %s", signal.sender)

    async def _handle_signal(self, signal: Signal) -> None:
        # Handle quarantine orders from the commander
        if signal.kind == "alert" and signal.payload.get("action") == "quarantine":
            agent_name = signal.payload.get("agent", "")
            if agent_name and agent_name != self.GATEWAY_NAME:
                self._quarantined.add(agent_name)
                print(
                    f"[{self.GATEWAY_NAME}] QUARANTINE ENFORCED: "
                    f"'{agent_name}' revoked from gateway access"
                )
            return

        if signal.kind != "request":
            return

        payload = signal.payload
        msg_type = payload.get("type", "action_request")

        if msg_type == "query_rates":
            await self._handle_query_rates(signal)
        elif msg_type == "query_agent_log":
            await self._handle_query_agent_log(signal)
        else:
            await self._handle_action_request(signal)

    async def _handle_action_request(self, signal: Signal) -> None:
        action = signal.payload.get("action", "")
        params = signal.payload.get("params", {})
        agent = signal.sender

        # Quarantine check — hard deny, no exceptions
        if agent in self._quarantined:
            verdict, reason = "denied", f"Agent '{agent}' is quarantined"
            record = ActionRecord(
                timestamp=time.time(),
                agent=agent,
                action=action,
                params=params,
                verdict=verdict,
                reason=reason,
            )
            self._ledger.append(record)
            response = Signal(
                kind="response",
                sender=self.GATEWAY_NAME,
                target=agent,
                correlation_id=signal.correlation_id,
                payload={"verdict": verdict, "result": "", "reason": reason, "rate": 0},
            )
            await self._transport.broadcast(agent, response)
            print(f"[{self.GATEWAY_NAME}] {agent}/{action} -> QUARANTINED")
            return

        # Evaluate
        verdict, reason = self._detector.evaluate(agent, action, params, self._ledger)

        result = ""
        if verdict == "approved":
            try:
                result = await self._executor.execute(action, params)
            except Exception as exc:
                # Execution failed AFTER passing the security gate. The audit
                # ledger must reflect that this action did NOT successfully
                # complete — recording it as "approved" would mean the audit
                # log lies about what actually happened in the system.
                logger.exception("Execution failed for %s/%s", agent, action)
                verdict = "error"
                reason = f"Execution error: {exc}"
                result = ""

        # Log to ledger
        record = ActionRecord(
            timestamp=time.time(),
            agent=agent,
            action=action,
            params=params,
            verdict=verdict,
            reason=reason,
            result_summary=result[:200] if result else "",
        )
        self._ledger.append(record)

        # Track denials for escalation
        if verdict != "approved":
            self._track_denial(agent)

        # Compute current rate for the response
        stats = self._ledger.agent_stats(minutes=1)
        agent_rate = stats.get(agent, {}).get("rate", 0)

        # Respond
        response = Signal(
            kind="response",
            sender=self.GATEWAY_NAME,
            target=signal.sender,
            correlation_id=signal.correlation_id,
            payload={
                "verdict": verdict,
                "result": result,
                "reason": reason,
                "rate": agent_rate,
            },
        )
        await self._transport.broadcast(signal.sender, response)

        status = f"{verdict}" + (f" ({reason})" if reason else "")
        print(f"[{self.GATEWAY_NAME}] {agent}/{action} -> {status}")

    def _track_denial(self, agent: str) -> None:
        """Track denials and escalate if threshold exceeded."""
        now = time.time()
        if agent not in self._denial_counts:
            self._denial_counts[agent] = []
        self._denial_counts[agent].append(now)
        # Prune older than 1 minute
        cutoff = now - 60
        self._denial_counts[agent] = [
            t for t in self._denial_counts[agent] if t >= cutoff
        ]
        count = len(self._denial_counts[agent])
        if count >= 5:
            asyncio.create_task(self._escalate_denial(agent, count))

    async def _escalate_denial(self, agent: str, denied_count: int) -> None:
        alert = Signal(
            kind="alert",
            sender=self.GATEWAY_NAME,
            payload={
                "severity": "critical",
                "category": "gateway_enforcement",
                "agent": agent,
                "denied_count": denied_count,
                "message": (
                    f"Agent '{agent}' blocked: {denied_count} denied requests in 1min"
                ),
            },
        )
        await self._transport.broadcast("alerts", alert)
        print(f"[{self.GATEWAY_NAME}] ALERT: {agent} — {denied_count} denials in 1min")

    async def _handle_query_rates(self, signal: Signal) -> None:
        minutes = signal.payload.get("minutes", 2)
        stats = self._ledger.agent_stats(minutes)
        total = sum(s["count"] for s in stats.values())

        response = Signal(
            kind="response",
            sender=self.GATEWAY_NAME,
            target=signal.sender,
            correlation_id=signal.correlation_id,
            payload={
                "type": "rate_stats",
                "window_minutes": minutes,
                "total_actions": total,
                "agents": stats,
            },
        )
        await self._transport.broadcast(signal.sender, response)

    async def _handle_query_agent_log(self, signal: Signal) -> None:
        agent = signal.payload.get("agent", "")
        minutes = signal.payload.get("minutes", 5)
        records = self._ledger.agent_log(agent, minutes)

        response = Signal(
            kind="response",
            sender=self.GATEWAY_NAME,
            target=signal.sender,
            correlation_id=signal.correlation_id,
            payload={
                "type": "agent_log",
                "agent": agent,
                "records": records,
            },
        )
        await self._transport.broadcast(signal.sender, response)


# ── Entrypoint ─────────────────────────────────────────────────────────


async def main():
    # Transport selection happens at the framework layer, not here. Set
    # BEDSHEET_TRANSPORT (and PUBNUB_* keys, if applicable) in the
    # environment to choose. Defaults to MockSenseTransport for local dev.
    transport = make_sense_transport()
    gateway = ActionGateway(transport)
    try:
        await gateway.start()
    except KeyboardInterrupt:
        pass
    finally:
        await transport.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
