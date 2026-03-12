"""Tests for LLM recording and replay."""

import json
from pathlib import Path

from bedsheet.action_group import ActionGroup
from bedsheet.events import CompletionEvent, ToolResultEvent
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


async def test_recording_wrap_action_group(tmp_path: Path):
    """wrap_action_group records tool results to JSONL."""
    from bedsheet.recording import RecordingLLMClient

    mock = MockLLMClient(
        responses=[
            MockResponse(
                tool_calls=[
                    ToolCall(id="tc-1", name="greet", input={"name": "Bob"}),
                ]
            ),
            MockResponse(text="Greeted Bob."),
        ]
    )
    path = tmp_path / "test.jsonl"
    recorder = RecordingLLMClient(mock, path=str(path), agent_name="test-agent")

    # Create and wrap an action group
    tools = ActionGroup(name="test-tools")

    @tools.action("greet", "Say hello")
    async def greet(name: str) -> str:
        return f"Hello, {name}!"

    wrapped = recorder.wrap_action_group(tools)

    # Simulate what the agent does: chat() then execute tool
    from bedsheet.agent import Agent

    agent = Agent(name="test-agent", instruction="Be helpful.", model_client=recorder)
    agent.add_action_group(wrapped)

    events = []
    async for event in agent.invoke("s1", "Greet Bob"):
        events.append(event)

    recorder.close()

    # Check tool_result was recorded
    lines = path.read_text().strip().split("\n")
    records = [json.loads(line) for line in lines]
    tool_results = [r for r in records if r["type"] == "tool_result"]
    assert len(tool_results) == 1
    assert tool_results[0]["name"] == "greet"
    assert tool_results[0]["result"] == "Hello, Bob!"
    assert tool_results[0]["error"] is None

    # Check agent produced expected events
    completions = [e for e in events if isinstance(e, CompletionEvent)]
    assert len(completions) == 1
    assert completions[0].response == "Greeted Bob."


async def test_recording_wrap_action_group_error(tmp_path: Path):
    """wrap_action_group records tool errors and re-raises the exception."""
    from bedsheet.recording import RecordingLLMClient

    mock = MockLLMClient(
        responses=[
            MockResponse(
                tool_calls=[
                    ToolCall(id="tc-1", name="explode", input={}),
                ]
            ),
            MockResponse(text="Handled the error."),
        ]
    )
    path = tmp_path / "test.jsonl"
    recorder = RecordingLLMClient(mock, path=str(path), agent_name="test-agent")

    tools = ActionGroup(name="test-tools")

    @tools.action("explode", "Always fails")
    async def explode() -> str:
        raise ValueError("Boom!")

    wrapped = recorder.wrap_action_group(tools)

    from bedsheet.agent import Agent

    agent = Agent(name="test-agent", instruction="Help.", model_client=recorder)
    agent.add_action_group(wrapped)

    events = []
    async for event in agent.invoke("s1", "Do it"):
        events.append(event)

    recorder.close()

    # Check tool_result error was recorded
    lines = path.read_text().strip().split("\n")
    records = [json.loads(line) for line in lines]
    tool_results = [r for r in records if r["type"] == "tool_result"]
    assert len(tool_results) == 1
    assert tool_results[0]["error"] == "Boom!"
    assert tool_results[0]["result"] is None

    # Agent should still complete (it handles errors)
    tool_result_events = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(tool_result_events) == 1
    assert tool_result_events[0].error == "Boom!"


async def test_replay_chat_returns_recorded_responses(tmp_path: Path):
    """ReplayLLMClient serves recorded responses in order."""
    from bedsheet.recording import ReplayLLMClient

    # Write a recording manually
    path = tmp_path / "test.jsonl"
    records = [
        {
            "type": "llm_call",
            "seq": 0,
            "agent": "test",
            "messages_hash": "x",
            "system_hash": "y",
            "tools": [],
        },
        {
            "type": "llm_response",
            "seq": 0,
            "text": "Hello!",
            "tool_calls": [],
            "stop_reason": "end_turn",
            "thinking": None,
            "parsed_output": None,
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    replay = ReplayLLMClient(path=str(path))
    response = await replay.chat(
        [Message(role="user", content="Hi")], system="Be helpful."
    )

    assert response.text == "Hello!"
    assert response.stop_reason == "end_turn"
    assert response.tool_calls == []


async def test_replay_chat_with_tool_calls(tmp_path: Path):
    """ReplayLLMClient reconstructs ToolCall objects from recording."""
    from bedsheet.recording import ReplayLLMClient

    path = tmp_path / "test.jsonl"
    records = [
        {
            "type": "llm_call",
            "seq": 0,
            "agent": "test",
            "messages_hash": "x",
            "system_hash": "y",
            "tools": ["greet"],
        },
        {
            "type": "llm_response",
            "seq": 0,
            "text": None,
            "tool_calls": [{"id": "tc-1", "name": "greet", "input": {"name": "Alice"}}],
            "stop_reason": "tool_use",
            "thinking": None,
            "parsed_output": None,
        },
        {
            "type": "tool_result",
            "seq": 0,
            "call_id": "tc-1",
            "name": "greet",
            "result": "Hello, Alice!",
            "error": None,
        },
        {
            "type": "llm_call",
            "seq": 1,
            "agent": "test",
            "messages_hash": "x2",
            "system_hash": "y",
            "tools": ["greet"],
        },
        {
            "type": "llm_response",
            "seq": 1,
            "text": "Done!",
            "tool_calls": [],
            "stop_reason": "end_turn",
            "thinking": None,
            "parsed_output": None,
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    replay = ReplayLLMClient(path=str(path))

    # First call — should return tool call
    resp1 = await replay.chat([], system="s")
    assert len(resp1.tool_calls) == 1
    assert resp1.tool_calls[0].name == "greet"
    assert resp1.tool_calls[0].id == "tc-1"

    # Second call — should return text
    resp2 = await replay.chat([], system="s")
    assert resp2.text == "Done!"


async def test_replay_get_action_groups(tmp_path: Path):
    """get_action_groups() builds mock tools that return recorded results."""
    from bedsheet.recording import ReplayLLMClient

    path = tmp_path / "test.jsonl"
    records = [
        {
            "type": "llm_call",
            "seq": 0,
            "agent": "test",
            "messages_hash": "x",
            "system_hash": "y",
            "tools": ["greet"],
        },
        {
            "type": "llm_response",
            "seq": 0,
            "text": None,
            "tool_calls": [{"id": "tc-1", "name": "greet", "input": {"name": "Alice"}}],
            "stop_reason": "tool_use",
            "thinking": None,
            "parsed_output": None,
        },
        {
            "type": "tool_result",
            "seq": 0,
            "call_id": "tc-1",
            "name": "greet",
            "result": "Hello, Alice!",
            "error": None,
        },
        {
            "type": "llm_call",
            "seq": 1,
            "agent": "test",
            "messages_hash": "x2",
            "system_hash": "y",
            "tools": ["greet"],
        },
        {
            "type": "llm_response",
            "seq": 1,
            "text": "Done!",
            "tool_calls": [],
            "stop_reason": "end_turn",
            "thinking": None,
            "parsed_output": None,
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    replay = ReplayLLMClient(path=str(path))
    groups = replay.get_action_groups()
    assert len(groups) == 1

    # Should have a "greet" action
    action = groups[0].get_action("greet")
    assert action is not None

    # Calling it should return the recorded result
    result = await action.fn(name="Alice")
    assert result == "Hello, Alice!"


async def test_replay_action_group_error(tmp_path: Path):
    """Mock action raises RuntimeError when recording has error."""
    from bedsheet.recording import ReplayLLMClient

    path = tmp_path / "test.jsonl"
    records = [
        {
            "type": "llm_call",
            "seq": 0,
            "agent": "test",
            "messages_hash": "x",
            "system_hash": "y",
            "tools": ["fail"],
        },
        {
            "type": "llm_response",
            "seq": 0,
            "text": None,
            "tool_calls": [{"id": "tc-1", "name": "fail", "input": {}}],
            "stop_reason": "tool_use",
            "thinking": None,
            "parsed_output": None,
        },
        {
            "type": "tool_result",
            "seq": 0,
            "call_id": "tc-1",
            "name": "fail",
            "result": None,
            "error": "Something broke",
        },
        {
            "type": "llm_call",
            "seq": 1,
            "agent": "test",
            "messages_hash": "x2",
            "system_hash": "y",
            "tools": ["fail"],
        },
        {
            "type": "llm_response",
            "seq": 1,
            "text": "Error handled.",
            "tool_calls": [],
            "stop_reason": "end_turn",
            "thinking": None,
            "parsed_output": None,
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    replay = ReplayLLMClient(path=str(path))
    groups = replay.get_action_groups()
    action = groups[0].get_action("fail")

    import pytest as pt

    with pt.raises(RuntimeError, match="Something broke"):
        await action.fn()
