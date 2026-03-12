"""Tests for LLM recording and replay."""

import json
from pathlib import Path

from bedsheet.llm.base import ToolCall
from bedsheet.memory.base import Message
from bedsheet.testing import MockLLMClient, MockResponse


async def test_recording_chat_writes_jsonl(tmp_path: Path):
    """RecordingLLMClient proxies chat() and writes llm_call + llm_response records."""
    from bedsheet.recording import RecordingLLMClient

    mock = MockLLMClient(
        responses=[
            MockResponse(text="Hello there!"),
        ]
    )
    path = tmp_path / "test.jsonl"
    recorder = RecordingLLMClient(mock, path=str(path), agent_name="test-agent")

    messages = [Message(role="user", content="Hi")]
    response = await recorder.chat(messages, system="Be helpful.")

    # Should proxy the response unchanged
    assert response.text == "Hello there!"
    assert response.stop_reason == "end_turn"

    recorder.close()

    # Should have written 2 records: llm_call + llm_response
    lines = path.read_text().strip().split("\n")
    assert len(lines) == 2

    call_record = json.loads(lines[0])
    assert call_record["type"] == "llm_call"
    assert call_record["seq"] == 0
    assert call_record["agent"] == "test-agent"
    assert "messages_hash" in call_record
    assert "system_hash" in call_record

    resp_record = json.loads(lines[1])
    assert resp_record["type"] == "llm_response"
    assert resp_record["seq"] == 0
    assert resp_record["text"] == "Hello there!"
    assert resp_record["tool_calls"] == []
    assert resp_record["stop_reason"] == "end_turn"


async def test_recording_chat_with_tool_calls(tmp_path: Path):
    """RecordingLLMClient records tool calls in llm_response."""
    from bedsheet.recording import RecordingLLMClient

    mock = MockLLMClient(
        responses=[
            MockResponse(
                tool_calls=[
                    ToolCall(id="tc-1", name="greet", input={"name": "Alice"}),
                ]
            ),
            MockResponse(text="Done greeting Alice."),
        ]
    )
    path = tmp_path / "test.jsonl"
    recorder = RecordingLLMClient(mock, path=str(path), agent_name="test-agent")

    # First call — returns tool call
    messages = [Message(role="user", content="Greet Alice")]
    resp1 = await recorder.chat(messages, system="Be helpful.")
    assert resp1.tool_calls[0].name == "greet"

    # Second call — returns text
    messages.append(
        Message(
            role="assistant",
            content=None,
            tool_calls=[{"id": "tc-1", "name": "greet", "input": {"name": "Alice"}}],
        )
    )
    messages.append(
        Message(role="tool_result", content="Hello, Alice!", tool_call_id="tc-1")
    )
    resp2 = await recorder.chat(messages, system="Be helpful.")
    assert resp2.text == "Done greeting Alice."

    recorder.close()

    lines = path.read_text().strip().split("\n")
    assert len(lines) == 4  # 2 calls × (llm_call + llm_response)

    resp_record = json.loads(lines[1])
    assert resp_record["tool_calls"] == [
        {"id": "tc-1", "name": "greet", "input": {"name": "Alice"}}
    ]


async def test_recording_seq_increments(tmp_path: Path):
    """Sequence counter increments on each chat() call."""
    from bedsheet.recording import RecordingLLMClient

    mock = MockLLMClient(
        responses=[
            MockResponse(text="First"),
            MockResponse(text="Second"),
        ]
    )
    path = tmp_path / "test.jsonl"
    recorder = RecordingLLMClient(mock, path=str(path), agent_name="test-agent")

    await recorder.chat([Message(role="user", content="1")], system="s")
    await recorder.chat([Message(role="user", content="2")], system="s")
    recorder.close()

    lines = path.read_text().strip().split("\n")
    assert json.loads(lines[0])["seq"] == 0
    assert json.loads(lines[2])["seq"] == 1
