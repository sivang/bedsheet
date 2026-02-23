"""Google Gemini LLM client implementation."""

import asyncio
import logging
import uuid
from typing import Any, AsyncIterator

from bedsheet.llm.base import LLMResponse, OutputSchema, ToolCall, ToolDefinition
from bedsheet.memory.base import Message

try:
    from google import genai
    from google.genai import types as gtypes
except ImportError as e:
    raise ImportError(
        "Gemini client requires the 'google-genai' package. "
        "Install it with: pip install google-genai"
    ) from e


_log = logging.getLogger(__name__)


class GeminiClient:
    """LLM client for Google Gemini models via the Gemini API (AI Studio key or Vertex AI)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-3-flash-preview",
        max_tokens: int = 4096,
        max_retries: int = 5,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self._client = genai.Client(api_key=api_key)

    async def _call_with_retry(
        self, contents: list, config: "gtypes.GenerateContentConfig"
    ) -> Any:
        """Call generate_content with exponential backoff on 429 rate limit errors."""
        delay = 15.0  # gemini-3-flash free tier = 5 RPM, so start at 15s
        for attempt in range(self.max_retries + 1):
            try:
                return await self._client.aio.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
            except Exception as e:
                err_str = str(e)
                is_rate_limit = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
                if is_rate_limit and attempt < self.max_retries:
                    _log.warning(
                        "Rate limited (attempt %d/%d), retrying in %.0fs...",
                        attempt + 1,
                        self.max_retries,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 1.5, 120.0)
                else:
                    raise

    async def chat(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
        output_schema: OutputSchema | None = None,
    ) -> LLMResponse:
        contents = self._convert_messages(messages)
        config = self._build_config(system, tools)
        response = await self._call_with_retry(contents, config)
        return self._parse_response(response)

    async def chat_stream(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
        output_schema: OutputSchema | None = None,
    ) -> AsyncIterator[str | LLMResponse]:
        # Stream text-only turns; fall back to non-streaming when tools are present
        # (avoids partial function-call assembly across chunks)
        if tools:
            response = await self.chat(messages, system, tools, output_schema)
            if response.text:
                yield response.text
            yield response
            return

        contents = self._convert_messages(messages)
        config = self._build_config(system, tools=None)
        async for chunk in await self._client.aio.models.generate_content_stream(
            model=self.model,
            contents=contents,
            config=config,
        ):
            if chunk.text:
                yield chunk.text

        final = await self.chat(messages, system, tools=None)
        yield final

    def _build_config(
        self, system: str, tools: list[ToolDefinition] | None
    ) -> "gtypes.GenerateContentConfig":
        kwargs: dict[str, Any] = {
            "system_instruction": system,
            "max_output_tokens": self.max_tokens,
        }
        if tools:
            kwargs["tools"] = [
                gtypes.Tool(
                    function_declarations=[
                        gtypes.FunctionDeclaration(
                            name=t.name,
                            description=t.description,
                            parameters=t.input_schema,
                        )
                        for t in tools
                    ]
                )
            ]
        return gtypes.GenerateContentConfig(**kwargs)

    def _convert_messages(self, messages: list[Message]) -> list["gtypes.Content"]:
        """Convert bedsheet messages to Gemini Content objects.

        Preserves raw Gemini parts (including thought_signature) when available
        via the _gemini_parts stash on assistant messages with tool calls.
        """
        result: list[gtypes.Content] = []
        for msg in messages:
            if msg.role == "user":
                result.append(
                    gtypes.Content(
                        role="user", parts=[gtypes.Part.from_text(text=msg.content)]
                    )
                )
            elif msg.role == "assistant":
                # Use raw Gemini parts if stashed (preserves thought_signature)
                raw_parts = getattr(msg, "_gemini_parts", None)
                if raw_parts:
                    result.append(gtypes.Content(role="model", parts=raw_parts))
                elif msg.tool_calls:
                    parts = [
                        gtypes.Part.from_function_call(
                            name=tc["name"], args=tc["input"]
                        )
                        for tc in msg.tool_calls
                    ]
                    result.append(gtypes.Content(role="model", parts=parts))
                else:
                    result.append(
                        gtypes.Content(
                            role="model",
                            parts=[gtypes.Part.from_text(text=msg.content or "")],
                        )
                    )
            elif msg.role == "tool_result":
                result.append(
                    gtypes.Content(
                        role="user",
                        parts=[
                            gtypes.Part.from_function_response(
                                name=msg.tool_call_id or "tool",
                                response={"result": msg.content},
                            )
                        ],
                    )
                )
        return result

    def _parse_response(self, response: Any) -> LLMResponse:
        candidate = response.candidates[0] if response.candidates else None
        if not candidate:
            return LLMResponse(text=None, tool_calls=[], stop_reason="stop")

        text = None
        tool_calls = []
        for part in candidate.content.parts:
            if part.text:
                text = part.text
            elif part.function_call:
                fc = part.function_call
                tool_calls.append(
                    ToolCall(
                        id=str(uuid.uuid4()),
                        name=fc.name,
                        input=dict(fc.args) if fc.args else {},
                    )
                )

        stop_reason = "tool_use" if tool_calls else "end_turn"
        llm_response = LLMResponse(
            text=text, tool_calls=tool_calls, stop_reason=stop_reason
        )
        # Stash raw parts so they can be echoed back with thought_signature intact
        if tool_calls:
            llm_response._gemini_raw_parts = list(candidate.content.parts)
        return llm_response
