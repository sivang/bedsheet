# Design: Annotated Support in generate_schema

## Problem

`generate_schema` introspects function signatures to build JSON tool schemas automatically, but doesn't support per-parameter descriptions. This forces agent authors to write verbose manual `parameters={...}` dicts, bypassing introspection entirely.

## Solution

Support `typing.Annotated` to carry descriptions:

```python
from typing import Annotated

@tools.action("add_appointment", "Add a new appointment")
async def add_appointment(
    title: Annotated[str, "Appointment title"],
    date: Annotated[str, "Date (YYYY-MM-DD)"],
    time: Annotated[str, "Time (HH:MM)"] = "09:00",
) -> str:
```

## Changes

### 1. `bedsheet/action_group.py` — enhance `generate_schema`

- Import `get_type_hints`, `get_origin`, `get_args` from `typing`
- When a hint is `Annotated[T, ...]`: use `T` for type mapping, first `str` metadata as `"description"`
- Plain types unchanged — full backward compat

### 2. `bedsheet/__init__.py` — re-export `Annotated`

Convenience export so users can `from bedsheet import Annotated`.

### 3. Sentinel agent cleanup

Remove manual `parameters={...}` from all `@action()` decorators in:
- `scheduler.py`
- `sentinel_commander.py`
- `behavior_sentinel.py`
- `supply_chain_sentinel.py`
- `web_researcher.py`
- `skill_acquirer.py`

Replace with `Annotated` hints. Rename mismatched params (e.g. `time_str` -> `time`).

### 4. Tests in `tests/test_action_group.py`

- `Annotated[str, "desc"]` -> `{"type": "string", "description": "desc"}`
- `Annotated[int, "desc"]` with default value
- Mixed annotated and plain params
- Non-string metadata in `Annotated` ignored gracefully

## What doesn't change

- `parameters=` kwarg still works as escape hatch
- Plain type hints without `Annotated` work identically
- No new dependencies (Annotated is stdlib since 3.9+)
