"""Tests for the Agent Sentinel Action Gateway.

The gateway is example code (lives under examples/agent-sentinel/middleware/),
but it's the security trust boundary that the Agent Sentinel demo's entire
narrative depends on. Untested gateway = untested security claims.

This file focuses on the small set of behaviors that block any v0.5 release of
the sentinel demo:
- ToolExecutor must NOT swallow exceptions and return them as success strings
  (B3 regression — the bug had the audit ledger logging "approved" for
  executions that actually raised)
- ActionLedger.agent_stats must compute per-agent rates correctly
- Per-agent rate limiting must be per-agent, not global
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

# Make `examples/agent-sentinel/middleware/action_gateway.py` importable.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_GATEWAY_DIR = _REPO_ROOT / "examples" / "agent-sentinel"
sys.path.insert(0, str(_GATEWAY_DIR))

from middleware.action_gateway import (  # noqa: E402
    ActionLedger,
    ActionRecord,
    AnomalyDetector,
    ToolExecutor,
)


# ---------- ToolExecutor error handling (B3 regression) ----------


@pytest.mark.asyncio
async def test_tool_executor_propagates_handler_exceptions():
    """REGRESSION TEST for B3: ToolExecutor.execute() used to catch every
    exception and return it as a string ("Execution error: ..."). The caller
    then logged that string to the audit ledger as if it were a successful
    result with verdict='approved' — the audit log lied about what happened.

    Fix: handler exceptions must propagate so the caller can record an
    explicit error verdict instead of forging an approval.
    """
    executor = ToolExecutor()

    # Inject a handler that raises
    async def boom(params: dict) -> str:
        raise RuntimeError("disk on fire")

    executor._do_boom = boom  # type: ignore[attr-defined]

    with pytest.raises(RuntimeError, match="disk on fire"):
        await executor.execute("boom", {})


@pytest.mark.asyncio
async def test_tool_executor_unknown_action_raises():
    """Unknown actions must raise (or use a sentinel error verdict) — they
    must not silently return a success-shaped string."""
    executor = ToolExecutor()
    with pytest.raises((ValueError, KeyError, AttributeError)):
        await executor.execute("nonexistent_action", {})


# ---------- ActionLedger basics ----------


def test_ledger_append_and_query():
    ledger = ActionLedger(max_age_seconds=600.0)
    record = ActionRecord(
        timestamp=time.time(),
        agent="agent-a",
        action="search_web",
        params={"q": "test"},
        verdict="approved",
    )
    ledger.append(record)
    results = ledger.query(minutes=10)
    assert len(results) == 1
    assert results[0].agent == "agent-a"


def test_ledger_prunes_old_records():
    """Records older than max_age must be evicted on query/append."""
    ledger = ActionLedger(max_age_seconds=1.0)  # 1 second window
    old = ActionRecord(
        timestamp=time.time() - 5.0,  # 5 seconds ago
        agent="agent-a",
        action="x",
        params={},
        verdict="approved",
    )
    fresh = ActionRecord(
        timestamp=time.time(),
        agent="agent-a",
        action="y",
        params={},
        verdict="approved",
    )
    ledger.append(old)
    ledger.append(fresh)
    results = ledger.query(minutes=10)
    # Old record should have been pruned by append's _prune call
    assert len(results) == 1
    assert results[0].action == "y"


def test_ledger_agent_stats_per_agent():
    """agent_stats must compute counts and rates per-agent, not globally.
    This pins the invariant called out in the security architecture docs:
    rate limiting is per-agent so a noisy peer can't starve a quiet one."""
    ledger = ActionLedger(max_age_seconds=600.0)
    now = time.time()
    for _ in range(5):
        ledger.append(
            ActionRecord(
                timestamp=now,
                agent="agent-a",
                action="x",
                params={},
                verdict="approved",
            )
        )
    for _ in range(2):
        ledger.append(
            ActionRecord(
                timestamp=now,
                agent="agent-b",
                action="y",
                params={},
                verdict="approved",
            )
        )
    ledger.append(
        ActionRecord(
            timestamp=now, agent="agent-b", action="y", params={}, verdict="denied"
        )
    )

    stats = ledger.agent_stats(minutes=1)
    assert stats["agent-a"]["count"] == 5
    assert stats["agent-a"]["approved"] == 5
    assert stats["agent-a"]["denied"] == 0
    assert stats["agent-b"]["count"] == 3
    assert stats["agent-b"]["approved"] == 2
    assert stats["agent-b"]["denied"] == 1


def test_anomaly_detector_rate_limit_is_per_agent():
    """The anomaly detector's rate limit must be applied per-agent, so one
    chatty agent can't push another agent over the threshold. This was
    explicitly called out as an invariant in the security architecture."""
    from middleware.action_gateway import _RATE_LIMIT  # noqa: E402

    ledger = ActionLedger(max_age_seconds=600.0)
    detector = AnomalyDetector()

    now = time.time()
    # Saturate agent-a up to the rate limit
    for _ in range(_RATE_LIMIT):
        ledger.append(
            ActionRecord(
                timestamp=now,
                agent="agent-a",
                action="search_web",
                params={"query": "ok"},
                verdict="approved",
            )
        )

    # agent-a's NEXT request should be rate-limited
    verdict_a, reason_a = detector.evaluate(
        "agent-a", "search_web", {"query": "ok"}, ledger
    )
    assert verdict_a == "rate_limited", reason_a

    # But agent-b's first request must not be affected by agent-a's history
    verdict_b, _ = detector.evaluate("agent-b", "search_web", {"query": "ok"}, ledger)
    assert verdict_b == "approved"
