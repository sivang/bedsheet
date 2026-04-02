# Annotated Schema Enhancement — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `generate_schema` support `Annotated[T, "description"]` so agent tools get per-parameter descriptions without manual JSON schemas.

**Architecture:** Enhance the single `generate_schema()` function to unwrap `Annotated` types, then remove all manual `parameters=` dicts from sentinel agents and replace with `Annotated` type hints.

**Tech Stack:** Python 3.11+ `typing.Annotated`, `typing.get_type_hints`, `typing.get_origin`, `typing.get_args`

---

### Task 1: Write failing tests for Annotated support

**Files:**
- Modify: `tests/test_action_group.py` (append new tests after line 143)

**Step 1: Write the failing tests**

Add these tests at the end of `tests/test_action_group.py`:

```python
from typing import Annotated


def test_generate_schema_annotated_string():
    def fn(title: Annotated[str, "Appointment title"]) -> str:
        pass

    schema = generate_schema(fn)
    assert schema["properties"]["title"] == {
        "type": "string",
        "description": "Appointment title",
    }
    assert schema["required"] == ["title"]


def test_generate_schema_annotated_with_default():
    def fn(time: Annotated[str, "Time (HH:MM)"] = "09:00") -> str:
        pass

    schema = generate_schema(fn)
    assert schema["properties"]["time"] == {
        "type": "string",
        "description": "Time (HH:MM)",
        "default": "09:00",
    }
    assert "time" not in schema["required"]


def test_generate_schema_annotated_int():
    def fn(minutes: Annotated[int, "Time window in minutes"] = 5) -> str:
        pass

    schema = generate_schema(fn)
    assert schema["properties"]["minutes"] == {
        "type": "integer",
        "description": "Time window in minutes",
        "default": 5,
    }


def test_generate_schema_mixed_annotated_and_plain():
    def fn(name: str, age: Annotated[int, "Age in years"], active: bool = True) -> str:
        pass

    schema = generate_schema(fn)
    assert schema["properties"]["name"] == {"type": "string"}
    assert schema["properties"]["age"] == {
        "type": "integer",
        "description": "Age in years",
    }
    assert schema["properties"]["active"] == {"type": "boolean", "default": True}
    assert set(schema["required"]) == {"name", "age"}


def test_generate_schema_annotated_non_string_metadata_ignored():
    def fn(value: Annotated[str, 42, {"extra": True}]) -> str:
        pass

    schema = generate_schema(fn)
    assert schema["properties"]["value"] == {"type": "string"}
    assert "description" not in schema["properties"]["value"]


def test_generate_schema_annotated_picks_first_string():
    def fn(value: Annotated[str, "First desc", "Second desc"]) -> str:
        pass

    schema = generate_schema(fn)
    assert schema["properties"]["value"]["description"] == "First desc"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_action_group.py -v -k "annotated"`
Expected: FAIL — `Annotated[str, ...]` is not in TYPE_MAP, raises `TypeError`

**Step 3: Commit**

```bash
git add tests/test_action_group.py
git commit -m "test: add failing tests for Annotated support in generate_schema"
```

---

### Task 2: Implement Annotated support in generate_schema

**Files:**
- Modify: `bedsheet/action_group.py:1-56`

**Step 1: Update imports and generate_schema**

Replace the entire top section of `bedsheet/action_group.py` (lines 1-56) with:

```python
"""ActionGroup and Action system for defining agent tools."""

import inspect
from dataclasses import dataclass
from typing import Annotated, Any, Awaitable, Callable, get_args, get_origin


from bedsheet.llm.base import ToolDefinition


# Type mapping from Python types to JSON Schema types
TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def generate_schema(fn: Callable) -> dict[str, Any]:
    """Generate a JSON Schema from a function's type hints.

    Supports typing.Annotated for per-parameter descriptions:
        def fn(name: Annotated[str, "User's full name"]) -> str:

    The first str metadata in Annotated is used as the JSON Schema
    "description". Non-string metadata is ignored.
    """
    sig = inspect.signature(fn)
    hints = fn.__annotations__

    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue

        type_hint = hints.get(name, str)
        description: str | None = None

        # Unwrap Annotated[T, ...] — extract base type and description
        if get_origin(type_hint) is Annotated:
            args = get_args(type_hint)
            type_hint = args[0]  # The base type (e.g. str, int)
            # First str in metadata is the description
            for meta in args[1:]:
                if isinstance(meta, str):
                    description = meta
                    break

        if type_hint not in TYPE_MAP:
            raise TypeError(
                f"Unsupported type {type_hint} for parameter '{name}'. "
                f"Supported types: {list(TYPE_MAP.keys())}"
            )

        json_type = TYPE_MAP[type_hint]
        prop: dict[str, Any] = {"type": json_type}

        if description is not None:
            prop["description"] = description

        # Check if parameter has a default value
        if param.default is inspect.Parameter.empty:
            required.append(name)
        else:
            prop["default"] = param.default

        properties[name] = prop

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }
```

**Step 2: Run the Annotated tests**

Run: `pytest tests/test_action_group.py -v -k "annotated"`
Expected: All 6 new tests PASS

**Step 3: Run all action_group tests**

Run: `pytest tests/test_action_group.py -v`
Expected: All tests PASS (existing + new)

**Step 4: Commit**

```bash
git add bedsheet/action_group.py
git commit -m "feat: support Annotated types in generate_schema for parameter descriptions"
```

---

### Task 3: Re-export Annotated from bedsheet

**Files:**
- Modify: `bedsheet/__init__.py`

**Step 1: Add Annotated to exports**

Add `Annotated` to the imports and `__all__`:

```python
"""Bedsheet Agents - Cloud-agnostic agent orchestration."""

from typing import Annotated

from bedsheet.agent import Agent
from bedsheet.action_group import ActionGroup
from bedsheet.supervisor import Supervisor
from bedsheet.sense import SenseMixin, SenseNetwork

__all__ = ["Agent", "ActionGroup", "Annotated", "Supervisor", "SenseMixin", "SenseNetwork"]
```

**Step 2: Verify import works**

Run: `python -c "from bedsheet import Annotated; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add bedsheet/__init__.py
git commit -m "feat: re-export Annotated from bedsheet for convenience"
```

---

### Task 4: Clean up scheduler.py

**Files:**
- Modify: `examples/agent-sentinel/agents/scheduler.py`

**Step 1: Replace manual schemas with Annotated hints**

Update imports — add at line 14 after the bedsheet imports:
```python
from bedsheet import Agent, ActionGroup, SenseMixin
```
becomes:
```python
from bedsheet import Agent, ActionGroup, Annotated, SenseMixin
```

Replace `add_appointment` (lines 87-108):
```python
@scheduler_tools.action("add_appointment", "Add a new appointment to the calendar")
async def add_appointment(
    title: Annotated[str, "Appointment title"],
    date: Annotated[str, "Date (YYYY-MM-DD)"],
    time: Annotated[str, "Time (HH:MM)"] = "09:00",
) -> str:
    response = await gateway_request(
        _agent,
        action="add_appointment",
        params={"title": title, "date": date, "time": time},
    )
    if response["verdict"] != "approved":
        return f"Action denied: {response['reason']}"
    return response["result"]
```

Replace `delete_appointment` (lines 111-133):
```python
@scheduler_tools.action("delete_appointment", "Delete an appointment by ID")
async def delete_appointment(
    appointment_id: Annotated[str, "Appointment ID to delete"],
) -> str:
    response = await gateway_request(
        _agent,
        action="delete_appointment",
        params={"appointment_id": appointment_id},
    )
    if response["verdict"] != "approved":
        return f"Action denied: {response['reason']}"
    return response["result"]
```

Note: `time_str` renamed to `time`. Update `params=` dict accordingly (was `"time": time_str`, now `"time": time`).

**Step 2: Run full test suite to check nothing breaks**

Run: `pytest tests/ -v --ignore=tests/integration`
Expected: All 265 tests PASS

**Step 3: Commit**

```bash
git add examples/agent-sentinel/agents/scheduler.py
git commit -m "refactor: use Annotated introspection in scheduler tools"
```

---

### Task 5: Clean up web_researcher.py

**Files:**
- Modify: `examples/agent-sentinel/agents/web_researcher.py`

**Step 1: Replace manual schema with Annotated hint**

Update import line 14:
```python
from bedsheet import Agent, ActionGroup, Annotated, SenseMixin
```

Replace `search_web` (lines 75-94):
```python
@research_tools.action("search_web", "Search the web using DuckDuckGo")
async def search_web(query: Annotated[str, "Search query"]) -> str:
    response = await gateway_request(
        _agent,
        action="search_web",
        params={"query": query},
    )
    if response["verdict"] != "approved":
        return f"Action denied: {response['reason']}"
    return response["result"]
```

**Step 2: Run tests**

Run: `pytest tests/ -v --ignore=tests/integration`
Expected: All PASS

**Step 3: Commit**

```bash
git add examples/agent-sentinel/agents/web_researcher.py
git commit -m "refactor: use Annotated introspection in web_researcher tools"
```

---

### Task 6: Clean up skill_acquirer.py

**Files:**
- Modify: `examples/agent-sentinel/agents/skill_acquirer.py`

**Step 1: Replace manual schema with Annotated hint**

Update import line 15:
```python
from bedsheet import Agent, ActionGroup, Annotated, SenseMixin
```

Replace `install_skill` (lines 93-133):
```python
@skill_tools.action("install_skill", "Install a skill from ClawHub to the local skills directory")
async def install_skill(
    skill_name: Annotated[str, "Skill filename (e.g. weather_lookup.py)"],
) -> str:
    response = await gateway_request(
        _agent,
        action="install_skill",
        params={"skill_name": skill_name},
    )
    if response["verdict"] != "approved":
        return f"Action denied: {response['reason']}"

    result = response["result"]

    # Gateway returns JSON with file content for approved installs
    try:
        install_data = json.loads(result)
        if install_data.get("installed"):
            os.makedirs(_INSTALLED_DIR, exist_ok=True)
            dest = os.path.join(_INSTALLED_DIR, install_data["skill_name"])
            with open(dest, "w") as f:
                f.write(install_data["content"])
            return (
                f"Installed '{install_data['skill_name']}' "
                f"(SHA-256 verified: {install_data['sha256']}...)"
            )
    except (json.JSONDecodeError, KeyError):
        pass

    return result
```

**Step 2: Run tests**

Run: `pytest tests/ -v --ignore=tests/integration`
Expected: All PASS

**Step 3: Commit**

```bash
git add examples/agent-sentinel/agents/skill_acquirer.py
git commit -m "refactor: use Annotated introspection in skill_acquirer tools"
```

---

### Task 7: Clean up behavior_sentinel.py

**Files:**
- Modify: `examples/agent-sentinel/agents/behavior_sentinel.py`

**Step 1: Replace manual schemas with Annotated hints**

Update import line 11:
```python
from bedsheet import Agent, ActionGroup, Annotated, SenseMixin
```

Replace `check_activity_log` (lines 32-64):
```python
@behavior_tools.action(
    "check_activity_log",
    "Query the Action Gateway ledger for actions per agent",
)
async def check_activity_log(
    minutes: Annotated[int, "Time window in minutes"] = 5,
) -> str:
```
(function body unchanged)

Replace `check_output_rate` (lines 67-92):
```python
@behavior_tools.action(
    "check_output_rate",
    "Get the actions-per-minute rate for a specific agent",
)
async def check_output_rate(
    agent_name: Annotated[str, "Name of the agent to check"],
) -> str:
```
(function body unchanged)

**Step 2: Run tests**

Run: `pytest tests/ -v --ignore=tests/integration`
Expected: All PASS

**Step 3: Commit**

```bash
git add examples/agent-sentinel/agents/behavior_sentinel.py
git commit -m "refactor: use Annotated introspection in behavior_sentinel tools"
```

---

### Task 8: Clean up supply_chain_sentinel.py

**Files:**
- Modify: `examples/agent-sentinel/agents/supply_chain_sentinel.py`

**Step 1: Replace manual schema with Annotated hint**

Update import line — add Annotated:
```python
from bedsheet import Agent, ActionGroup, Annotated, SenseMixin
```

Replace `verify_skill_integrity` (lines 103-131):
```python
@supply_chain_tools.action(
    "verify_skill_integrity",
    "Verify a specific installed skill's hash against the registry",
)
async def verify_skill_integrity(
    skill_name: Annotated[str, "Skill filename to verify"],
) -> str:
```
(function body unchanged)

**Step 2: Run tests**

Run: `pytest tests/ -v --ignore=tests/integration`
Expected: All PASS

**Step 3: Commit**

```bash
git add examples/agent-sentinel/agents/supply_chain_sentinel.py
git commit -m "refactor: use Annotated introspection in supply_chain_sentinel tools"
```

---

### Task 9: Clean up sentinel_commander.py

**Files:**
- Modify: `examples/agent-sentinel/agents/sentinel_commander.py`

**Step 1: Replace manual schemas with Annotated hints**

Update import line 14:
```python
from bedsheet import Agent, ActionGroup, Annotated, SenseMixin
```

Replace `request_remote_agent` (lines 38-59):
```python
@commander_tools.action(
    "request_remote_agent",
    "Send a task to a remote agent and wait for its response",
)
async def request_remote_agent(
    agent_name: Annotated[str, "Name of the remote agent"],
    task: Annotated[str, "Task description for the agent"],
) -> str:
```
(function body unchanged)

Replace `broadcast_alert` (lines 62-86):
```python
@commander_tools.action(
    "broadcast_alert",
    "Broadcast an alert to all agents on the network",
)
async def broadcast_alert(
    severity: Annotated[str, "Alert severity: low, medium, high, critical"],
    message: Annotated[str, "Alert message"],
) -> str:
```
(function body unchanged)

Replace `issue_quarantine` (lines 89-124):
```python
@commander_tools.action(
    "issue_quarantine",
    "Issue a quarantine order for a compromised agent",
)
async def issue_quarantine(
    agent_name: Annotated[str, "Name of the agent to quarantine"],
    reason: Annotated[str, "Reason for quarantine"],
) -> str:
```
(function body unchanged)

**Step 2: Run tests**

Run: `pytest tests/ -v --ignore=tests/integration`
Expected: All PASS

**Step 3: Commit**

```bash
git add examples/agent-sentinel/agents/sentinel_commander.py
git commit -m "refactor: use Annotated introspection in sentinel_commander tools"
```

---

### Task 10: Final verification

**Step 1: Run full test suite**

Run: `pytest tests/ -v --ignore=tests/integration`
Expected: All 265+ tests PASS (6 new tests added)

**Step 2: Spot-check a schema output**

Run:
```python
python -c "
from typing import Annotated
from bedsheet.action_group import generate_schema
import json

def fn(title: Annotated[str, 'Appointment title'], date: str, time: Annotated[str, 'HH:MM'] = '09:00') -> str: pass

print(json.dumps(generate_schema(fn), indent=2))
"
```

Expected output:
```json
{
  "type": "object",
  "properties": {
    "title": {"type": "string", "description": "Appointment title"},
    "date": {"type": "string"},
    "time": {"type": "string", "description": "HH:MM", "default": "09:00"}
  },
  "required": ["title", "date"]
}
```
