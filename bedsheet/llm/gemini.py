"""Google Gemini LLM client implementation."""

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


class GeminiClient:
    """LLM client for Google Gemini models via the Gemini API (AI Studio key or Vertex AI)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.0-flash-exp",
        max_tokens: int = 4096,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._client = genai.Client(api_key=api_key)

    async def chat(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
        output_schema: OutputSchema | None = None,
    ) -> LLMResponse:
        contents = self._convert_messages(messages)
        config = self._build_config(system, tools)
        response = await self._client.aio.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )
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
            # Thinking models (e.g. gemini-3-flash-preview) attach a thought_signature
            # to function call parts that must be echoed back in subsequent turns.
            # Since bedsheet's ToolCall only stores name/id/input, disable thinking
            # when tools are active to avoid the INVALID_ARGUMENT error.
            kwargs["thinking_config"] = gtypes.ThinkingConfig(thinking_budget=0)
        return gtypes.GenerateContentConfig(**kwargs)

    def _convert_messages(self, messages: list[Message]) -> list["gtypes.Content"]:
        """Convert bedsheet messages to Gemini Content objects."""
        result: list[gtypes.Content] = []
        for msg in messages:
            if msg.role == "user":
                result.append(
                    gtypes.Content(
                        role="user", parts=[gtypes.Part.from_text(text=msg.content)]
                    )
                )
            elif msg.role == "assistant":
                if msg.tool_calls:
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
                # Gemini expects function responses as a user turn
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
        return LLMResponse(text=text, tool_calls=tool_calls, stop_reason=stop_reason)
