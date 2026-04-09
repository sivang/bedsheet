# PR #4 Fixes — Background & Python Constructs

A concise walkthrough of the nine fixes that landed on `feature/sixth-sense`, the Python mechanics behind each, and why the fix works the way it does.

---

## 1. `fix(gemini): chat_stream must make a single API call per turn`

**Commit:** `8b9f3b4` · **File:** `bedsheet/llm/gemini.py`

### Background
`chat_stream` was issuing two API calls per streaming turn: one to `generate_content_stream` (which produced the tokens the user saw) and a second call to `self.chat()` just to obtain the final `LLMResponse`. Users paid 2× per stream, and because LLM sampling isn't deterministic, the text the user *saw* streamed could diverge from the text persisted in memory.

### Python construct: async generators + accumulator pattern
An `async def` function that uses `yield` is an **async generator**. Its caller consumes it with `async for`. To yield *both* streamed tokens AND a final structured result, the standard idiom is:

1. Yield each token as it arrives.
2. Simultaneously **accumulate** the tokens into a local list.
3. After the stream ends, synthesize the final object from the accumulation and yield it.

The wrong pattern is to make a second API call to "get the final answer" — the stream already contains it.

### Before
```python
async for chunk in await self._client.aio.models.generate_content_stream(...):
    if chunk.text:
        yield chunk.text                # user sees this

final = await self.chat(messages, system, tools=None)  # second API call!
yield final                              # user gets this in memory
```

### After
```python
accumulated: list[str] = []
async for chunk in await self._client.aio.models.generate_content_stream(...):
    if chunk.text:
        accumulated.append(chunk.text)   # capture for final
        yield chunk.text                 # stream to user

# Synthesize from what was streamed — no second API call
full_text = "".join(accumulated)
yield LLMResponse(
    text=full_text if full_text else None,
    tool_calls=[],
    stop_reason="end_turn",
)
```

**Why it works:** `accumulated` is a closure-captured local list that survives across all `async for` iterations. The final `yield LLMResponse(...)` produces the same shape as before, but its contents are **provably** equal to the concatenation of what the user saw.

---

## 2. `fix(sense): hold strong references to in-flight request handler tasks`

**Commit:** `fb8ad7e` · **File:** `bedsheet/sense/mixin.py`

### Background
The sense layer's signal loop dispatched incoming `request` signals with `asyncio.create_task(self._handle_request(signal))` and discarded the returned task. CPython's event loop only holds a **weak reference** to tasks created this way — if nothing else holds a strong reference, the garbage collector can drop the task mid-execution, and the requesting agent sees only a `TimeoutError`.

### Python construct: asyncio's weak task bookkeeping
From the [asyncio docs](https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task):

> Important: Save a reference to the result of this function, to avoid a task disappearing mid-execution. The event loop only keeps weak references to tasks.

The canonical fix is:

1. Keep a strong reference in a `set` owned by the dispatcher.
2. Use `task.add_done_callback(callback)` to remove the task from the set when it completes (success, error, or cancellation all trigger the callback).

### Before
```python
if signal.kind == "request":
    asyncio.create_task(self._handle_request(signal))  # dropped!
    continue
```

### After
```python
# in __init__:
self._inflight_request_tasks: set[asyncio.Task[None]] = set()

# in _signal_loop:
if signal.kind == "request":
    handler_task = asyncio.create_task(self._handle_request(signal))
    self._inflight_request_tasks.add(handler_task)
    handler_task.add_done_callback(self._inflight_request_tasks.discard)
    continue
```

**Why it works:** As long as `self._inflight_request_tasks` exists (and the agent instance exists), Python's reference-counter sees the set → task edge and won't collect the task. `set.discard` is used (not `set.remove`) because `discard` is idempotent — safe to call even if the task was already removed by some other path.

Related: `leave_network()` now `await`s `asyncio.gather(*tasks, return_exceptions=True)` instead of calling `task.cancel()` and immediately clearing the set. `cancel()` is asynchronous — it merely *schedules* a `CancelledError`. Without awaiting, the transport could tear down while handlers are still mid-broadcast.

---

## 3. `fix(sentinel): Action Gateway must not lie about execution failures`

**Commit:** `cb9641f` · **File:** `examples/agent-sentinel/middleware/action_gateway.py`

### Background
`ToolExecutor.execute` had a `try: ... except Exception as e: return f"Execution error: {e}"` pattern. Any exception from the handler was silently converted into a normal-looking return string. The caller, `_handle_action_request`, then wrote that string to the append-only audit ledger with `verdict="approved"` — because the pre-execution check *had* said "approved", and nothing communicated "but the execution failed."

The audit ledger lied about what happened. In a demo marketed as a "tamper-proof trust boundary," that's a contradiction.

### Python construct: exception propagation vs. swallowing
A `try/except Exception` block that converts the exception into a value **destroys information**. The caller can no longer distinguish "the tool returned this string" from "the tool raised this exception." The fix is to **let exceptions propagate** out of layers that don't have the context to handle them, and catch them at layers that do.

In this codebase:
- `ToolExecutor` knows how to *run* handlers — it should raise on failure.
- `_handle_action_request` owns the policy for what an audit ledger entry looks like — it should catch and translate to an `error` verdict.

### Before
```python
# ToolExecutor.execute — swallows everything
async def execute(self, action: str, params: dict) -> str:
    handler = getattr(self, f"_do_{action}", None)
    if handler is None:
        return f"Unknown action: {action}"
    try:
        return await handler(params)
    except Exception as e:
        return f"Execution error: {e}"  # lies as a success value

# Caller — verdict stays "approved" even on failure
result = await self._executor.execute(action, params)
record = ActionRecord(..., verdict=verdict, ..., result_summary=result[:200])
```

### After
```python
# ToolExecutor.execute — propagates
async def execute(self, action: str, params: dict) -> str:
    handler = getattr(self, f"_do_{action}", None)
    if handler is None:
        raise ValueError(f"Unknown action: {action}")
    return await handler(params)

# Caller — translates exceptions into an explicit error verdict
if verdict == "approved":
    try:
        result = await self._executor.execute(action, params)
    except Exception as exc:
        logger.exception("Execution failed for %s/%s", agent, action)
        verdict = "error"              # honest verdict
        reason = f"Execution error: {exc}"
        result = ""
```

**Why it works:** The exception-to-value translation now happens **once**, at the layer that writes the audit ledger. The `verdict` is now a single source of truth for whether the action succeeded — the ledger stops lying.

---

## 4. `test(action_group): pin Annotated unwrapping under PEP 563`

**Commit:** `a312015` · **Files:** `tests/test_action_group.py`, `tests/fixtures/future_annotated_action.py`

### Background
Bedsheet supports tool parameter descriptions via `Annotated[str, "description text"]`. The `generate_schema()` function unwraps these annotations to build the tool's JSON schema. The subtle part: under **PEP 563** (`from __future__ import annotations`), all annotations in a module become *strings* at module load time, and the naive `fn.__annotations__["x"]` returns the literal string `'Annotated[str, "description text"]'` — the metadata is lost.

The fix (already in place on an earlier commit) uses `typing.get_type_hints(fn, include_extras=True)` instead of `fn.__annotations__` — the former *resolves* the string forms back into real types AND preserves `Annotated` metadata. But nothing in the test suite actually pinned the PEP 563 case — so a future refactor back to `fn.__annotations__` would break every user who opted into PEP 563, silently.

### Python constructs: PEP 563 + `get_type_hints`
```python
# fixture file — PEP 563 is active
from __future__ import annotations
from typing import Annotated

def add_appointment(
    title: Annotated[str, "Appointment title"],
    minutes: Annotated[int, "Duration in minutes"] = 30,
) -> str: ...
```

Under PEP 563:
- `add_appointment.__annotations__["title"]` → `'Annotated[str, "Appointment title"]'` (a string!)
- `typing.get_type_hints(add_appointment, include_extras=True)["title"]` → `Annotated[str, 'Appointment title']` (the actual type, with metadata intact)

The `include_extras=True` kwarg is the magic bit — without it, `get_type_hints` unwraps `Annotated` and throws the metadata away.

### The test
```python
def test_generate_schema_annotated_under_pep_563_future_annotations():
    from tests.fixtures.future_annotated_action import add_appointment
    schema = generate_schema(add_appointment)
    assert schema["properties"]["title"] == {
        "type": "string",
        "description": "Appointment title",    # <- the metadata survived
    }
```

**Why the fixture lives in its own file:** `from __future__ import annotations` is a *module-level* directive. It must be in scope at module import time. Putting the function inline in the test file wouldn't activate PEP 563 on it, defeating the point.

---

## 5. `feat(sense): add make_sense_transport factory + refactor gateway`

**Commit:** `08c9463` · **File:** `bedsheet/sense/factory.py`

### Background
`SenseTransport` was already a `Protocol` (structural typing, no inheritance required), so the framework was nominally transport-agnostic. But `examples/agent-sentinel/middleware/action_gateway.py` imported `PubNubTransport` at module top level, coupling the example to one specific transport. Any test that imported the gateway dragged `pubnub` into the collection chain, exploding on CI (which doesn't install the `[sense]` extra).

More importantly, this blocked future transports (NATS, Redis pub/sub, ZMQ) from being true drop-ins.

### Python construct: factory pattern + lazy imports
The pattern mirrors `bedsheet/llm/factory.py`:

1. The factory function inspects environment variables.
2. Based on the selection, it **lazily imports** the concrete class (only when actually needed).
3. It returns an instance typed as the **protocol**, not the concrete class.

Lazy imports matter here because `bedsheet.sense.pubnub_transport` raises `ImportError` at module-load time if `pubnub` isn't installed (the file has a top-level `try: from pubnub import ...; except ImportError: raise`). By only importing it inside the `pubnub` branch, we make the factory safe to call even when `pubnub` is missing.

### The factory
```python
def make_sense_transport() -> SenseTransport:
    explicit = os.environ.get("BEDSHEET_TRANSPORT", "").strip().lower()

    if explicit == "mock":
        return _make_mock()
    if explicit == "pubnub":
        return _make_pubnub_or_raise()
    if explicit:
        raise RuntimeError(f"Unknown BEDSHEET_TRANSPORT='{explicit}'. ...")

    # Back-compat: PUBNUB_* keys set → assume PubNub
    if os.environ.get("PUBNUB_SUBSCRIBE_KEY") and os.environ.get("PUBNUB_PUBLISH_KEY"):
        return _make_pubnub_or_raise()

    return _make_mock()

def _make_pubnub_or_raise() -> SenseTransport:
    sub = os.environ.get("PUBNUB_SUBSCRIBE_KEY")
    pub = os.environ.get("PUBNUB_PUBLISH_KEY")
    if not sub or not pub:
        raise RuntimeError("BEDSHEET_TRANSPORT=pubnub requires both keys. ...")
    # Lazy import — only reached when pubnub is actually needed
    from bedsheet.sense.pubnub_transport import PubNubTransport
    return PubNubTransport(subscribe_key=sub, publish_key=pub, ...)
```

### Gateway refactor
```python
# Before
from bedsheet.sense.pubnub_transport import PubNubTransport  # top-level!

class ActionGateway:
    def __init__(self, transport: PubNubTransport) -> None: ...

# After
from bedsheet.sense import Signal, SenseTransport, make_sense_transport

class ActionGateway:
    def __init__(self, transport: SenseTransport) -> None: ...    # protocol type

async def main():
    transport = make_sense_transport()                              # env-driven
```

**Why it works:** `SenseTransport` is a `runtime_checkable Protocol`, so `MockSenseTransport` and `PubNubTransport` both satisfy it structurally without inheriting from anything. Adding a future `NatsTransport` requires zero changes to agent code — just a new `BEDSHEET_TRANSPORT=nats` branch in `factory.py` and a lazy import of the new module.

---

## 6. `chore(deps): add google-genai and pubnub to dev extras`

**Commit:** `30398be` · **File:** `pyproject.toml`

### Background
`bedsheet/llm/gemini.py` has a top-level `from google import genai` guarded by `try/except ImportError`. When `google-genai` isn't installed, the module raises at import time. This meant `patch("bedsheet.llm.gemini.genai", ...)` couldn't even load the module to patch it — my Gemini tests failed on CI with a confusing `AttributeError: module 'bedsheet.llm' has no attribute 'gemini'`.

The same pattern applied to `pubnub` via `bedsheet/sense/pubnub_transport.py`.

### Python construct: optional-dependency groups in pyproject.toml
`pyproject.toml`'s `[project.optional-dependencies]` table defines *extras* — groups of dependencies users can opt into with `pip install bedsheet[group]`. The fix adds both packages to `dev`, the group maintainers install:

```toml
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    ...
    # Optional runtime deps required by the full test suite. These are also
    # in the `sense`/LLM extras so end users installing only what they need
    # stay lean, but `dev` pulls them in so maintainers running
    # `pip install -e ".[dev]"` can execute every test.
    "google-genai>=1.0.0",
    "pubnub>=7.0.0",
]
```

**Why it works:** End users who only want the core framework (and Anthropic / MockLLMClient) still install a lean bedsheet. Maintainers running the full test suite via the `dev` extra get everything needed to exercise every code path.

---

## 7. `fix(gemini): silence strict mypy noise and guard None user content`

**Commit:** `44d2c63` · **File:** `bedsheet/llm/gemini.py`

### Background
Adding `google-genai` to `dev` had a side effect: CI now sees the real Gemini SDK types instead of treating them as `Any`. Three previously-invisible mypy errors surfaced. Two were type-stub strictness (not real bugs), one was a real latent bug (a `None` crash waiting to happen).

### Construct 1: list invariance in type hints
Python's type system treats `list[T]` as **invariant** in `T` — meaning `list[A]` is NOT a subtype of `list[A | B]` even though every element clearly satisfies the union. The Gemini SDK declares `contents` with an extremely broad union, so `list[gtypes.Content]` fails the type check even though it works at runtime.

```python
# list[Content] is fine at runtime but fails mypy's strict list invariance check
async for chunk in await self._client.aio.models.generate_content_stream(
    model=self.model,
    contents=contents,  # type: ignore[arg-type]
    config=config,
):
```

### Construct 2: `# type: ignore[code]` directive
`# type: ignore[arg-type]` suppresses **only** the `arg-type` error category on that line. Better than a bare `# type: ignore` because:
- It documents *which* error we're suppressing.
- If a different, real type error appears later, mypy still catches it.

### Construct 3: `str | None` + `or ""` guard — the real bug
`Message.content` is typed `str | None`. The code was doing `gtypes.Part.from_text(text=msg.content)`, but `from_text` requires `str`. A caller constructing a user message with `content=None` would hit a runtime `TypeError` from inside the SDK. Fix: the `or ""` fallback pattern (same idiom the assistant branch was already using).

```python
# Before — latent crash if content is None
parts=[gtypes.Part.from_text(text=msg.content)]

# After — explicit None guard
parts=[gtypes.Part.from_text(text=msg.content or "")]
```

**Why `or ""` works:** Python evaluates `x or y` as `x` if `x` is truthy, otherwise `y`. `None` is falsy, so `None or ""` evaluates to `""`. This turns a potential runtime crash into "user message is empty string" — an empty turn is at least a defined behavior.

---

## 8. `fix(agent): handle empty model response instead of looping to max_iterations`

**Commit:** `0974b62` · **File:** `bedsheet/agent.py`

### Background
A subtle side-effect of fix #1. The old Gemini `chat_stream` accidentally hid a latent bug: when the stream was empty, the second (wasteful) `self.chat()` call usually returned non-empty text on a different sampling, masking the "empty response" case. After fix #1 correctly stopped the double-call, the agent loop's missing handling of empty responses became reachable.

The ReAct loop's termination logic only handled two cases:
- **Text and no tool calls** → yield `CompletionEvent`, return.
- **Tool calls** → execute them and iterate.

When an `LLMResponse` had **neither** text nor tool calls, both branches were skipped and the loop iterated again with the same prompt — up to `max_iterations` times, eventually yielding a misleading `"Max iterations exceeded"` error.

### Python construct: explicit control flow for the "missing case"
The fix is trivial in code but important in design: when a guard covers some cases, **every remaining case must be explicitly handled** — either by a matching guard or by a final fallback.

### Before
```python
# If text response with no tool calls, we're done
if response.text and not response.tool_calls:
    ...
    return

# Handle tool calls
if response.tool_calls:
    ...
# ← empty response falls through to next iteration silently
```

### After
```python
if response.text and not response.tool_calls:
    ...
    return

# Empty response — no text AND no tool calls. Looping would just
# re-issue the same prompt max_iterations times before yielding a
# generic "max iterations exceeded" error. Bail out cleanly.
if not response.tool_calls:
    yield ErrorEvent(
        error="Model returned an empty response (no text, no tool calls)",
        recoverable=False,
    )
    return

# Handle tool calls
if response.tool_calls:
    ...
```

**Why the check is `if not response.tool_calls:` and not `if not response.text and not response.tool_calls:`:** by this point in the function, the `response.text and not response.tool_calls` branch above has already returned. So if we get here with `not response.tool_calls`, we already know `response.text` is falsy. The shorter condition is equivalent and reads more directly.

---

## 9. `test+fix: harden coverage from PR re-review`

**Commit:** `c4ceb86` · **Files:** multiple tests + `bedsheet/sense/mixin.py`

Six things in one logical batch, all surfaced by re-running the PR review toolkit against the delta.

### 9a. B3 audit-ledger integration test

The original B3 unit tests only covered `ToolExecutor`. The actual B3 **bug** lived in `_handle_action_request`'s bookkeeping. A unit test that only pins executor behavior doesn't catch a regression where someone reorders the try/except in the caller. Fix: a small integration test that constructs an `ActionGateway` with a stub transport, injects a failing handler, and inspects the ledger directly.

```python
async def test_handle_action_request_records_error_verdict_on_executor_failure():
    gateway = ActionGateway(StubTransport())

    async def boom(params: dict) -> str:
        raise RuntimeError("disk on fire")
    gateway._executor._do_explode = boom  # dynamic attribute injection

    await gateway._handle_action_request(
        Signal(kind="request", sender="rogue", payload={"action": "explode", "params": {}}, ...)
    )

    records = gateway._ledger.query(minutes=10)
    assert records[-1].verdict == "error"    # the ledger stays honest
```

### 9b. Factory env-var normalization tests (`@pytest.mark.parametrize`)

The factory uses `.strip().lower()` for forgiving env-var parsing, but nothing pinned that contract. Added parametrized tests for `""`, `"   "`, `"\t"`, `"\n"`, `" mock "`, `"MOCK"`, `"Mock"`, `"  Mock  "`, `"mock\n"`, plus partial-PubNub-keys edge cases.

```python
@pytest.mark.parametrize(
    "raw_value",
    ["", "   ", "\t", "\n"],
    ids=["empty", "spaces", "tab", "newline"],
)
def test_factory_treats_blank_transport_as_unset(monkeypatch, raw_value):
    ...
```

**`@pytest.mark.parametrize`** is pytest's way of running the same test body against multiple inputs. The `ids=[...]` argument gives each case a readable name in the test output (e.g. `test_factory_treats_blank_transport_as_unset[newline]`).

### 9c. B2 pure-behavioral GC test (`gc.collect()`)

The original B2 test was **structural** — it asserted the existence of the `_inflight_request_tasks` attribute. If a future refactor changes the retention strategy (say, a `WeakSet` wrapper or a different attribute name), the structural test breaks even though behavior is fine.

A complementary **behavioral** test forces a GC cycle while the handler is suspended and verifies the request still completes. It doesn't care HOW the agent retains the task — only that it survives.

```python
import gc

async def test_inflight_request_survives_gc_pressure(self):
    # ... set up a blocking LLM client + worker + commander ...
    request_task = asyncio.create_task(commander.request("gc-worker", ...))
    await asyncio.sleep(0.05)  # let the handler dispatch and block

    gc.collect()
    gc.collect()  # second pass to handle reference cycles
    await asyncio.sleep(0.05)
    gc.collect()

    gate.set()
    result = await request_task
    assert result == "survived-gc"   # behavioral assertion
```

**`gc.collect()`** forces a full garbage collection cycle. Python's cyclic garbage collector sometimes needs multiple passes to reach reference cycles, hence the repeated calls. If the handler task were only weakly referenced (the pre-fix bug), this sequence would collect it and the request would time out.

### 9d. Thought-signature middle-hop test

Gemini 3.x requires the model's raw "parts" (including `thought_signature`) to be echoed back on every multi-turn call. The round-trip has three stops:
1. `_parse_response` stashes raw parts on `LLMResponse._gemini_raw_parts`.
2. The agent loop copies that stash onto the persisted `Message._gemini_parts`.
3. `_convert_messages` echoes them back on the next call.

Steps 1 and 3 were tested in `test_gemini.py`. Step 2 — the agent loop copy — was uncovered. A stub LLM client that returns an `LLMResponse` with `_gemini_raw_parts` set, one ReAct iteration, then inspect `agent.memory.get_messages(...)`.

```python
response = LLMResponse(text=None, tool_calls=[...], stop_reason="tool_use")
response._gemini_raw_parts = sentinel_parts  # runtime attribute set
# ... run one iteration ...
persisted = await agent.memory.get_messages("thought-sig")
assistant_msgs = [m for m in persisted if m.role == "assistant" and m.tool_calls]
assert assistant_msgs[0]._gemini_parts is sentinel_parts  # identity check
```

**Why `is` and not `==`:** `is` tests object identity (the same object in memory), while `==` tests equality. For this test we want to prove the *exact* sentinel list made it through unmodified — not that some other equal list was built along the way.

### 9e. `leave_network()` defensive cancel (`asyncio.gather` + `return_exceptions`)

`task.cancel()` schedules a `CancelledError` — it does **not** synchronously stop execution. The old code called `cancel()` then immediately cleared the set, which meant in-flight handlers could still be mid-`broadcast` while the transport tore down underneath them.

Fix: use `asyncio.gather(*tasks, return_exceptions=True)` to await every handler's reaction to the cancel. The `return_exceptions=True` flag is critical — without it, `gather` would re-raise the first `CancelledError` it sees, short-circuiting the rest. With it, all tasks are awaited to completion and their exceptions (including `CancelledError`) are returned as values instead of raised.

```python
if self._inflight_request_tasks:
    inflight = list(self._inflight_request_tasks)
    for task in inflight:
        task.cancel()
    # Await every cancellation so handlers can't race with transport teardown
    await asyncio.gather(*inflight, return_exceptions=True)
    self._inflight_request_tasks.clear()
```

### 9f. Replace `sys.path.insert` with `importlib.util.spec_from_file_location`

The gateway example lives outside `tests/` (under `examples/agent-sentinel/middleware/`), so the test needed some way to import it. The original approach mutated `sys.path` — functional but brittle (global side effect, potential name collisions if the example tree grows).

Fix: use `importlib.util` to load the file as a module directly, without touching `sys.path`.

```python
import importlib.util
from pathlib import Path

_GATEWAY_PATH = (
    Path(__file__).resolve().parent.parent
    / "examples" / "agent-sentinel" / "middleware" / "action_gateway.py"
)

def _load_action_gateway_module():
    spec = importlib.util.spec_from_file_location(
        "_agent_sentinel_action_gateway",  # module name for identification
        _GATEWAY_PATH,                      # file path to load
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)         # runs the file's top-level code
    return module

_gateway = _load_action_gateway_module()

# Now bind names from the loaded module at test-file module level
ActionLedger = _gateway.ActionLedger
ActionGateway = _gateway.ActionGateway
# ... etc
```

**Why this is cleaner than `sys.path.insert`:**
- No global state mutation — the loaded module exists only in the test file's namespace.
- No risk of collisions with other test files that happen to use the same package name.
- Self-contained — the test file owns its entire import strategy.

**The three-step machinery:**
1. `spec_from_file_location(name, path)` builds a module *spec* (metadata).
2. `module_from_spec(spec)` creates an empty module object.
3. `spec.loader.exec_module(module)` runs the file's source inside that module's namespace.

This is exactly what Python's normal import machinery does under the hood; `importlib.util` just exposes it for explicit use.

---

## Summary — Python constructs used across the fixes

| Construct | Fix | Purpose |
|---|---|---|
| Async generators + accumulate-and-yield | #1 | Stream tokens AND produce a final synthesized result from one API call |
| `asyncio.create_task` strong-ref set + `add_done_callback` | #2 | Prevent the event loop's weak task references from dropping handlers |
| `asyncio.gather(..., return_exceptions=True)` | #9e | Await cancellations without short-circuiting on the first `CancelledError` |
| Exception propagation across layers | #3 | Keep policy (ledger verdict) at the layer that owns the policy |
| `from __future__ import annotations` + `get_type_hints(include_extras=True)` | #4 | Resolve string-form annotations back to real `Annotated` types |
| Factory pattern + lazy imports | #5 | Keep optional deps out of the import graph unless actually needed |
| `[project.optional-dependencies]` groups | #6 | End-user lean install vs. maintainer full install |
| `# type: ignore[arg-type]` targeted suppressions | #7 | Silence SDK stub strictness without hiding real errors |
| `or ""` fallback for `str \| None` | #7 | Turn a latent `None`-crash into a defined empty-string behavior |
| Explicit control-flow guards for "missing case" | #8 | Don't rely on the next iteration to recover from degenerate responses |
| `@pytest.mark.parametrize(..., ids=[...])` | #9b | Run one test body against many named inputs |
| `gc.collect()` + `asyncio.Event` | #9c | Force GC cycles to test weak-reference invariants behaviorally |
| `is` vs `==` (identity vs equality) | #9d | Prove a specific object survived a round-trip, not just "something equal" |
| `importlib.util.spec_from_file_location` | #9f | Load a module from an arbitrary file path without mutating `sys.path` |

---

## One-line meta takeaway

The common thread is **honesty about state**: the B1 fix makes streamed text equal persisted text, the B2 fix prevents the event loop from silently dropping work, the B3 fix stops the audit ledger from lying, the H1 fix turns a silent retry loop into an explicit error, and the factory removes hidden coupling between examples and one specific transport. Every fix replaces an implicit behavior with an explicit one.
