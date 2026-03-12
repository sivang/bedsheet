# LLM Recording & Replay — Design Spec

> Record LLM responses and tool results during live runs, replay them deterministically without API keys or network access.

## Motivation

The Agent Sentinel demo requires a real Gemini API key and live network access. This blocks:
- **Demo recording** — can't replay a polished demo without hitting the API
- **CI testing** — can't run end-to-end agent flows in GitHub Actions without API keys
- **Deployment testing** — can't verify the full agent loop without external dependencies

## Design

### Architecture

Two new classes in `bedsheet/recording.py`, both implementing the `LLMClient` Protocol:

- **`RecordingLLMClient`** — wraps a real `LLMClient`, proxies all calls, writes interactions to a JSONL file
- **`ReplayLLMClient`** — reads a JSONL file, serves recorded responses in sequence, provides recorded tool results for dry_run mode

### JSONL Record Format

Each line is a JSON object with a `type` field. A complete agent turn produces paired records:

```jsonl
{"type": "llm_call", "seq": 0, "agent": "scheduler", "messages_hash": "a1b2c3", "system_hash": "d4e5f6", "tools": ["add_appointment", "delete_appointment"]}
{"type": "llm_response", "seq": 0, "text": null, "tool_calls": [{"id": "tc-1", "name": "add_appointment", "input": {"title": "Standup", "date": "2026-03-12"}}], "stop_reason": "tool_use"}
{"type": "tool_result", "seq": 0, "call_id": "tc-1", "name": "add_appointment", "result": "Appointment added", "error": null}
{"type": "llm_call", "seq": 1, "agent": "scheduler", "messages_hash": "f7g8h9", "system_hash": "d4e5f6", "tools": ["add_appointment", "delete_appointment"]}
{"type": "llm_response", "seq": 1, "text": "Done! I've added your standup.", "tool_calls": [], "stop_reason": "end_turn"}
```

Fields:
- **`seq`** — sequence counter, ties llm_call → llm_response → tool_results together
- **`messages_hash`** — SHA-256 hash of input messages, used during replay to optionally verify conversation is tracking the same path
- **`system_hash`** — SHA-256 hash of system prompt
- **`tools`** — list of tool names available for this call (for documentation, not used in replay)
- **`tool_calls`** — list of `{id, name, input}` dicts from the LLM response
- **One file per agent** in multi-agent scenarios (e.g., `recording-scheduler.jsonl`, `recording-web-researcher.jsonl`)

### RecordingLLMClient

Wraps any real `LLMClient`. Records every interaction to disk.

```python
from bedsheet.recording import RecordingLLMClient

client = make_llm_client()
recorder = RecordingLLMClient(client, path="recordings/scheduler.jsonl", agent_name="scheduler")

agent = Agent(name="scheduler", model_client=recorder, ...)
async for event in agent.invoke("session-1", "Add a standup"):
    print(event)

recorder.close()
```

Behavior:
- `chat()` → calls real client's `chat()`, writes `llm_call` + `llm_response` records, returns the real response
- `chat_stream()` → calls real client's `chat_stream()`, collects the full response, writes records, yields tokens + final response
- Tool results are captured from the next `chat()` call's input messages — the conversation history already contains them. No hook or callback needed.
- `close()` flushes and closes the file handle
- Maintains internal `seq` counter

### ReplayLLMClient

Reads a JSONL recording, serves responses deterministically.

```python
from bedsheet.recording import ReplayLLMClient

replay = ReplayLLMClient(path="recordings/scheduler.jsonl")

agent = Agent(name="scheduler", model_client=replay, ...)
async for event in agent.invoke("session-1", "Add a standup", dry_run=True):
    print(event)
```

Behavior:
- `chat()` → ignores input messages, returns the next recorded `llm_response` in sequence
- `chat_stream()` → yields recorded text as tokens, then final LLMResponse
- `get_tool_results(seq)` → returns list of `(call_id, result, error)` tuples for the given sequence number. Called by `agent.py` when `dry_run=True`.
- Optionally verifies `messages_hash` matches the recording to detect conversation drift

### Agent Changes: dry_run Parameter

One change to `agent.py` — add `dry_run=False` parameter to `invoke()`:

```python
async def invoke(self, session_id: str, input_text: str, stream: bool = False, dry_run: bool = False) -> AsyncIterator[Event]:
```

In the tool execution section of the ReAct loop:

```python
if dry_run:
    results = self.model_client.get_tool_results(seq)
else:
    results = await asyncio.gather(*[execute_tool(tc) for tc in response.tool_calls])
```

When `dry_run=True`:
- LLM calls go through `ReplayLLMClient` (returns recorded responses)
- Tool execution is skipped entirely
- Tool results come from the recording via `get_tool_results(seq)`
- `ToolCallEvent` is still yielded (from recorded LLM response)
- `ToolResultEvent` is still yielded (from recorded tool results)
- `CompletionEvent` matches the original recording exactly

### File Layout

```
bedsheet/
├── recording.py          # RecordingLLMClient, ReplayLLMClient (~150 LOC)
├── agent.py              # Add dry_run parameter + if/else in tool execution
```

No new dependencies. Uses only stdlib (`json`, `hashlib`, `pathlib`).

## Usage Patterns

### Record a demo

```python
from bedsheet.llm import make_llm_client
from bedsheet.recording import RecordingLLMClient

client = make_llm_client()  # real Gemini client
recorder = RecordingLLMClient(client, path="recordings/scheduler.jsonl", agent_name="scheduler")
agent = Agent(name="scheduler", model_client=recorder, ...)

async for event in agent.invoke("demo-1", "Schedule a team standup for tomorrow at 9am"):
    print(event)

recorder.close()
```

### Replay without API keys

```python
from bedsheet.recording import ReplayLLMClient

replay = ReplayLLMClient(path="recordings/scheduler.jsonl")
agent = Agent(name="scheduler", model_client=replay, ...)

async for event in agent.invoke("demo-1", "Schedule a team standup for tomorrow at 9am", dry_run=True):
    print(event)
```

### CI test

```python
def test_scheduler_replay():
    replay = ReplayLLMClient(path="recordings/scheduler.jsonl")
    agent = Agent(name="scheduler", model_client=replay, ...)

    events = []
    async for event in agent.invoke("test-1", "Schedule a team standup", dry_run=True):
        events.append(event)

    completions = [e for e in events if isinstance(e, CompletionEvent)]
    assert len(completions) == 1
    assert "standup" in completions[0].response.lower()
```

## Done Signal — Verification Criteria

1. **Record** — run sentinel demo with `RecordingLLMClient`, produces `.jsonl` files
2. **Replay** — run same demo with `ReplayLLMClient` + `dry_run=True`, no API keys, no network
3. **Match** — `CompletionEvent.response` text from replay matches original recording exactly
4. **CI test** — committed test in `tests/test_recording.py` replays a small recording and asserts expected output
5. **No regressions** — all existing 307 tests still pass
