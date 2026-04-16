"""Tests for LLM recording and replay."""

import json
from pathlib import Path

from bedsheet.action_group import ActionGroup
from bedsheet.events import CompletionEvent, ToolCallEvent, ToolResultEvent
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


async def test_record_then_replay_e2e(tmp_path: Path):
    """Full cycle: record with real agent, replay from file, get same output."""
    from bedsheet.recording import RecordingLLMClient, ReplayLLMClient

    # --- RECORD ---
    mock = MockLLMClient(
        responses=[
            MockResponse(
                tool_calls=[
                    ToolCall(id="tc-1", name="lookup", input={"key": "weather"}),
                ]
            ),
            MockResponse(text="The weather is sunny."),
        ]
    )
    recording_path = tmp_path / "e2e.jsonl"
    recorder = RecordingLLMClient(
        mock, path=str(recording_path), agent_name="e2e-agent"
    )

    tools = ActionGroup(name="e2e-tools")

    @tools.action("lookup", "Look up a value")
    async def lookup(key: str) -> str:
        return f"value-for-{key}"

    wrapped_tools = recorder.wrap_action_group(tools)

    from bedsheet.agent import Agent

    agent = Agent(name="e2e-agent", instruction="Help the user.", model_client=recorder)
    agent.add_action_group(wrapped_tools)

    recorded_events = []
    async for event in agent.invoke("s1", "What's the weather?"):
        recorded_events.append(event)
    recorder.close()

    recorded_completions = [
        e for e in recorded_events if isinstance(e, CompletionEvent)
    ]
    assert len(recorded_completions) == 1
    recorded_text = recorded_completions[0].response

    # --- REPLAY ---
    replay = ReplayLLMClient(path=str(recording_path))
    replay_agent = Agent(
        name="e2e-agent", instruction="Help the user.", model_client=replay
    )
    for group in replay.get_action_groups():
        replay_agent.add_action_group(group)

    replayed_events = []
    async for event in replay_agent.invoke("s1", "What's the weather?"):
        replayed_events.append(event)

    replayed_completions = [
        e for e in replayed_events if isinstance(e, CompletionEvent)
    ]
    assert len(replayed_completions) == 1
    replayed_text = replayed_completions[0].response

    # --- MATCH ---
    assert replayed_text == recorded_text

    # Verify same tool call events
    recorded_tool_calls = [e for e in recorded_events if isinstance(e, ToolCallEvent)]
    replayed_tool_calls = [e for e in replayed_events if isinstance(e, ToolCallEvent)]
    assert len(recorded_tool_calls) == len(replayed_tool_calls)
    assert recorded_tool_calls[0].tool_name == replayed_tool_calls[0].tool_name

    # Verify same tool result events
    recorded_tool_results = [
        e for e in recorded_events if isinstance(e, ToolResultEvent)
    ]
    replayed_tool_results = [
        e for e in replayed_events if isinstance(e, ToolResultEvent)
    ]
    assert len(recorded_tool_results) == len(replayed_tool_results)
    assert recorded_tool_results[0].result == replayed_tool_results[0].result


async def test_recording_chat_stream(tmp_path: Path):
    """RecordingLLMClient.chat_stream() proxies tokens and records the final response."""
    from bedsheet.recording import RecordingLLMClient

    mock = MockLLMClient(
        responses=[
            MockResponse(text="Hello world"),
        ]
    )
    path = tmp_path / "test.jsonl"
    recorder = RecordingLLMClient(mock, path=str(path), agent_name="test")

    tokens = []
    final = None
    async for chunk in recorder.chat_stream(
        [Message(role="user", content="Hi")], system="s"
    ):
        if isinstance(chunk, str):
            tokens.append(chunk)
        else:
            final = chunk

    recorder.close()

    # Should have streamed tokens
    assert len(tokens) > 0
    # Should have final LLMResponse
    assert final is not None
    assert final.text == "Hello world"

    # Should have written records
    lines = path.read_text().strip().split("\n")
    assert len(lines) == 2  # llm_call + llm_response


async def test_replay_chat_stream(tmp_path: Path):
    """ReplayLLMClient.chat_stream() yields recorded text as tokens."""
    from bedsheet.recording import ReplayLLMClient

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
            "text": "Hello world",
            "tool_calls": [],
            "stop_reason": "end_turn",
            "thinking": None,
            "parsed_output": None,
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    replay = ReplayLLMClient(path=str(path))
    tokens = []
    final = None
    async for chunk in replay.chat_stream([], system="s"):
        if isinstance(chunk, str):
            tokens.append(chunk)
        else:
            final = chunk

    assert len(tokens) > 0
    assert final is not None
    assert final.text == "Hello world"


async def test_recording_parsed_output(tmp_path: Path):
    """RecordingLLMClient serializes parsed_output in recording."""
    from bedsheet.recording import RecordingLLMClient

    mock = MockLLMClient(
        responses=[
            MockResponse(text="result", parsed_output={"name": "Alice", "age": 30}),
        ]
    )
    path = tmp_path / "test.jsonl"
    recorder = RecordingLLMClient(mock, path=str(path), agent_name="test")

    await recorder.chat([Message(role="user", content="Hi")], system="s")
    recorder.close()

    lines = path.read_text().strip().split("\n")
    resp = json.loads(lines[1])
    assert resp["parsed_output"] == {"name": "Alice", "age": 30}


async def test_replay_parsed_output(tmp_path: Path):
    """ReplayLLMClient returns parsed_output as plain dict."""
    from bedsheet.recording import ReplayLLMClient

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
            "text": "ok",
            "tool_calls": [],
            "stop_reason": "end_turn",
            "thinking": None,
            "parsed_output": {"name": "Alice", "age": 30},
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    replay = ReplayLLMClient(path=str(path))
    response = await replay.chat([], system="s")
    assert response.parsed_output == {"name": "Alice", "age": 30}


async def test_recording_context_manager(tmp_path: Path):
    """RecordingLLMClient supports async with."""
    from bedsheet.recording import RecordingLLMClient

    mock = MockLLMClient(responses=[MockResponse(text="Hi")])
    path = tmp_path / "test.jsonl"

    async with RecordingLLMClient(mock, path=str(path), agent_name="test") as recorder:
        await recorder.chat([Message(role="user", content="Hi")], system="s")

    # File should be closed and flushed
    assert path.exists()
    lines = path.read_text().strip().split("\n")
    assert len(lines) == 2


async def test_replay_exhausted_responses(tmp_path: Path):
    """Exhausted ReplayLLMClient returns a synthetic text completion.

    When replay runs out of recorded responses it returns a sentinel text
    message instead of text=None.  Returning None with empty tool_calls
    would trigger the agent's empty-response guard (added for Gemini
    content-filtering failures) and surface a misleading error during
    replay.  The synthetic text lets the ReAct loop exit cleanly via its
    normal "text with no tool_calls → CompletionEvent" branch.
    """
    from bedsheet.recording import ReplayLLMClient

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
            "text": "Only one",
            "tool_calls": [],
            "stop_reason": "end_turn",
            "thinking": None,
            "parsed_output": None,
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    replay = ReplayLLMClient(path=str(path))
    await replay.chat([], system="s")  # consumes the one response

    # Exhausted replay returns a synthetic text completion (not None) so the
    # agent's ReAct loop exits via the normal completion branch rather than
    # hitting the empty-response error guard.
    result = await replay.chat([], system="s")
    assert result.stop_reason == "end_turn"
    assert result.tool_calls == []
    assert result.text is not None
    assert "Replay complete" in result.text


async def test_replay_exhausted_tool_results(tmp_path: Path):
    """Mock action raises RuntimeError when tool result queue is empty."""
    from bedsheet.recording import ReplayLLMClient
    import pytest as pt

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
            "tool_calls": [{"id": "tc-1", "name": "greet", "input": {}}],
            "stop_reason": "tool_use",
            "thinking": None,
            "parsed_output": None,
        },
        {
            "type": "tool_result",
            "seq": 0,
            "call_id": "tc-1",
            "name": "greet",
            "result": "Hi",
            "error": None,
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    replay = ReplayLLMClient(path=str(path))
    groups = replay.get_action_groups()
    action = groups[0].get_action("greet")

    await action.fn()  # consumes the one result

    with pt.raises(RuntimeError, match="no more recorded results"):
        await action.fn()


async def test_enable_recording(tmp_path: Path):
    """enable_recording wraps agent's model_client and action groups."""
    from bedsheet.recording import RecordingLLMClient, enable_recording

    mock = MockLLMClient(
        responses=[
            MockResponse(text="Hello!"),
        ]
    )
    from bedsheet.agent import Agent

    tools = ActionGroup(name="test-tools")

    @tools.action("noop", "Do nothing")
    async def noop() -> str:
        return "ok"

    agent = Agent(name="test", instruction="Help.", model_client=mock)
    agent.add_action_group(tools)

    enable_recording(agent, directory=str(tmp_path))

    # model_client should now be RecordingLLMClient
    assert isinstance(agent.model_client, RecordingLLMClient)

    # Run the agent
    async for event in agent.invoke("s1", "Hi"):
        pass

    agent.model_client.close()

    # Should have created a recording file named after the agent
    recording_path = tmp_path / "test.jsonl"
    assert recording_path.exists()
    lines = recording_path.read_text().strip().split("\n")
    assert len(lines) >= 2  # at least llm_call + llm_response


async def test_enable_replay(tmp_path: Path):
    """enable_replay replaces agent's model_client and action groups."""
    from bedsheet.recording import ReplayLLMClient, enable_replay

    # Write a recording
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
            "text": "Replayed!",
            "tool_calls": [],
            "stop_reason": "end_turn",
            "thinking": None,
            "parsed_output": None,
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    from bedsheet.agent import Agent

    agent = Agent(
        name="test", instruction="Help.", model_client=MockLLMClient(responses=[])
    )

    enable_replay(agent, directory=str(tmp_path))

    # model_client should now be ReplayLLMClient
    assert isinstance(agent.model_client, ReplayLLMClient)

    # Run the agent — should get replayed response
    events = []
    async for event in agent.invoke("s1", "Hi"):
        events.append(event)

    completions = [e for e in events if isinstance(e, CompletionEvent)]
    assert len(completions) == 1
    assert completions[0].response == "Replayed!"
