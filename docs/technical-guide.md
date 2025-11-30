# Bedsheet Agents - Technical Deep Dive

A comprehensive guide to the architecture, patterns, and Python techniques used in Bedsheet Agents.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Python Patterns](#core-python-patterns)
   - [Protocols (Structural Typing)](#protocols-structural-typing)
   - [Dataclasses](#dataclasses)
   - [Type Hints & Union Types](#type-hints--union-types)
3. [Async Programming](#async-programming)
   - [Async/Await Basics](#asyncawait-basics)
   - [AsyncIterator & Streaming](#asynciterator--streaming)
   - [Parallel Execution with asyncio.gather](#parallel-execution-with-asynciogather)
4. [The Decorator Pattern](#the-decorator-pattern)
   - [@action Decorator](#action-decorator)
   - [Schema Inference from Type Hints](#schema-inference-from-type-hints)
5. [Event-Driven Architecture](#event-driven-architecture)
   - [Event Types](#event-types)
   - [Event Flow](#event-flow)
6. [Multi-Agent Orchestration](#multi-agent-orchestration)
   - [Supervisor Pattern](#supervisor-pattern)
   - [Parallel Delegation](#parallel-delegation)
7. [LLM Integration](#llm-integration)
   - [Non-Streaming vs Streaming](#non-streaming-vs-streaming)
   - [Tool Calling](#tool-calling)
8. [Testing Patterns](#testing-patterns)
   - [MockLLMClient](#mockllmclient)
   - [Async Test Fixtures](#async-test-fixtures)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Application                         │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Supervisor / Agent                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Instruction │  │   Memory    │  │      ActionGroups       │  │
│  │   (prompt)  │  │  (history)  │  │   (tools/functions)     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
         ┌──────────────────┐        ┌──────────────────┐
         │    LLMClient     │        │   Collaborators  │
         │  (AnthropicAPI)  │        │  (other Agents)  │
         └──────────────────┘        └──────────────────┘
                    │
                    ▼
         ┌──────────────────┐
         │  Event Stream    │
         │  (AsyncIterator) │
         └──────────────────┘
```

**Key Components:**

| Component | Purpose | File |
|-----------|---------|------|
| `Agent` | Single agent with ReAct loop | `agent.py` |
| `Supervisor` | Multi-agent coordinator | `supervisor.py` |
| `ActionGroup` | Tool/function container | `action_group.py` |
| `LLMClient` | Protocol for LLM providers | `llm/base.py` |
| `Memory` | Conversation history storage | `memory/base.py` |
| `Event` | Streaming event types | `events.py` |

---

## Core Python Patterns

### Protocols (Structural Typing)

**What it is:** Protocols define interfaces without inheritance. Any class that has the right methods/attributes satisfies the protocol - this is called "structural typing" or "duck typing with type hints."

**Why use it:** Loose coupling. You can swap implementations without changing code that uses the protocol.

```python
# bedsheet/llm/base.py
from typing import Protocol, runtime_checkable

@runtime_checkable  # Allows isinstance() checks
class LLMClient(Protocol):
    """Protocol defining what an LLM client must implement."""

    async def chat(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Send messages and get a response."""
        ...

    async def chat_stream(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[str | LLMResponse]:
        """Stream response token by token."""
        ...
```

**Usage - Any class with these methods satisfies the protocol:**

```python
# This class doesn't inherit from LLMClient, but satisfies the protocol
class AnthropicClient:
    async def chat(self, messages, system, tools=None) -> LLMResponse:
        # Implementation...

    async def chat_stream(self, messages, system, tools=None):
        # Implementation...

# Type checking works:
client: LLMClient = AnthropicClient()  # ✓ Valid

# Runtime checking works (because of @runtime_checkable):
assert isinstance(client, LLMClient)  # ✓ True
```

**Comparison with Abstract Base Classes:**

| Approach | Coupling | isinstance() | Flexibility |
|----------|----------|--------------|-------------|
| ABC (inheritance) | Tight - must inherit | Built-in | Less - locked to hierarchy |
| Protocol | Loose - duck typing | Requires @runtime_checkable | More - any matching class works |

---

### Dataclasses

**What it is:** A decorator that auto-generates `__init__`, `__repr__`, `__eq__`, and more from class attributes.

**Why use it:** Less boilerplate, immutable-by-default option, type hints integrated.

```python
# bedsheet/events.py
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class ToolCallEvent:
    """Emitted when the LLM requests a tool call."""
    tool_name: str
    tool_input: dict[str, Any]
    call_id: str
    # field() with default - computed at class definition, not instance creation
    type: Literal["tool_call"] = field(default="tool_call", init=False)
```

**What dataclass generates:**

```python
# Equivalent to writing:
class ToolCallEvent:
    def __init__(self, tool_name: str, tool_input: dict, call_id: str):
        self.tool_name = tool_name
        self.tool_input = tool_input
        self.call_id = call_id
        self.type = "tool_call"

    def __repr__(self):
        return f"ToolCallEvent(tool_name={self.tool_name!r}, ...)"

    def __eq__(self, other):
        if not isinstance(other, ToolCallEvent):
            return NotImplemented
        return (self.tool_name == other.tool_name and ...)
```

**Key `field()` options:**

```python
@dataclass
class Example:
    # Regular field - required in __init__
    name: str

    # Default value
    count: int = 0

    # Computed default (use field + default_factory for mutable defaults)
    items: list = field(default_factory=list)

    # Excluded from __init__ but set after
    computed: str = field(init=False)

    def __post_init__(self):
        self.computed = f"Hello {self.name}"
```

---

### Type Hints & Union Types

**Modern Python typing (3.10+):**

```python
# Union types with | operator (Python 3.10+)
def process(value: str | int | None) -> str | None:
    ...

# Generic types without importing from typing
def get_items() -> list[dict[str, Any]]:
    ...

# Literal types for exact values
from typing import Literal
mode: Literal["supervisor", "router"] = "supervisor"
```

**Union type for events:**

```python
# bedsheet/events.py
from typing import Union

# All possible event types
Event = Union[
    ThinkingEvent,
    TextTokenEvent,
    ToolCallEvent,
    ToolResultEvent,
    CompletionEvent,
    ErrorEvent,
    RoutingEvent,
    DelegationEvent,
    CollaboratorStartEvent,
    CollaboratorEvent,
    CollaboratorCompleteEvent,
]

# Usage with isinstance for type narrowing
async for event in agent.invoke(...):
    if isinstance(event, ToolCallEvent):
        # Type checker knows event.tool_name exists here
        print(event.tool_name)
    elif isinstance(event, CompletionEvent):
        # Type checker knows event.response exists here
        print(event.response)
```

**Pattern matching (Python 3.10+):**

```python
# Alternative to isinstance chains
match event:
    case ToolCallEvent(tool_name=name, tool_input=args):
        print(f"Calling {name} with {args}")
    case CompletionEvent(response=text):
        print(f"Done: {text}")
    case _:
        pass  # Other events
```

---

## Async Programming

### Async/Await Basics

**What it is:** Cooperative multitasking. Code voluntarily yields control at `await` points, allowing other tasks to run.

**Key insight:** Async is about **concurrency** (interleaving tasks), not **parallelism** (simultaneous execution). It's ideal for I/O-bound operations like API calls.

```python
import asyncio

async def fetch_data(url: str) -> dict:
    """An async function (coroutine)."""
    # await pauses this function, lets others run
    response = await http_client.get(url)
    return response.json()

async def main():
    # Sequential - one after another
    data1 = await fetch_data("url1")  # Wait for completion
    data2 = await fetch_data("url2")  # Then this runs

    # Concurrent - interleaved execution
    data1, data2 = await asyncio.gather(
        fetch_data("url1"),
        fetch_data("url2"),
    )  # Both run "at the same time"

# Run the async code
asyncio.run(main())
```

**Visual: Sequential vs Concurrent**

```
Sequential:
Task1: [====WAITING====]
Task2:                   [====WAITING====]
Time:  |----------------|----------------|
       0s               1s               2s

Concurrent (asyncio.gather):
Task1: [====WAITING====]
Task2: [====WAITING====]
Time:  |----------------|
       0s               1s  (half the time!)
```

---

### AsyncIterator & Streaming

**What it is:** An async version of iterators. Instead of `__iter__` and `__next__`, you implement `__aiter__` and `__anext__`.

**Why use it:** Perfect for streaming data - yields items as they become available without loading everything into memory.

```python
# bedsheet/agent.py
from typing import AsyncIterator

class Agent:
    async def invoke(
        self,
        session_id: str,
        input_text: str,
        stream: bool = False,
    ) -> AsyncIterator[Event]:  # Returns an async iterator
        """Invoke agent, yielding events as they occur."""

        # yield makes this an async generator
        yield ToolCallEvent(...)  # Event 1

        # Can do async operations between yields
        result = await self.execute_tool(...)

        yield ToolResultEvent(...)  # Event 2
        yield CompletionEvent(...)  # Event 3

# Consumption with async for
async for event in agent.invoke("session", "hello"):
    print(event)  # Processes each event as it arrives
```

**How async generators work internally:**

```python
async def my_generator() -> AsyncIterator[int]:
    yield 1
    await asyncio.sleep(0.1)
    yield 2
    await asyncio.sleep(0.1)
    yield 3

# Equivalent to:
class MyGenerator:
    def __init__(self):
        self.state = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        self.state += 1
        if self.state > 3:
            raise StopAsyncIteration
        if self.state > 1:
            await asyncio.sleep(0.1)
        return self.state
```

**Streaming from LLM:**

```python
# bedsheet/llm/anthropic.py
async def chat_stream(self, messages, system, tools=None) -> AsyncIterator[str | LLMResponse]:
    """Stream tokens from Claude."""

    # Anthropic SDK provides async context manager for streaming
    async with self._client.messages.stream(**kwargs) as stream:
        # Yields tokens as they arrive from the API
        async for text in stream.text_stream:
            yield text  # Each token (word/character)

        # After streaming completes, get final message for tool calls
        final = await stream.get_final_message()
        yield self._parse_response(final)
```

---

### Parallel Execution with asyncio.gather

**What it is:** Run multiple coroutines concurrently and wait for all to complete.

**Key pattern in Bedsheet:** Parallel tool execution and parallel agent delegation.

```python
# bedsheet/supervisor.py - Parallel delegation
async def _handle_parallel_delegation(self, delegations, session_id, stream):
    """Execute multiple delegations in parallel."""

    async def run_delegation(d):
        """Wrapper to run one delegation and collect its events."""
        agent_name = d["agent_name"]
        task = d["task"]
        events = []
        async for event in self._execute_single_delegation(
            agent_name, task, session_id, stream=stream
        ):
            events.append(event)
        return agent_name, events

    # Create tasks for all delegations
    tasks = [run_delegation(d) for d in delegations]

    # Run ALL tasks concurrently, wait for ALL to complete
    results = await asyncio.gather(*tasks)

    # results = [(agent1, events1), (agent2, events2), ...]
    return results
```

**Visual: Parallel Delegation**

```
Without gather (sequential):
MarketAnalyst:  [=======WORKING=======]
NewsResearcher:                         [=======WORKING=======]
Total time:     |---------------------|---------------------|
                0s                    10s                   20s

With asyncio.gather (parallel):
MarketAnalyst:  [=======WORKING=======]
NewsResearcher: [=======WORKING=======]
Total time:     |---------------------|
                0s                    10s  (half the time!)
```

**Parallel tool execution:**

```python
# bedsheet/agent.py
async def _execute_tools_parallel(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
    """Execute multiple tool calls concurrently."""

    async def execute_one(tc: ToolCall) -> ToolResult:
        try:
            result = await self._call_tool(tc.name, tc.input)
            return ToolResult(call_id=tc.id, result=result)
        except Exception as e:
            return ToolResult(call_id=tc.id, error=str(e))

    # All tools run at the same time
    results = await asyncio.gather(*[execute_one(tc) for tc in tool_calls])
    return results
```

---

## The Decorator Pattern

### @action Decorator

**What it is:** A decorator that registers functions as tools and extracts metadata from them.

**Implementation:**

```python
# bedsheet/action_group.py
class ActionGroup:
    def __init__(self, name: str):
        self.name = name
        self.actions: dict[str, Action] = {}

    def action(
        self,
        name: str,
        description: str,
        parameters: dict | None = None,
    ):
        """Decorator to register a function as an action."""

        def decorator(fn: Callable) -> Callable:
            # Infer schema from type hints if not provided
            schema = parameters if parameters is not None else generate_schema(fn)

            # Store metadata
            self.actions[name] = Action(
                name=name,
                description=description,
                parameters=schema,
                handler=fn,  # The actual function
            )

            return fn  # Return original function unchanged

        return decorator
```

**Usage:**

```python
tools = ActionGroup(name="MarketTools")

@tools.action(name="get_stock_data", description="Get stock price and metrics")
async def get_stock_data(symbol: str) -> dict:
    """The docstring isn't used - description comes from decorator."""
    return {"symbol": symbol, "price": 100.0}

# What happened:
# 1. @tools.action(...) called -> returns decorator function
# 2. decorator(get_stock_data) called -> registers function, returns it
# 3. get_stock_data is now registered in tools.actions["get_stock_data"]
```

**Decorator with arguments pattern:**

```python
# Decorator WITHOUT arguments
def simple_decorator(fn):
    def wrapper(*args, **kwargs):
        print("Before")
        result = fn(*args, **kwargs)
        print("After")
        return result
    return wrapper

@simple_decorator
def my_func():
    pass
# Equivalent to: my_func = simple_decorator(my_func)

# Decorator WITH arguments (what @action uses)
def decorator_with_args(arg1, arg2):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            print(f"Args were: {arg1}, {arg2}")
            return fn(*args, **kwargs)
        return wrapper
    return decorator

@decorator_with_args("hello", "world")
def my_func():
    pass
# Equivalent to: my_func = decorator_with_args("hello", "world")(my_func)
```

---

### Schema Inference from Type Hints

**What it is:** Automatically generate JSON Schema from Python function signatures.

```python
# bedsheet/action_group.py
import inspect
from typing import get_type_hints

def generate_schema(fn: Callable) -> dict:
    """Generate JSON Schema from function type hints."""

    hints = get_type_hints(fn)  # Get type annotations
    sig = inspect.signature(fn)  # Get parameter info

    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        if param_name == "return":
            continue

        param_type = hints.get(param_name, str)

        # Map Python types to JSON Schema types
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }

        json_type = type_mapping.get(param_type, "string")
        properties[param_name] = {"type": json_type}

        # If no default value, it's required
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }
```

**Example:**

```python
async def search_news(query: str, limit: int = 10) -> dict:
    pass

schema = generate_schema(search_news)
# Result:
# {
#     "type": "object",
#     "properties": {
#         "query": {"type": "string"},
#         "limit": {"type": "integer"}
#     },
#     "required": ["query"]  # limit has default, so not required
# }
```

---

## Event-Driven Architecture

### Event Types

**All event types in the system:**

```python
# bedsheet/events.py

@dataclass
class ThinkingEvent:
    """LLM is thinking (extended thinking mode)."""
    content: str
    type: Literal["thinking"] = field(default="thinking", init=False)

@dataclass
class TextTokenEvent:
    """A token arrived from streaming LLM response."""
    token: str
    type: Literal["text_token"] = field(default="text_token", init=False)

@dataclass
class ToolCallEvent:
    """LLM wants to call a tool."""
    tool_name: str
    tool_input: dict[str, Any]
    call_id: str
    type: Literal["tool_call"] = field(default="tool_call", init=False)

@dataclass
class ToolResultEvent:
    """Tool execution completed."""
    call_id: str
    result: Any
    error: str | None = None
    type: Literal["tool_result"] = field(default="tool_result", init=False)

@dataclass
class CompletionEvent:
    """Agent produced final response."""
    response: str
    type: Literal["completion"] = field(default="completion", init=False)

@dataclass
class ErrorEvent:
    """An error occurred."""
    error: str
    recoverable: bool = False
    type: Literal["error"] = field(default="error", init=False)

@dataclass
class DelegationEvent:
    """Supervisor is delegating to agent(s)."""
    delegations: list[dict]  # [{"agent_name": "X", "task": "Y"}, ...]
    type: Literal["delegation"] = field(default="delegation", init=False)

@dataclass
class CollaboratorStartEvent:
    """A collaborator agent is starting."""
    agent_name: str
    task: str
    type: Literal["collaborator_start"] = field(default="collaborator_start", init=False)

@dataclass
class CollaboratorEvent:
    """Wraps any event from a collaborator."""
    agent_name: str
    inner_event: Event  # The wrapped event
    type: Literal["collaborator"] = field(default="collaborator", init=False)

@dataclass
class CollaboratorCompleteEvent:
    """A collaborator agent finished."""
    agent_name: str
    response: str
    type: Literal["collaborator_complete"] = field(default="collaborator_complete", init=False)

@dataclass
class RoutingEvent:
    """Router mode: supervisor picked an agent."""
    agent_name: str
    task: str
    type: Literal["routing"] = field(default="routing", init=False)
```

---

### Event Flow

**Single Agent Flow:**

```
User Input
    │
    ▼
┌─────────────────────────────────────────────┐
│                Agent.invoke()                │
│                                              │
│  ┌─────────────────────────────────────┐    │
│  │         LLM Call (streaming)         │    │
│  │  ┌─────────────────────────────────┐ │    │
│  │  │ yield TextTokenEvent("Hello")   │ │    │
│  │  │ yield TextTokenEvent(" world")  │ │    │
│  │  │ ...                             │ │    │
│  │  └─────────────────────────────────┘ │    │
│  │         OR                           │    │
│  │  ┌─────────────────────────────────┐ │    │
│  │  │ Tool calls requested            │ │    │
│  │  └─────────────────────────────────┘ │    │
│  └─────────────────────────────────────┘    │
│                     │                        │
│         ┌───────────┴───────────┐           │
│         ▼                       ▼           │
│  ┌─────────────┐         ┌─────────────┐   │
│  │ Tool Call 1 │         │ Tool Call 2 │   │
│  │   (async)   │         │   (async)   │   │
│  └─────────────┘         └─────────────┘   │
│         │                       │           │
│         ▼                       ▼           │
│  yield ToolCallEvent    yield ToolCallEvent │
│  yield ToolResultEvent  yield ToolResultEvent
│                     │                        │
│                     ▼                        │
│            ┌──────────────┐                 │
│            │ Next LLM Call │                 │
│            │  (loop back)  │                 │
│            └──────────────┘                 │
│                     │                        │
│                     ▼                        │
│          yield CompletionEvent               │
└─────────────────────────────────────────────┘
```

**Supervisor Flow with Parallel Delegation:**

```
User Input
    │
    ▼
┌──────────────────────────────────────────────────────┐
│                  Supervisor.invoke()                  │
│                                                       │
│  ┌─────────────────────────────────────────────┐     │
│  │              LLM Call                        │     │
│  │  "Delegate to MarketAnalyst AND NewsResearcher"   │
│  └─────────────────────────────────────────────┘     │
│                       │                               │
│                       ▼                               │
│            yield DelegationEvent                      │
│                       │                               │
│         ┌─────────────┴─────────────┐                │
│         ▼                           ▼                │
│  ┌─────────────────┐      ┌─────────────────┐       │
│  │  MarketAnalyst  │      │  NewsResearcher │       │
│  │   (parallel)    │      │    (parallel)   │       │
│  └────────┬────────┘      └────────┬────────┘       │
│           │                        │                 │
│  yield CollaboratorStartEvent  yield CollaboratorStartEvent
│           │                        │                 │
│  ┌────────▼────────┐      ┌────────▼────────┐       │
│  │ Agent.invoke()  │      │ Agent.invoke()  │       │
│  │                 │      │                 │       │
│  │ TextTokenEvent ─┼──────┼─ TextTokenEvent │       │
│  │ ToolCallEvent  ─┼──────┼─ ToolCallEvent  │       │
│  │ ToolResultEvent─┼──────┼─ ToolResultEvent│       │
│  │ CompletionEvent─┼──────┼─ CompletionEvent│       │
│  └────────┬────────┘      └────────┬────────┘       │
│           │                        │                 │
│           └──────────┬─────────────┘                │
│                      ▼                               │
│  yield CollaboratorCompleteEvent (for each)          │
│                      │                               │
│                      ▼                               │
│  ┌─────────────────────────────────────────────┐    │
│  │         Supervisor LLM Call                  │    │
│  │   (synthesize collaborator results)          │    │
│  └─────────────────────────────────────────────┘    │
│                      │                               │
│                      ▼                               │
│           yield TextTokenEvent (streaming)           │
│           yield CompletionEvent (final)              │
└──────────────────────────────────────────────────────┘
```

---

## Multi-Agent Orchestration

### Supervisor Pattern

**Supervisor extends Agent:**

```python
# bedsheet/supervisor.py
class Supervisor(Agent):
    """An agent that can coordinate other agents."""

    def __init__(
        self,
        name: str,
        instruction: str,
        model_client: LLMClient,
        collaborators: list[Agent],  # Child agents
        collaboration_mode: Literal["supervisor", "router"] = "supervisor",
        **kwargs,
    ):
        super().__init__(name=name, instruction=instruction, model_client=model_client, **kwargs)

        # Store collaborators by name for lookup
        self.collaborators = {agent.name: agent for agent in collaborators}
        self.collaboration_mode = collaboration_mode

        # Register built-in delegate tool
        self._register_delegate_action()
```

**Two collaboration modes:**

| Mode | Behavior | Use Case |
|------|----------|----------|
| `supervisor` | Delegates, collects results, synthesizes | Complex analysis needing multiple perspectives |
| `router` | Picks one agent, hands off entirely | Simple routing to specialists |

**The delegate tool:**

```python
def _register_delegate_action(self):
    """Register the built-in delegate action."""

    delegate_group = ActionGroup(name="DelegateTools")

    @delegate_group.action(
        name="delegate",
        description="Delegate tasks to collaborator agents",
        parameters={
            "type": "object",
            "properties": {
                "delegations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "agent_name": {"type": "string"},
                            "task": {"type": "string"},
                        },
                        "required": ["agent_name", "task"],
                    },
                },
            },
            "required": ["delegations"],
        },
    )
    async def delegate(delegations: list) -> str:
        # This is a placeholder - actual delegation handled specially
        return "Delegation handled"

    self.add_action_group(delegate_group)
```

---

### Parallel Delegation

**How parallel delegation works:**

```python
# bedsheet/supervisor.py

async def _execute_single_delegation(
    self,
    agent_name: str,
    task: str,
    session_id: str,
    stream: bool = False,
) -> AsyncIterator[Event]:
    """Execute one delegation and yield its events."""

    collaborator = self.collaborators.get(agent_name)
    if collaborator is None:
        yield ErrorEvent(error=f"Unknown agent: {agent_name}")
        return

    yield CollaboratorStartEvent(agent_name=agent_name, task=task)

    # Invoke the collaborator, wrapping all its events
    result = ""
    async for event in collaborator.invoke(
        session_id=f"{session_id}:{agent_name}",
        input_text=task,
        stream=stream,
    ):
        # Wrap every event from the collaborator
        yield CollaboratorEvent(agent_name=agent_name, inner_event=event)

        if isinstance(event, CompletionEvent):
            result = event.response

    yield CollaboratorCompleteEvent(agent_name=agent_name, response=result)


async def _handle_parallel_delegations(
    self,
    delegations: list[dict],
    session_id: str,
    stream: bool,
) -> list[tuple[str, list[Event]]]:
    """Execute multiple delegations in parallel."""

    async def run_one(d: dict) -> tuple[str, list[Event]]:
        events = []
        async for event in self._execute_single_delegation(
            d["agent_name"], d["task"], session_id, stream
        ):
            events.append(event)
        return d["agent_name"], events

    # asyncio.gather runs all delegations concurrently
    results = await asyncio.gather(*[run_one(d) for d in delegations])
    return results
```

---

## LLM Integration

### Non-Streaming vs Streaming

**Non-streaming (original):**

```python
# bedsheet/llm/anthropic.py
async def chat(self, messages, system, tools=None) -> LLMResponse:
    """Wait for complete response."""

    response = await self._client.messages.create(
        model=self.model,
        max_tokens=self.max_tokens,
        system=system,
        messages=self._convert_messages(messages),
        tools=self._format_tools(tools) if tools else None,
    )

    return self._parse_response(response)
```

**Streaming (new):**

```python
async def chat_stream(self, messages, system, tools=None) -> AsyncIterator[str | LLMResponse]:
    """Stream tokens as they arrive."""

    # Use stream() instead of create()
    async with self._client.messages.stream(
        model=self.model,
        max_tokens=self.max_tokens,
        system=system,
        messages=self._convert_messages(messages),
        tools=self._format_tools(tools) if tools else None,
    ) as stream:
        # Yield each token as it arrives
        async for text in stream.text_stream:
            yield text  # "Hello" -> "Hello " -> "Hello world" etc.

        # After streaming, get the full message for tool calls
        final = await stream.get_final_message()
        yield self._parse_response(final)
```

**Consumption in Agent:**

```python
async def invoke(self, session_id, input_text, stream=False) -> AsyncIterator[Event]:
    # ... setup ...

    if stream and hasattr(self.model_client, 'chat_stream'):
        # Streaming path
        response = None
        async for chunk in self.model_client.chat_stream(messages, system, tools):
            if isinstance(chunk, str):
                yield TextTokenEvent(token=chunk)  # Emit each token
            else:
                response = chunk  # Final LLMResponse
    else:
        # Non-streaming path
        response = await self.model_client.chat(messages, system, tools)

    # Continue with tool handling using response...
```

---

### Tool Calling

**How Claude tool calling works:**

1. You provide tool definitions in the API request
2. Claude responds with `tool_use` blocks if it wants to call tools
3. You execute the tools and send results back
4. Claude continues with more tool calls or a text response

```python
# Request to Claude includes tools:
{
    "tools": [
        {
            "name": "get_stock_data",
            "description": "Get stock price and metrics",
            "input_schema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"}
                },
                "required": ["symbol"]
            }
        }
    ]
}

# Claude's response when it wants to use tools:
{
    "content": [
        {
            "type": "tool_use",
            "id": "call_123",
            "name": "get_stock_data",
            "input": {"symbol": "NVDA"}
        }
    ],
    "stop_reason": "tool_use"
}

# You execute the tool and send result back:
{
    "role": "user",
    "content": [
        {
            "type": "tool_result",
            "tool_use_id": "call_123",
            "content": "{\"symbol\": \"NVDA\", \"price\": 875.50}"
        }
    ]
}
```

**Bedsheet's tool execution loop:**

```python
# bedsheet/agent.py (simplified)
async def invoke(self, session_id, input_text, stream=False):
    # Add user message to memory
    await self.memory.add_message(session_id, Message(role="user", content=input_text))

    for iteration in range(self.max_iterations):
        messages = await self.memory.get_messages(session_id)
        tools = self._get_tool_definitions()

        # Call LLM
        response = await self.model_client.chat(messages, system_prompt, tools)

        if response.text and not response.tool_calls:
            # Final text response - we're done
            yield CompletionEvent(response=response.text)
            return

        if response.tool_calls:
            # Execute all tool calls in parallel
            for tc in response.tool_calls:
                yield ToolCallEvent(tool_name=tc.name, tool_input=tc.input, call_id=tc.id)

            results = await asyncio.gather(*[
                self._execute_tool(tc) for tc in response.tool_calls
            ])

            for result in results:
                yield ToolResultEvent(call_id=result.call_id, result=result.result)

            # Add results to memory and loop back for next LLM call
            await self._add_tool_results_to_memory(session_id, results)
```

---

## Testing Patterns

### MockLLMClient

**Purpose:** Test agents without making real API calls.

```python
# bedsheet/testing.py
@dataclass
class MockResponse:
    """A pre-programmed response from the mock LLM."""
    text: str | None = None
    tool_calls: list[ToolCall] | None = None


class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self, responses: list[MockResponse]):
        self.responses = list(responses)
        self.call_count = 0

    def _get_next_response(self) -> MockResponse:
        """Get and remove the next response from the queue."""
        if not self.responses:
            raise RuntimeError("MockLLMClient exhausted - no more responses")
        self.call_count += 1
        return self.responses.pop(0)

    async def chat(self, messages, system, tools=None) -> LLMResponse:
        """Return the next pre-programmed response."""
        response = self._get_next_response()
        return LLMResponse(
            text=response.text,
            tool_calls=response.tool_calls or [],
            stop_reason="end_turn" if response.text else "tool_use",
        )

    async def chat_stream(self, messages, system, tools=None) -> AsyncIterator[str | LLMResponse]:
        """Stream the next pre-programmed response."""
        response = self._get_next_response()

        # Yield text word by word
        if response.text:
            words = response.text.split(' ')
            for i, word in enumerate(words):
                if i > 0:
                    yield ' '
                yield word

        # Yield final response
        yield LLMResponse(
            text=response.text,
            tool_calls=response.tool_calls or [],
            stop_reason="end_turn",
        )
```

**Usage in tests:**

```python
# tests/test_agent.py
@pytest.mark.asyncio
async def test_agent_calls_tool_and_returns_result():
    mock = MockLLMClient(responses=[
        # First response: LLM wants to call a tool
        MockResponse(tool_calls=[
            ToolCall(id="1", name="get_weather", input={"city": "NYC"})
        ]),
        # Second response: LLM synthesizes result
        MockResponse(text="The weather in NYC is sunny."),
    ])

    tools = ActionGroup(name="Weather")

    @tools.action(name="get_weather", description="Get weather")
    async def get_weather(city: str) -> str:
        return f"Sunny in {city}"

    agent = Agent(
        name="WeatherBot",
        instruction="Help with weather",
        model_client=mock,
    )
    agent.add_action_group(tools)

    events = []
    async for event in agent.invoke("test", "What's the weather in NYC?"):
        events.append(event)

    # Verify event sequence
    assert isinstance(events[0], ToolCallEvent)
    assert events[0].tool_name == "get_weather"

    assert isinstance(events[1], ToolResultEvent)
    assert "Sunny" in events[1].result

    assert isinstance(events[2], CompletionEvent)
    assert "sunny" in events[2].response.lower()
```

---

### Async Test Fixtures

**pytest-asyncio setup:**

```python
# tests/conftest.py or in test file
import pytest

# Mark all tests in file as async
pytestmark = pytest.mark.asyncio

# Or mark individual tests
@pytest.mark.asyncio
async def test_something():
    result = await some_async_function()
    assert result == expected
```

**Fixtures for common setup:**

```python
@pytest.fixture
def mock_client():
    """Fixture providing a mock LLM client."""
    return MockLLMClient(responses=[
        MockResponse(text="Hello!"),
    ])

@pytest.fixture
def sample_agent(mock_client):
    """Fixture providing a configured agent."""
    return Agent(
        name="TestAgent",
        instruction="You are a test agent.",
        model_client=mock_client,
    )

@pytest.mark.asyncio
async def test_agent_responds(sample_agent):
    events = [e async for e in sample_agent.invoke("s1", "Hi")]
    assert any(isinstance(e, CompletionEvent) for e in events)
```

---

## Summary

### Key Patterns Recap

| Pattern | Where Used | Why |
|---------|------------|-----|
| **Protocol** | `LLMClient`, `Memory` | Loose coupling, easy to swap implementations |
| **Dataclass** | All events, `ToolCall`, `LLMResponse` | Clean data structures with less boilerplate |
| **AsyncIterator** | `invoke()` methods | Stream events as they happen |
| **asyncio.gather** | Tool execution, parallel delegation | Concurrent I/O operations |
| **Decorator** | `@action` | Register functions with metadata |
| **Type hints** | Everywhere | Self-documenting, IDE support, type checking |

### File Reference

| File | Purpose |
|------|---------|
| `agent.py` | Single agent with ReAct loop |
| `supervisor.py` | Multi-agent coordinator |
| `action_group.py` | Tool definitions and @action decorator |
| `events.py` | All event dataclasses |
| `llm/base.py` | LLMClient protocol and types |
| `llm/anthropic.py` | Claude integration |
| `memory/base.py` | Memory protocol |
| `memory/in_memory.py` | Dict-based memory |
| `testing.py` | MockLLMClient for tests |

---

## Further Reading

- [Python Protocols (PEP 544)](https://peps.python.org/pep-0544/)
- [Dataclasses (PEP 557)](https://peps.python.org/pep-0557/)
- [AsyncIO Documentation](https://docs.python.org/3/library/asyncio.html)
- [Type Hints (PEP 484)](https://peps.python.org/pep-0484/)
- [Anthropic Claude API](https://docs.anthropic.com/claude/reference/messages_post)
