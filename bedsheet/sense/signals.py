"""Signal types for inter-agent communication."""

from dataclasses import dataclass, field
from typing import Any, Literal
from time import time
from uuid import uuid4


SignalKind = Literal[
    "request",
    "response",
    "alert",
    "heartbeat",
    "claim",
    "release",
    "event",
]


@dataclass
class Signal:
    """A unit of inter-agent communication.

    Signals are the messages exchanged between agents over the sense network.
    Each signal has a kind, a sender, and an optional payload.
    """

    kind: SignalKind
    sender: str
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = field(default_factory=lambda: uuid4().hex[:12])
    target: str | None = None
    timestamp: float = field(default_factory=time)
    source_channel: str | None = None
