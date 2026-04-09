"""Tests for the sense transport factory.

Mirrors tests/test_llm_factory.py — locks in the env-var contract for
make_sense_transport() so a future refactor can't silently flip the default
transport or break the back-compat path that auto-detects PubNub keys.

The factory is the single source of truth for "which transport are we using
right now"; agent code calls make_sense_transport() and never imports
specific transport classes.
"""

from __future__ import annotations

import pytest


def _clear_sense_env(monkeypatch):
    monkeypatch.delenv("BEDSHEET_TRANSPORT", raising=False)
    monkeypatch.delenv("PUBNUB_SUBSCRIBE_KEY", raising=False)
    monkeypatch.delenv("PUBNUB_PUBLISH_KEY", raising=False)
    monkeypatch.delenv("PUBNUB_SECRET_KEY", raising=False)


def test_factory_returns_mock_transport_when_explicitly_requested(monkeypatch):
    _clear_sense_env(monkeypatch)
    monkeypatch.setenv("BEDSHEET_TRANSPORT", "mock")

    from bedsheet.sense.factory import make_sense_transport
    from bedsheet.testing import MockSenseTransport

    transport = make_sense_transport()
    assert isinstance(transport, MockSenseTransport)


def test_factory_returns_mock_when_no_other_config(monkeypatch):
    """With nothing configured, the factory falls back to MockSenseTransport
    so local development and tests work out of the box (mirrors the way
    MockLLMClient is the safe-no-API-key default in many of our tests)."""
    _clear_sense_env(monkeypatch)

    from bedsheet.sense.factory import make_sense_transport
    from bedsheet.testing import MockSenseTransport

    transport = make_sense_transport()
    assert isinstance(transport, MockSenseTransport)


def test_factory_picks_pubnub_when_keys_set(monkeypatch):
    """If PUBNUB_* keys are set without an explicit BEDSHEET_TRANSPORT, the
    factory must back-compat into PubNubTransport — this matches the behavior
    of every existing agent-sentinel script before the factory existed."""
    pytest.importorskip("pubnub", reason="PubNubTransport requires bedsheet[sense]")
    _clear_sense_env(monkeypatch)
    monkeypatch.setenv("PUBNUB_SUBSCRIBE_KEY", "sub-c-fake")
    monkeypatch.setenv("PUBNUB_PUBLISH_KEY", "pub-c-fake")

    from bedsheet.sense.factory import make_sense_transport
    from bedsheet.sense.pubnub_transport import PubNubTransport

    transport = make_sense_transport()
    assert isinstance(transport, PubNubTransport)


def test_factory_pubnub_explicit_with_keys(monkeypatch):
    pytest.importorskip("pubnub", reason="PubNubTransport requires bedsheet[sense]")
    _clear_sense_env(monkeypatch)
    monkeypatch.setenv("BEDSHEET_TRANSPORT", "pubnub")
    monkeypatch.setenv("PUBNUB_SUBSCRIBE_KEY", "sub-c-fake")
    monkeypatch.setenv("PUBNUB_PUBLISH_KEY", "pub-c-fake")

    from bedsheet.sense.factory import make_sense_transport
    from bedsheet.sense.pubnub_transport import PubNubTransport

    transport = make_sense_transport()
    assert isinstance(transport, PubNubTransport)


def test_factory_pubnub_missing_keys_raises(monkeypatch):
    """Asking for pubnub without keys must fail with a clear, actionable
    error — silently falling back to mock would mask a misconfiguration."""
    _clear_sense_env(monkeypatch)
    monkeypatch.setenv("BEDSHEET_TRANSPORT", "pubnub")

    from bedsheet.sense.factory import make_sense_transport

    with pytest.raises(RuntimeError, match="PUBNUB_SUBSCRIBE_KEY"):
        make_sense_transport()


def test_factory_unknown_transport_raises(monkeypatch):
    _clear_sense_env(monkeypatch)
    monkeypatch.setenv("BEDSHEET_TRANSPORT", "carrier-pigeon")

    from bedsheet.sense.factory import make_sense_transport

    with pytest.raises(RuntimeError, match="carrier-pigeon"):
        make_sense_transport()


# ---------- Env-var normalization edge cases ----------
#
# These pin the .strip().lower() + back-compat contract that's currently
# applied at bedsheet/sense/factory.py:38. Unset, empty, whitespace-only,
# and case-varied values must all be handled identically — a future
# refactor that strips this normalization would silently change user-
# visible behavior, and these tests catch that.


@pytest.mark.parametrize(
    "raw_value",
    ["", "   ", "\t", "\n"],
    ids=["empty", "spaces", "tab", "newline"],
)
def test_factory_treats_blank_transport_as_unset(monkeypatch, raw_value):
    """A blank BEDSHEET_TRANSPORT must fall through to back-compat (or
    mock fallback), not raise a confusing 'Unknown' error and not match
    against any branch."""
    _clear_sense_env(monkeypatch)
    monkeypatch.setenv("BEDSHEET_TRANSPORT", raw_value)

    from bedsheet.sense.factory import make_sense_transport
    from bedsheet.testing import MockSenseTransport

    transport = make_sense_transport()
    # No PUBNUB keys set → falls back to mock
    assert isinstance(transport, MockSenseTransport)


@pytest.mark.parametrize(
    "raw_value",
    [" mock ", "MOCK", "Mock", "  Mock  ", "mock\n"],
    ids=["padded", "uppercase", "titlecase", "padded-titlecase", "trailing-newline"],
)
def test_factory_normalizes_mock_transport_value(monkeypatch, raw_value):
    """`.strip().lower()` must accept any reasonable variation of 'mock'."""
    _clear_sense_env(monkeypatch)
    monkeypatch.setenv("BEDSHEET_TRANSPORT", raw_value)

    from bedsheet.sense.factory import make_sense_transport
    from bedsheet.testing import MockSenseTransport

    transport = make_sense_transport()
    assert isinstance(transport, MockSenseTransport)


def test_factory_partial_pubnub_keys_falls_back_to_mock(monkeypatch):
    """If only ONE of PUBNUB_SUBSCRIBE_KEY or PUBNUB_PUBLISH_KEY is set
    (without an explicit BEDSHEET_TRANSPORT), the back-compat path must
    NOT silently use PubNub with a missing key — it must fall back to
    mock so local dev with one stale env var still works."""
    _clear_sense_env(monkeypatch)
    monkeypatch.setenv("PUBNUB_SUBSCRIBE_KEY", "sub-c-orphan")
    # PUBNUB_PUBLISH_KEY intentionally NOT set

    from bedsheet.sense.factory import make_sense_transport
    from bedsheet.testing import MockSenseTransport

    transport = make_sense_transport()
    assert isinstance(transport, MockSenseTransport)


def test_factory_partial_pubnub_keys_with_explicit_pubnub_raises(monkeypatch):
    """If the user explicitly asks for pubnub but only one key is set, the
    factory must raise — not silently fall back. This pins the principle:
    silent fallback is OK for "no preference set", NEVER OK after an
    explicit choice."""
    _clear_sense_env(monkeypatch)
    monkeypatch.setenv("BEDSHEET_TRANSPORT", "pubnub")
    monkeypatch.setenv("PUBNUB_SUBSCRIBE_KEY", "sub-c-orphan")
    # PUBNUB_PUBLISH_KEY intentionally NOT set

    from bedsheet.sense.factory import make_sense_transport

    with pytest.raises(RuntimeError, match="PUBNUB_PUBLISH_KEY"):
        make_sense_transport()
