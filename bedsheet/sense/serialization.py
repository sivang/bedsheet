"""Compact JSON serialization for signals.

PubNub has a 32KB message limit. We use short keys to minimize payload size
and truncate if necessary.
"""
import json
from typing import Any

from bedsheet.sense.signals import Signal


# Short keys for compact serialization
_KEY_MAP = {
    "kind": "k",
    "sender": "s",
    "payload": "p",
    "correlation_id": "c",
    "target": "t",
    "timestamp": "ts",
}

_REVERSE_KEY_MAP = {v: k for k, v in _KEY_MAP.items()}

MAX_MESSAGE_BYTES = 30_000  # Leave headroom under PubNub's 32KB limit


def serialize(signal: Signal) -> dict[str, Any]:
    """Serialize a Signal to a compact dict for transmission."""
    data: dict[str, Any] = {
        "k": signal.kind,
        "s": signal.sender,
        "ts": signal.timestamp,
    }

    if signal.payload:
        data["p"] = signal.payload
    if signal.correlation_id:
        data["c"] = signal.correlation_id
    if signal.target:
        data["t"] = signal.target

    # Check size and truncate payload if needed
    encoded = json.dumps(data)
    if len(encoded.encode("utf-8")) > MAX_MESSAGE_BYTES:
        data["p"] = {"_truncated": True, "summary": str(signal.payload)[:500]}

    return data


def deserialize(data: dict[str, Any], source_channel: str | None = None) -> Signal:
    """Deserialize a compact dict back into a Signal."""
    return Signal(
        kind=data["k"],
        sender=data["s"],
        payload=data.get("p", {}),
        correlation_id=data.get("c", ""),
        target=data.get("t"),
        timestamp=data.get("ts", 0.0),
        source_channel=source_channel,
    )
