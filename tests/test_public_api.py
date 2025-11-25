"""Test that public API is properly exported."""


def test_main_exports():
    from bedsheet import Agent, ActionGroup
    assert Agent is not None
    assert ActionGroup is not None


def test_llm_exports():
    from bedsheet.llm import AnthropicClient, LLMClient
    assert AnthropicClient is not None
    assert LLMClient is not None


def test_memory_exports():
    from bedsheet.memory import InMemory, RedisMemory, Memory
    assert InMemory is not None
    assert RedisMemory is not None
    assert Memory is not None


def test_events_exports():
    from bedsheet.events import (
        Event,
        ThinkingEvent,
        ToolCallEvent,
        ToolResultEvent,
        CompletionEvent,
        ErrorEvent,
    )
    assert Event is not None
    assert ThinkingEvent is not None
    assert ToolCallEvent is not None
    assert ToolResultEvent is not None
    assert CompletionEvent is not None
    assert ErrorEvent is not None


def test_testing_exports():
    from bedsheet.testing import MockLLMClient, MockResponse
    assert MockLLMClient is not None
    assert MockResponse is not None


def test_exceptions_exports():
    from bedsheet.exceptions import (
        BedsheetError,
        MaxIterationsError,
        LLMError,
        ActionNotFoundError,
    )
    assert BedsheetError is not None
    assert MaxIterationsError is not None
    assert LLMError is not None
    assert ActionNotFoundError is not None
