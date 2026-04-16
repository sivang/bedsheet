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
            _log.info("Replay complete — no more recorded responses")
            # Return a synthetic text completion so the agent's ReAct loop
            # exits cleanly via the "text with no tool_calls" branch.
            # Returning text=None with empty tool_calls triggers the agent's
            # empty-response guard ("Model returned an empty response") which
            # is correct for live LLM failures but misleading during replay.
            return LLMResponse(
                text="[Replay complete — no more recorded responses]",
                tool_calls=[],
                stop_reason="end_turn",
            )

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
            words = response.text.split(" ")
            for i, word in enumerate(words):
                if self._delay > 0:
                    await asyncio.sleep(self._delay)
                if i < len(words) - 1:
                    yield word + " "
                else:
                    yield word
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
                        raise RuntimeError(
                            f"ReplayLLMClient: no more recorded results for '{name}'"
                        )
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


def enable_recording(agent: Any, directory: str) -> RecordingLLMClient:
    """Enable recording mode on an agent.

    Wraps the agent's model_client with RecordingLLMClient and
    re-wraps all action groups to record tool results.

    Returns the RecordingLLMClient so the caller can close() it when done.
    Also accessible via agent.model_client after this call.

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
    return recorder


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
