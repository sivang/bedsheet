# LLM Recording & Replay — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `RecordingLLMClient` and `ReplayLLMClient` to bedsheet so agent runs can be recorded to JSONL and replayed deterministically without API keys or network access.

**Architecture:** Two classes in `bedsheet/recording.py` that implement the `LLMClient` Protocol. `RecordingLLMClient` wraps a real client and logs interactions. `ReplayLLMClient` reads a recording and serves canned responses + mock action groups. Two helper functions (`enable_recording`, `enable_replay`) provide one-liner setup with env var support.

**Tech Stack:** Python 3.11+ stdlib only (`json`, `hashlib`, `pathlib`, `logging`, `collections`)

**Spec:** `docs/plans/2026-03-12-llm-recording-replay-design.md` (v3)

---

## File Structure

| File | Responsibility |
|------|----------------|
| `bedsheet/recording.py` (create) | `RecordingLLMClient`, `ReplayLLMClient`, `enable_recording`, `enable_replay` |
| `bedsheet/__init__.py` (modify) | Export `enable_recording`, `enable_replay` |
| `tests/test_recording.py` (create) | All recording/replay tests |

---

## Chunk 1: RecordingLLMClient

### Task 1: Write failing tests for RecordingLLMClient.chat()

**Files:**
- Create: `tests/test_recording.py`

- [ ] **Step 1: Write the test file with recording tests**

```python
"""Tests for LLM recording and replay."""

import json
from pathlib import Path

from bedsheet.action_group import ActionGroup
from bedsheet.events import CompletionEvent, ToolCallEvent, ToolResultEvent
from bedsheet.llm.base import LLMResponse, ToolCall, ToolDefinition
from bedsheet.memory.base import Message
from bedsheet.testing import MockLLMClient, MockResponse


async def test_recording_chat_writes_jsonl(tmp_path: Path):
    """RecordingLLMClient proxies chat() and writes llm_call + llm_response records."""
    from bedsheet.recording import RecordingLLMClient

    mock = MockLLMClient(responses=[
        MockResponse(text="Hello there!"),
    ])
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

    mock = MockLLMClient(responses=[
        MockResponse(tool_calls=[
            ToolCall(id="tc-1", name="greet", input={"name": "Alice"}),
        ]),
        MockResponse(text="Done greeting Alice."),
    ])
    path = tmp_path / "test.jsonl"
    recorder = RecordingLLMClient(mock, path=str(path), agent_name="test-agent")

    # First call — returns tool call
    messages = [Message(role="user", content="Greet Alice")]
    resp1 = await recorder.chat(messages, system="Be helpful.")
    assert resp1.tool_calls[0].name == "greet"

    # Second call — returns text
    messages.append(Message(role="assistant", content=None, tool_calls=[
        {"id": "tc-1", "name": "greet", "input": {"name": "Alice"}}
    ]))
    messages.append(Message(role="tool_result", content="Hello, Alice!", tool_call_id="tc-1"))
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

    mock = MockLLMClient(responses=[
        MockResponse(text="First"),
        MockResponse(text="Second"),
    ])
    path = tmp_path / "test.jsonl"
    recorder = RecordingLLMClient(mock, path=str(path), agent_name="test-agent")

    await recorder.chat([Message(role="user", content="1")], system="s")
    await recorder.chat([Message(role="user", content="2")], system="s")
    recorder.close()

    lines = path.read_text().strip().split("\n")
    assert json.loads(lines[0])["seq"] == 0
    assert json.loads(lines[2])["seq"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_recording.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bedsheet.recording'`

- [ ] **Step 3: Commit**

```bash
git add tests/test_recording.py
git commit -m "test: add failing tests for RecordingLLMClient.chat()"
```

---

### Task 2: Implement RecordingLLMClient.chat()

**Files:**
- Create: `bedsheet/recording.py`

- [ ] **Step 1: Write the implementation**

```python
"""LLM recording and replay for deterministic agent runs."""

import hashlib
import json
import logging
from collections import deque
from pathlib import Path
from typing import Any, AsyncIterator

from bedsheet.action_group import Action, ActionGroup
from bedsheet.llm.base import LLMResponse, OutputSchema, ToolCall, ToolDefinition
from bedsheet.memory.base import Message

_log = logging.getLogger(__name__)


def _hash(data: str) -> str:
    """SHA-256 hash, truncated to 12 hex chars."""
    return hashlib.sha256(data.encode()).hexdigest()[:12]


def _messages_hash(messages: list[Message]) -> str:
    """Hash the content of messages for drift detection."""
    parts = []
    for m in messages:
        parts.append(f"{m.role}:{m.content or ''}")
        if m.tool_calls:
            parts.append(json.dumps(m.tool_calls, sort_keys=True))
        if m.tool_call_id:
            parts.append(m.tool_call_id)
    return _hash("|".join(parts))


def _serialize_tool_calls(tool_calls: list[ToolCall]) -> list[dict[str, Any]]:
    """Convert ToolCall dataclasses to JSON-serializable dicts."""
    return [{"id": tc.id, "name": tc.name, "input": tc.input} for tc in tool_calls]


def _serialize_parsed_output(parsed_output: Any) -> Any:
    """Serialize parsed_output, handling Pydantic models."""
    if parsed_output is None:
        return None
    if hasattr(parsed_output, "model_dump"):
        return parsed_output.model_dump()
    return parsed_output


class RecordingLLMClient:
    """LLM client wrapper that records all interactions to a JSONL file.

    Wraps any LLMClient, proxies all calls, and writes records to disk.
    Use wrap_action_group() to also record tool results.
    """

    def __init__(self, client: Any, path: str, agent_name: str) -> None:
        self._client = client
        self._path = Path(path)
        self._agent_name = agent_name
        self._seq = 0
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self._path, "w")

    def _write(self, record: dict[str, Any]) -> None:
        self._file.write(json.dumps(record, separators=(",", ":")) + "\n")
        self._file.flush()

    def _record_call(
        self, messages: list[Message], system: str, tools: list[ToolDefinition] | None
    ) -> None:
        self._write({
            "type": "llm_call",
            "seq": self._seq,
            "agent": self._agent_name,
            "messages_hash": _messages_hash(messages),
            "system_hash": _hash(system),
            "tools": [t.name for t in tools] if tools else [],
        })

    def _record_response(self, response: LLMResponse) -> None:
        self._write({
            "type": "llm_response",
            "seq": self._seq,
            "text": response.text,
            "tool_calls": _serialize_tool_calls(response.tool_calls),
            "stop_reason": response.stop_reason,
            "thinking": response.thinking,
            "parsed_output": _serialize_parsed_output(response.parsed_output),
        })

    async def chat(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
        output_schema: OutputSchema | None = None,
    ) -> LLMResponse:
        self._record_call(messages, system, tools)
        response = await self._client.chat(messages, system, tools, output_schema)
        self._record_response(response)
        self._seq += 1
        return response

    async def chat_stream(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
        output_schema: OutputSchema | None = None,
    ) -> AsyncIterator[str | LLMResponse]:
        self._record_call(messages, system, tools)
        final_response = None
        async for chunk in self._client.chat_stream(messages, system, tools, output_schema):
            if isinstance(chunk, LLMResponse):
                final_response = chunk
                self._record_response(chunk)
                self._seq += 1
            yield chunk
        if final_response is None:
            _log.warning("chat_stream ended without LLMResponse")

    def wrap_action_group(self, group: ActionGroup) -> ActionGroup:
        """Wrap an action group so tool results are recorded."""
        wrapped = ActionGroup(name=group.name, description=group.description)
        for action in group.get_actions():
            recorder = self

            def _build_wrapper(act: Action) -> Any:
                original_fn = act.fn

                async def wrapper(**kwargs: Any) -> Any:
                    try:
                        result = await original_fn(**kwargs)
                        recorder._write({
                            "type": "tool_result",
                            "seq": recorder._seq - 1,  # seq was incremented after chat()
                            "call_id": "",  # not available here; replay matches by name + order
                            "name": act.name,
                            "result": result if isinstance(result, str) else json.dumps(result),
                            "error": None,
                        })
                        return result
                    except Exception as e:
                        recorder._write({
                            "type": "tool_result",
                            "seq": recorder._seq - 1,
                            "call_id": "",
                            "name": act.name,
                            "result": None,
                            "error": str(e),
                        })
                        raise

                return wrapper

            wrapped._actions[action.name] = Action(
                name=action.name,
                description=action.description,
                fn=_build_wrapper(action),
                input_schema=action.input_schema,
            )
        return wrapped

    def close(self) -> None:
        """Flush and close the recording file."""
        if not self._file.closed:
            self._file.flush()
            self._file.close()

    async def __aenter__(self) -> "RecordingLLMClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        self.close()
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/test_recording.py -v`
Expected: All 3 tests PASS

- [ ] **Step 3: Commit**

```bash
git add bedsheet/recording.py
git commit -m "feat: add RecordingLLMClient with chat() and JSONL output"
```

---

### Task 3: Test and implement wrap_action_group

**Files:**
- Modify: `tests/test_recording.py`

- [ ] **Step 1: Add test for wrap_action_group**

Append to `tests/test_recording.py`:

```python
async def test_recording_wrap_action_group(tmp_path: Path):
    """wrap_action_group records tool results to JSONL."""
    from bedsheet.recording import RecordingLLMClient

    mock = MockLLMClient(responses=[
        MockResponse(tool_calls=[
            ToolCall(id="tc-1", name="greet", input={"name": "Bob"}),
        ]),
        MockResponse(text="Greeted Bob."),
    ])
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
    tool_results = [json.loads(l) for l in lines if json.loads(l)["type"] == "tool_result"]
    assert len(tool_results) == 1
    assert tool_results[0]["name"] == "greet"
    assert tool_results[0]["result"] == "Hello, Bob!"
    assert tool_results[0]["error"] is None

    # Check agent produced expected events
    completions = [e for e in events if isinstance(e, CompletionEvent)]
    assert len(completions) == 1
    assert completions[0].response == "Greeted Bob."
```

- [ ] **Step 2: Run to verify it passes**

Run: `pytest tests/test_recording.py::test_recording_wrap_action_group -v`
Expected: PASS (implementation already in Task 2)

- [ ] **Step 3: Commit**

```bash
git add tests/test_recording.py
git commit -m "test: add wrap_action_group recording test"
```

---

### Task 3b: Test error recording in wrap_action_group

**Files:**
- Modify: `tests/test_recording.py`

- [ ] **Step 1: Add error recording test**

Append to `tests/test_recording.py`:

```python
async def test_recording_wrap_action_group_error(tmp_path: Path):
    """wrap_action_group records tool errors and re-raises the exception."""
    from bedsheet.recording import RecordingLLMClient

    mock = MockLLMClient(responses=[
        MockResponse(tool_calls=[
            ToolCall(id="tc-1", name="explode", input={}),
        ]),
        MockResponse(text="Handled the error."),
    ])
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
    tool_results = [json.loads(l) for l in lines if json.loads(l)["type"] == "tool_result"]
    assert len(tool_results) == 1
    assert tool_results[0]["error"] == "Boom!"
    assert tool_results[0]["result"] is None

    # Agent should still complete (it handles errors)
    tool_result_events = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(tool_result_events) == 1
    assert tool_result_events[0].error == "Boom!"
```

- [ ] **Step 2: Run to verify it passes**

Run: `pytest tests/test_recording.py::test_recording_wrap_action_group_error -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_recording.py
git commit -m "test: add error recording test for wrap_action_group"
```

---

## Chunk 2: ReplayLLMClient

### Task 4: Write failing tests for ReplayLLMClient

**Files:**
- Modify: `tests/test_recording.py`

- [ ] **Step 1: Add ReplayLLMClient tests**

Append to `tests/test_recording.py`:

```python
async def test_replay_chat_returns_recorded_responses(tmp_path: Path):
    """ReplayLLMClient serves recorded responses in order."""
    from bedsheet.recording import ReplayLLMClient

    # Write a recording manually
    path = tmp_path / "test.jsonl"
    records = [
        {"type": "llm_call", "seq": 0, "agent": "test", "messages_hash": "x", "system_hash": "y", "tools": []},
        {"type": "llm_response", "seq": 0, "text": "Hello!", "tool_calls": [], "stop_reason": "end_turn", "thinking": None, "parsed_output": None},
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
        {"type": "llm_call", "seq": 0, "agent": "test", "messages_hash": "x", "system_hash": "y", "tools": ["greet"]},
        {"type": "llm_response", "seq": 0, "text": None, "tool_calls": [{"id": "tc-1", "name": "greet", "input": {"name": "Alice"}}], "stop_reason": "tool_use", "thinking": None, "parsed_output": None},
        {"type": "tool_result", "seq": 0, "call_id": "tc-1", "name": "greet", "result": "Hello, Alice!", "error": None},
        {"type": "llm_call", "seq": 1, "agent": "test", "messages_hash": "x2", "system_hash": "y", "tools": ["greet"]},
        {"type": "llm_response", "seq": 1, "text": "Done!", "tool_calls": [], "stop_reason": "end_turn", "thinking": None, "parsed_output": None},
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
        {"type": "llm_call", "seq": 0, "agent": "test", "messages_hash": "x", "system_hash": "y", "tools": ["greet"]},
        {"type": "llm_response", "seq": 0, "text": None, "tool_calls": [{"id": "tc-1", "name": "greet", "input": {"name": "Alice"}}], "stop_reason": "tool_use", "thinking": None, "parsed_output": None},
        {"type": "tool_result", "seq": 0, "call_id": "tc-1", "name": "greet", "result": "Hello, Alice!", "error": None},
        {"type": "llm_call", "seq": 1, "agent": "test", "messages_hash": "x2", "system_hash": "y", "tools": ["greet"]},
        {"type": "llm_response", "seq": 1, "text": "Done!", "tool_calls": [], "stop_reason": "end_turn", "thinking": None, "parsed_output": None},
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
        {"type": "llm_call", "seq": 0, "agent": "test", "messages_hash": "x", "system_hash": "y", "tools": ["fail"]},
        {"type": "llm_response", "seq": 0, "text": None, "tool_calls": [{"id": "tc-1", "name": "fail", "input": {}}], "stop_reason": "tool_use", "thinking": None, "parsed_output": None},
        {"type": "tool_result", "seq": 0, "call_id": "tc-1", "name": "fail", "result": None, "error": "Something broke"},
        {"type": "llm_call", "seq": 1, "agent": "test", "messages_hash": "x2", "system_hash": "y", "tools": ["fail"]},
        {"type": "llm_response", "seq": 1, "text": "Error handled.", "tool_calls": [], "stop_reason": "end_turn", "thinking": None, "parsed_output": None},
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    replay = ReplayLLMClient(path=str(path))
    groups = replay.get_action_groups()
    action = groups[0].get_action("fail")

    import pytest as pt
    with pt.raises(RuntimeError, match="Something broke"):
        await action.fn()
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_recording.py -v -k "replay"`
Expected: FAIL — `ImportError: cannot import name 'ReplayLLMClient'`

- [ ] **Step 3: Commit**

```bash
git add tests/test_recording.py
git commit -m "test: add failing tests for ReplayLLMClient"
```

---

### Task 5: Implement ReplayLLMClient

**Files:**
- Modify: `bedsheet/recording.py`

- [ ] **Step 1: Add ReplayLLMClient to recording.py**

Append to `bedsheet/recording.py`:

```python
class ReplayLLMClient:
    """LLM client that replays recorded responses from a JSONL file.

    Serves canned LLM responses in sequence. Use get_action_groups()
    to get mock action groups that return recorded tool results.
    """

    def __init__(self, path: str, delay: float = 0.0) -> None:
        self._path = Path(path)
        self._delay = delay
        self._responses: deque[dict[str, Any]] = deque()
        self._tool_results: dict[str, deque[dict[str, Any]]] = {}  # tool_name -> queue
        self._load()

    def _load(self) -> None:
        """Parse JSONL and index records by type."""
        with open(self._path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record["type"] == "llm_response":
                    self._responses.append(record)
                elif record["type"] == "tool_result":
                    name = record["name"]
                    if name not in self._tool_results:
                        self._tool_results[name] = deque()
                    self._tool_results[name].append(record)

    async def chat(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
        output_schema: OutputSchema | None = None,
    ) -> LLMResponse:
        if not self._responses:
            raise RuntimeError("ReplayLLMClient: no more recorded responses")

        if self._delay > 0:
            import asyncio
            await asyncio.sleep(self._delay)

        record = self._responses.popleft()
        tool_calls = [
            ToolCall(id=tc["id"], name=tc["name"], input=tc["input"])
            for tc in record.get("tool_calls", [])
        ]
        return LLMResponse(
            text=record.get("text"),
            tool_calls=tool_calls,
            stop_reason=record.get("stop_reason", "end_turn"),
            thinking=record.get("thinking"),
            parsed_output=record.get("parsed_output"),
        )

    async def chat_stream(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
        output_schema: OutputSchema | None = None,
    ) -> AsyncIterator[str | LLMResponse]:
        import asyncio

        response = await self.chat(messages, system, tools, output_schema)
        if response.text:
            for word in response.text.split(" "):
                if self._delay > 0:
                    await asyncio.sleep(self._delay)
                yield word + " "
        yield response

    def get_action_groups(self) -> list[ActionGroup]:
        """Build mock action groups from recorded tool results.

        Each unique tool name gets an async function backed by a queue.
        Results are served in recording order. Errors raise RuntimeError.
        """
        if not self._tool_results:
            return []

        group = ActionGroup(name="replay-tools", description="Replayed tool results")

        for tool_name, result_queue in self._tool_results.items():
            queue = result_queue  # capture for closure

            def _build_mock(name: str, q: deque) -> Any:
                async def mock_fn(**kwargs: Any) -> Any:
                    if not q:
                        raise RuntimeError(f"ReplayLLMClient: no more recorded results for '{name}'")
                    record = q.popleft()
                    if record.get("error"):
                        raise RuntimeError(record["error"])
                    return record["result"]
                return mock_fn

            group._actions[tool_name] = Action(
                name=tool_name,
                description=f"Replayed: {tool_name}",
                fn=_build_mock(tool_name, queue),
                input_schema={"type": "object", "properties": {}, "required": []},
            )

        return [group]
```

- [ ] **Step 2: Run the replay tests**

Run: `pytest tests/test_recording.py -v -k "replay"`
Expected: All 4 replay tests PASS

- [ ] **Step 3: Run all recording tests**

Run: `pytest tests/test_recording.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add bedsheet/recording.py
git commit -m "feat: add ReplayLLMClient with mock action groups"
```

---

## Chunk 3: End-to-End Record + Replay

### Task 6: End-to-end record-then-replay test

**Files:**
- Modify: `tests/test_recording.py`

- [ ] **Step 1: Add the e2e test**

Append to `tests/test_recording.py`:

```python
async def test_record_then_replay_e2e(tmp_path: Path):
    """Full cycle: record with real agent, replay from file, get same output."""
    from bedsheet.recording import RecordingLLMClient, ReplayLLMClient

    # --- RECORD ---
    mock = MockLLMClient(responses=[
        MockResponse(tool_calls=[
            ToolCall(id="tc-1", name="lookup", input={"key": "weather"}),
        ]),
        MockResponse(text="The weather is sunny."),
    ])
    recording_path = tmp_path / "e2e.jsonl"
    recorder = RecordingLLMClient(mock, path=str(recording_path), agent_name="e2e-agent")

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

    recorded_completions = [e for e in recorded_events if isinstance(e, CompletionEvent)]
    assert len(recorded_completions) == 1
    recorded_text = recorded_completions[0].response

    # --- REPLAY ---
    replay = ReplayLLMClient(path=str(recording_path))
    replay_agent = Agent(name="e2e-agent", instruction="Help the user.", model_client=replay)
    for group in replay.get_action_groups():
        replay_agent.add_action_group(group)

    replayed_events = []
    async for event in replay_agent.invoke("s1", "What's the weather?"):
        replayed_events.append(event)

    replayed_completions = [e for e in replayed_events if isinstance(e, CompletionEvent)]
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
    recorded_tool_results = [e for e in recorded_events if isinstance(e, ToolResultEvent)]
    replayed_tool_results = [e for e in replayed_events if isinstance(e, ToolResultEvent)]
    assert len(recorded_tool_results) == len(replayed_tool_results)
    assert recorded_tool_results[0].result == replayed_tool_results[0].result
```

- [ ] **Step 2: Run to verify it passes**

Run: `pytest tests/test_recording.py::test_record_then_replay_e2e -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_recording.py
git commit -m "test: add end-to-end record-then-replay test"
```

---

### Task 6b: Additional coverage tests (streaming, parsed_output, context manager, exhaustion)

**Files:**
- Modify: `tests/test_recording.py`

- [ ] **Step 1: Add coverage tests**

Append to `tests/test_recording.py`:

```python
async def test_recording_chat_stream(tmp_path: Path):
    """RecordingLLMClient.chat_stream() proxies tokens and records the final response."""
    from bedsheet.recording import RecordingLLMClient

    mock = MockLLMClient(responses=[
        MockResponse(text="Hello world"),
    ])
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
        {"type": "llm_call", "seq": 0, "agent": "test", "messages_hash": "x", "system_hash": "y", "tools": []},
        {"type": "llm_response", "seq": 0, "text": "Hello world", "tool_calls": [], "stop_reason": "end_turn", "thinking": None, "parsed_output": None},
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

    mock = MockLLMClient(responses=[
        MockResponse(text="result", parsed_output={"name": "Alice", "age": 30}),
    ])
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
        {"type": "llm_call", "seq": 0, "agent": "test", "messages_hash": "x", "system_hash": "y", "tools": []},
        {"type": "llm_response", "seq": 0, "text": "ok", "tool_calls": [], "stop_reason": "end_turn", "thinking": None, "parsed_output": {"name": "Alice", "age": 30}},
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
    """ReplayLLMClient raises RuntimeError when recordings are exhausted."""
    from bedsheet.recording import ReplayLLMClient
    import pytest as pt

    path = tmp_path / "test.jsonl"
    records = [
        {"type": "llm_call", "seq": 0, "agent": "test", "messages_hash": "x", "system_hash": "y", "tools": []},
        {"type": "llm_response", "seq": 0, "text": "Only one", "tool_calls": [], "stop_reason": "end_turn", "thinking": None, "parsed_output": None},
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    replay = ReplayLLMClient(path=str(path))
    await replay.chat([], system="s")  # consumes the one response

    with pt.raises(RuntimeError, match="no more recorded responses"):
        await replay.chat([], system="s")


async def test_replay_exhausted_tool_results(tmp_path: Path):
    """Mock action raises RuntimeError when tool result queue is empty."""
    from bedsheet.recording import ReplayLLMClient
    import pytest as pt

    path = tmp_path / "test.jsonl"
    records = [
        {"type": "llm_call", "seq": 0, "agent": "test", "messages_hash": "x", "system_hash": "y", "tools": ["greet"]},
        {"type": "llm_response", "seq": 0, "text": None, "tool_calls": [{"id": "tc-1", "name": "greet", "input": {}}], "stop_reason": "tool_use", "thinking": None, "parsed_output": None},
        {"type": "tool_result", "seq": 0, "call_id": "tc-1", "name": "greet", "result": "Hi", "error": None},
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    replay = ReplayLLMClient(path=str(path))
    groups = replay.get_action_groups()
    action = groups[0].get_action("greet")

    await action.fn()  # consumes the one result

    with pt.raises(RuntimeError, match="no more recorded results"):
        await action.fn()
```

- [ ] **Step 2: Run to verify all pass**

Run: `pytest tests/test_recording.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_recording.py
git commit -m "test: add streaming, parsed_output, context manager, and exhaustion tests"
```

---

## Chunk 4: Helper Functions + Exports

### Task 7: Write failing tests for enable_recording / enable_replay

**Files:**
- Modify: `tests/test_recording.py`

- [ ] **Step 1: Add helper function tests**

Append to `tests/test_recording.py`:

```python
async def test_enable_recording(tmp_path: Path):
    """enable_recording wraps agent's model_client and action groups."""
    from bedsheet.recording import RecordingLLMClient, enable_recording

    mock = MockLLMClient(responses=[
        MockResponse(text="Hello!"),
    ])
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
        {"type": "llm_call", "seq": 0, "agent": "test", "messages_hash": "x", "system_hash": "y", "tools": []},
        {"type": "llm_response", "seq": 0, "text": "Replayed!", "tool_calls": [], "stop_reason": "end_turn", "thinking": None, "parsed_output": None},
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    from bedsheet.agent import Agent

    agent = Agent(name="test", instruction="Help.", model_client=MockLLMClient(responses=[]))

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
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_recording.py -v -k "enable_"`
Expected: FAIL — `ImportError: cannot import name 'enable_recording'`

- [ ] **Step 3: Commit**

```bash
git add tests/test_recording.py
git commit -m "test: add failing tests for enable_recording/enable_replay helpers"
```

---

### Task 8: Implement enable_recording / enable_replay

**Files:**
- Modify: `bedsheet/recording.py`

- [ ] **Step 1: Add helper functions to recording.py**

Append to `bedsheet/recording.py`:

```python
def enable_recording(agent: Any, directory: str) -> None:
    """Enable recording mode on an agent.

    Wraps the agent's model_client with RecordingLLMClient and
    re-wraps all action groups to record tool results.

    Args:
        agent: An Agent or Supervisor instance.
        directory: Directory to write recording files to.
                   File is named {agent.name}.jsonl.
    """
    path = str(Path(directory) / f"{agent.name}.jsonl")
    recorder = RecordingLLMClient(agent.model_client, path=path, agent_name=agent.name)
    agent.model_client = recorder

    # Re-wrap existing action groups
    new_groups = []
    for group in agent._action_groups:
        new_groups.append(recorder.wrap_action_group(group))
    agent._action_groups = new_groups


def enable_replay(agent: Any, directory: str, delay: float = 0.0) -> None:
    """Enable replay mode on an agent.

    Replaces the agent's model_client with ReplayLLMClient and
    replaces action groups with mock groups from the recording.

    Args:
        agent: An Agent or Supervisor instance.
        directory: Directory containing recording files.
                   Reads {agent.name}.jsonl.
        delay: Seconds between tokens/responses. 0.0 for instant (CI),
               0.05-0.2 for demo presentations.
    """
    path = str(Path(directory) / f"{agent.name}.jsonl")
    replay = ReplayLLMClient(path=path, delay=delay)
    agent.model_client = replay

    # Replace action groups with replay mocks
    agent._action_groups = replay.get_action_groups()
```

- [ ] **Step 2: Run the helper tests**

Run: `pytest tests/test_recording.py -v -k "enable_"`
Expected: Both PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/test_recording.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add bedsheet/recording.py
git commit -m "feat: add enable_recording/enable_replay helper functions"
```

---

### Task 9: Export from bedsheet.__init__

**Files:**
- Modify: `bedsheet/__init__.py`

- [ ] **Step 1: Add exports**

Add to `bedsheet/__init__.py`:

```python
from bedsheet.recording import enable_recording, enable_replay
```

And add to `__all__`:

```python
__all__ = [
    "Agent",
    "ActionGroup",
    "Annotated",
    "Supervisor",
    "SenseMixin",
    "SenseNetwork",
    "enable_recording",
    "enable_replay",
]
```

- [ ] **Step 2: Verify imports work**

Run: `python -c "from bedsheet import enable_recording, enable_replay; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Run full test suite to check no regressions**

Run: `pytest tests/ -v --ignore=tests/integration`
Expected: All 307+ tests PASS (307 existing + new recording tests)

- [ ] **Step 4: Commit**

```bash
git add bedsheet/__init__.py
git commit -m "feat: export enable_recording/enable_replay from bedsheet"
```

---

## Chunk 5: Verification (Done Signal)

### Task 10: Final verification

- [ ] **Step 1: Run all recording tests**

Run: `pytest tests/test_recording.py -v`
Expected: All PASS

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v --ignore=tests/integration`
Expected: All PASS, no regressions

- [ ] **Step 3: Verify the e2e test proves the done signal**

The `test_record_then_replay_e2e` test proves:
1. Recording produces a JSONL file ✓
2. Replay reads the file and serves responses without API keys ✓
3. CompletionEvent.response matches exactly ✓
4. ToolCallEvent and ToolResultEvent match ✓
5. Runs in pytest with no API keys ✓

- [ ] **Step 4: Commit and push**

```bash
git push
```
