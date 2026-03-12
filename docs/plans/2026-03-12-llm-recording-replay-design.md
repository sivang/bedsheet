# LLM Recording & Replay — Design Spec (v2)

> Record LLM responses and tool results during live runs, replay them deterministically without API keys or network access.

## Motivation

The Agent Sentinel demo requires a real Gemini API key and live network access. This blocks:
- **Demo recording** — can't replay a polished demo without hitting the API
- **CI testing** — can't run end-to-end agent flows in GitHub Actions without API keys
- **Deployment testing** — can't verify the full agent loop without external dependencies

## Design

### Architecture

Two new classes in `bedsheet/recording.py`, both implementing the `LLMClient` Protocol:

- **`RecordingLLMClient`** — wraps a real `LLMClient`, proxies all calls, writes interactions to a JSONL file. Also wraps action groups to record tool results.
- **`ReplayLLMClient`** — reads a JSONL file, serves recorded LLM responses in sequence. Also generates mock action groups that return recorded tool results.

**Zero changes to `agent.py` or `supervisor.py`.** The agent loop runs exactly as normal — it gets canned LLM responses from `ReplayLLMClient` and canned tool results from the mock action groups. No `dry_run` parameter, no protocol extensions, no special cases.

### JSONL Record Format

Each line is a JSON object with a `type` field. A complete agent turn produces paired records:

```jsonl
{"type": "llm_call", "seq": 0, "agent": "scheduler", "messages_hash": "a1b2c3", "system_hash": "d4e5f6", "tools": ["add_appointment", "delete_appointment"]}
{"type": "llm_response", "seq": 0, "text": null, "tool_calls": [{"id": "tc-1", "name": "add_appointment", "input": {"title": "Standup", "date": "2026-03-12"}}], "stop_reason": "tool_use", "thinking": null}
{"type": "tool_result", "seq": 0, "call_id": "tc-1", "name": "add_appointment", "result": "Appointment added", "error": null}
{"type": "llm_call", "seq": 1, "agent": "scheduler", "messages_hash": "f7g8h9", "system_hash": "d4e5f6", "tools": ["add_appointment", "delete_appointment"]}
{"type": "llm_response", "seq": 1, "text": "Done! I've added your standup.", "tool_calls": [], "stop_reason": "end_turn", "thinking": null}
```

Fields:
- **`seq`** — sequence counter, ties llm_call → llm_response → tool_results together
- **`messages_hash`** — SHA-256 hash of JSON-serialized message content strings, used during replay to optionally verify conversation is tracking the same path. On mismatch: logs a warning, does not raise.
- **`system_hash`** — SHA-256 hash of system prompt
- **`tools`** — list of tool names available (for documentation/debugging, not used in replay)
- **`tool_calls`** — list of `{id, name, input}` dicts from the LLM response
- **`thinking`** — thinking/reasoning text from extended thinking mode, if present
- **One file per agent** in multi-agent scenarios (e.g., `recording-scheduler.jsonl`, `recording-web-researcher.jsonl`)

### RecordingLLMClient

Wraps any real `LLMClient`. Records every interaction to disk. Also wraps action groups to capture tool results.

```python
from bedsheet.recording import RecordingLLMClient

client = make_llm_client()
recorder = RecordingLLMClient(client, path="recordings/scheduler.jsonl", agent_name="scheduler")

agent = Agent(name="scheduler", model_client=recorder, ...)

# Wrap action groups so tool results are recorded
scheduler_tools = recorder.wrap_action_group(scheduler_tools)
agent.add_action_group(scheduler_tools)

async for event in agent.invoke("session-1", "Add a standup"):
    print(event)

recorder.close()
```

Behavior:
- `chat()` → calls real client's `chat()`, writes `llm_call` + `llm_response` records, returns the real response unchanged
- `chat_stream()` → proxies the real client's `chat_stream()` iterator, yielding tokens as they arrive. After the final `LLMResponse` is yielded, writes the records. Streaming behavior is preserved — no buffering.
- `wrap_action_group(group)` → returns a new `ActionGroup` with wrapper functions that call the original tool, record the result as a `tool_result` record, and return the result unchanged. This is how tool results get into the JSONL.
- `close()` flushes and closes the file handle. Also supports `async with` context manager.
- Maintains internal `seq` counter, incremented on each `chat()` call.
- `parsed_output` from structured output responses is serialized as JSON in the `llm_response` record.

### ReplayLLMClient

Reads a JSONL recording, serves responses deterministically. Generates mock action groups from recorded tool results.

```python
from bedsheet.recording import ReplayLLMClient

replay = ReplayLLMClient(path="recordings/scheduler.jsonl")

agent = Agent(name="scheduler", model_client=replay, ...)

# Add replay's mock action groups — they return recorded tool results
for group in replay.get_action_groups():
    agent.add_action_group(group)

async for event in agent.invoke("session-1", "Add a standup"):
    print(event)
```

Behavior:
- `chat()` → ignores input messages, returns the next recorded `llm_response` in sequence as an `LLMResponse` object (with `text`, `tool_calls`, `stop_reason`, `thinking`, `parsed_output`)
- `chat_stream()` → yields recorded text word-by-word as tokens, then the final `LLMResponse`
- `get_action_groups()` → builds `ActionGroup` objects from the recording's `tool_result` records. Each unique tool name gets an async function that returns the next recorded result for that tool (matched by sequence). The agent calls these exactly as it would call real tools.
- Optionally verifies `messages_hash` — on mismatch, logs a warning (does not raise)
- **No `_gemini_raw_parts`** — replay responses do not include Gemini-specific raw parts. This is acceptable because replay never sends to a real Gemini API. Noted as a known limitation.

### How Recording Works (Data Flow)

```
Recording:
  Agent.invoke() → chat() → [real LLM] → LLMResponse    → JSONL: llm_call + llm_response
                 → execute_tool() → [real tool] → result  → JSONL: tool_result (via wrapped action group)
                 → chat() → [real LLM] → LLMResponse      → JSONL: llm_call + llm_response
                 → CompletionEvent

Replay:
  Agent.invoke() → chat() → [ReplayLLMClient] → recorded LLMResponse
                 → execute_tool() → [mock action group] → recorded result
                 → chat() → [ReplayLLMClient] → recorded LLMResponse
                 → CompletionEvent (identical to original)
```

### Why This Works for Supervisor Too

`Supervisor` extends `Agent` and has its own `invoke()` loop, but it uses the same `LLMClient` protocol for LLM calls and the same `ActionGroup` mechanism for tool execution. Since recording/replay operates entirely through these two interfaces — replacing the LLM client and wrapping/mocking action groups — it works for both `Agent` and `Supervisor` without any changes to either class.

For multi-agent replay (Supervisor + collaborators), each agent gets its own `ReplayLLMClient` loaded from its own recording file. The Supervisor's delegate tool is also recorded and replayed via the action group wrapper.

### File Layout

```
bedsheet/
├── recording.py          # RecordingLLMClient, ReplayLLMClient (~200 LOC)
```

No new dependencies. Uses only stdlib (`json`, `hashlib`, `pathlib`, `logging`).

## Usage Patterns

### Record a demo

```python
from bedsheet.llm import make_llm_client
from bedsheet.recording import RecordingLLMClient

client = make_llm_client()  # real Gemini client
recorder = RecordingLLMClient(client, path="recordings/scheduler.jsonl", agent_name="scheduler")

agent = Agent(name="scheduler", model_client=recorder, ...)
scheduler_tools = recorder.wrap_action_group(scheduler_tools)
agent.add_action_group(scheduler_tools)

async for event in agent.invoke("demo-1", "Schedule a team standup for tomorrow at 9am"):
    print(event)

recorder.close()
```

### Replay without API keys

```python
from bedsheet.recording import ReplayLLMClient

replay = ReplayLLMClient(path="recordings/scheduler.jsonl")
agent = Agent(name="scheduler", model_client=replay, ...)
for group in replay.get_action_groups():
    agent.add_action_group(group)

async for event in agent.invoke("demo-1", "Schedule a team standup for tomorrow at 9am"):
    print(event)
```

### CI test

```python
async def test_scheduler_replay():
    replay = ReplayLLMClient(path="recordings/scheduler.jsonl")
    agent = Agent(name="scheduler", model_client=replay, ...)
    for group in replay.get_action_groups():
        agent.add_action_group(group)

    events = []
    async for event in agent.invoke("test-1", "Schedule a team standup"):
        events.append(event)

    completions = [e for e in events if isinstance(e, CompletionEvent)]
    assert len(completions) == 1
    assert "standup" in completions[0].response.lower()
```

## Known Limitations

- **No `_gemini_raw_parts` in replay** — Gemini-specific thought_signature parts are not serialized. Pure replay does not need them since responses never go back to a real Gemini API.
- **`stop_reason` values are preserved as-is** — no normalization between Anthropic ("tool_use") and Gemini conventions. The recording captures whatever the original client returned.
- **Streaming replay is simulated** — `chat_stream()` on `ReplayLLMClient` yields recorded text word-by-word, not at original timing. Sufficient for testing, not for timing-accurate playback.

## Done Signal — Verification Criteria

1. **Record** — run sentinel demo with `RecordingLLMClient` + wrapped action groups, produces `.jsonl` files
2. **Replay** — run same demo with `ReplayLLMClient` + `get_action_groups()`, no API keys, no network
3. **Match** — `CompletionEvent.response` text from replay matches original recording exactly
4. **CI test** — committed test in `tests/test_recording.py` replays a small recording and asserts expected output
5. **No regressions** — all existing 307 tests still pass
