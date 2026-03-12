"""LLM recording and replay for deterministic agent runs."""

import hashlib
import json
import logging
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
        self._write(
            {
                "type": "llm_call",
                "seq": self._seq,
                "agent": self._agent_name,
                "messages_hash": _messages_hash(messages),
                "system_hash": _hash(system),
                "tools": [t.name for t in tools] if tools else [],
            }
        )

    def _record_response(self, response: LLMResponse) -> None:
        self._write(
            {
                "type": "llm_response",
                "seq": self._seq,
                "text": response.text,
                "tool_calls": _serialize_tool_calls(response.tool_calls),
                "stop_reason": response.stop_reason,
                "thinking": response.thinking,
                "parsed_output": _serialize_parsed_output(response.parsed_output),
            }
        )

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
        async for chunk in self._client.chat_stream(
            messages, system, tools, output_schema
        ):
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
                        recorder._write(
                            {
                                "type": "tool_result",
                                "seq": recorder._seq - 1,
                                "call_id": "",
                                "name": act.name,
                                "result": result
                                if isinstance(result, str)
                                else json.dumps(result),
                                "error": None,
                            }
                        )
                        return result
                    except Exception as e:
                        recorder._write(
                            {
                                "type": "tool_result",
                                "seq": recorder._seq - 1,
                                "call_id": "",
                                "name": act.name,
                                "result": None,
                                "error": str(e),
                            }
                        )
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
