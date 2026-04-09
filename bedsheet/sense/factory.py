"""Factory for creating SenseTransport instances from environment variables.

Mirrors `bedsheet/llm/factory.py` — agent code calls `make_sense_transport()`
and never imports a specific transport class. This is what makes the sense
layer transport-agnostic in practice (the protocol always was, but examples
that hard-imported PubNubTransport coupled the example layer to one impl).

Selection priority:
  BEDSHEET_TRANSPORT=mock                       -> MockSenseTransport
  BEDSHEET_TRANSPORT=pubnub  + PUBNUB_*_KEY     -> PubNubTransport
  PUBNUB_SUBSCRIBE_KEY + PUBNUB_PUBLISH_KEY     -> PubNubTransport (back-compat)
  (nothing set)                                 -> MockSenseTransport (safe default)

Future transports (NATS, Redis pub/sub, in-process ZMQ) plug in as
additional `BEDSHEET_TRANSPORT=...` branches without touching agent code.

The PubNub branch lazily imports `bedsheet.sense.pubnub_transport` so this
module is safe to import on systems that don't have the `pubnub` package
installed (i.e. anyone who hasn't installed `bedsheet[sense]`).
"""

from __future__ import annotations

import os

from bedsheet.sense.protocol import SenseTransport


def make_sense_transport() -> SenseTransport:
    """Return a SenseTransport based on environment configuration.

    Raises RuntimeError if the requested transport is unknown or its
    required configuration is missing. Falls back to MockSenseTransport
    when nothing is configured (so local dev and tests work without
    any setup).
    """
    explicit = os.environ.get("BEDSHEET_TRANSPORT", "").strip().lower()

    if explicit == "mock":
        return _make_mock()

    if explicit == "pubnub":
        return _make_pubnub_or_raise()

    if explicit:
        raise RuntimeError(
            f"Unknown BEDSHEET_TRANSPORT='{explicit}'. "
            "Supported values: 'mock', 'pubnub'."
        )

    # No explicit transport — back-compat: if PubNub keys are set, assume
    # the user wants PubNub. Otherwise fall back to a hub-less Mock so
    # local development just works.
    if os.environ.get("PUBNUB_SUBSCRIBE_KEY") and os.environ.get("PUBNUB_PUBLISH_KEY"):
        return _make_pubnub_or_raise()

    return _make_mock()


def _make_mock() -> SenseTransport:
    # Lazy import to avoid pulling test utilities into the import graph for
    # callers that explicitly want a real transport.
    from bedsheet.testing import MockSenseTransport

    return MockSenseTransport()


def _make_pubnub_or_raise() -> SenseTransport:
    sub = os.environ.get("PUBNUB_SUBSCRIBE_KEY")
    pub = os.environ.get("PUBNUB_PUBLISH_KEY")
    if not sub or not pub:
        missing = []
        if not sub:
            missing.append("PUBNUB_SUBSCRIBE_KEY")
        if not pub:
            missing.append("PUBNUB_PUBLISH_KEY")
        raise RuntimeError(
            f"BEDSHEET_TRANSPORT=pubnub requires {', '.join(missing)}. "
            "Either set the keys or pick a different transport (e.g. "
            "BEDSHEET_TRANSPORT=mock for local development)."
        )

    # Lazy import so importing this factory doesn't drag in the `pubnub`
    # package for users who don't have `bedsheet[sense]` installed.
    from bedsheet.sense.pubnub_transport import PubNubTransport

    return PubNubTransport(
        subscribe_key=sub,
        publish_key=pub,
        secret_key=os.environ.get("PUBNUB_SECRET_KEY"),
    )
