"""Fixture for PEP 563 (`from __future__ import annotations`) compatibility test.

When this future import is active, ALL annotations on `add_appointment` are
stored as strings inside `add_appointment.__annotations__`. The naive
`fn.__annotations__["title"]` returns the literal string
`'Annotated[str, "Appointment title"]'` instead of the actual `Annotated` type.

`generate_schema()` must use `typing.get_type_hints(fn, include_extras=True)`
(NOT `fn.__annotations__`) to resolve the strings into real `Annotated` types
and unwrap the description metadata.

This file exists as a fixture so the future import is in scope at module
import time — the bug only manifests in modules that opted into PEP 563.
"""

from __future__ import annotations

from typing import Annotated


def add_appointment(
    title: Annotated[str, "Appointment title"],
    minutes: Annotated[int, "Duration in minutes"] = 30,
) -> str:
    """A tool function defined in a module with PEP 563 enabled."""
    return f"{title} ({minutes}min)"
