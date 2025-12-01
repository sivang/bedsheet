"""ActionGroup and Action system for defining agent tools."""
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

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
    """Generate a JSON Schema from a function's type hints."""
    sig = inspect.signature(fn)
    hints = fn.__annotations__

    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue

        # Get type hint
        type_hint = hints.get(name, str)
        if type_hint not in TYPE_MAP:
            raise TypeError(
                f"Unsupported type {type_hint} for parameter '{name}'. "
                f"Supported types: {list(TYPE_MAP.keys())}"
            )

        json_type = TYPE_MAP[type_hint]
        prop: dict[str, Any] = {"type": json_type}

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


@dataclass
class Action:
    """An action that can be invoked by the agent."""
    name: str
    description: str
    fn: Callable[..., Awaitable[Any]]
    input_schema: dict[str, Any]

    def to_tool_definition(self) -> ToolDefinition:
        """Convert to LLM tool definition."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
        )


class ActionGroup:
    """A group of related actions."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._actions: dict[str, Action] = {}

    def action(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any] | None = None,
    ) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
        """Decorator to register an action."""
        def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
            # Use explicit parameters or infer from function
            schema = parameters if parameters is not None else generate_schema(fn)

            action = Action(
                name=name,
                description=description,
                fn=fn,
                input_schema=schema,
            )
            self._actions[name] = action
            return fn
        return decorator

    def get_action(self, name: str) -> Action | None:
        """Get an action by name."""
        return self._actions.get(name)

    def get_actions(self) -> list[Action]:
        """Get all actions in this group."""
        return list(self._actions.values())

    def get_tool_definitions(self) -> list[ToolDefinition]:
        """Get tool definitions for all actions."""
        return [action.to_tool_definition() for action in self._actions.values()]
