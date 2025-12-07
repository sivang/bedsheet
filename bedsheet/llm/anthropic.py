"""Anthropic Claude LLM client implementation."""
import json
from typing import Any, AsyncIterator

import anthropic

from bedsheet.llm.base import LLMResponse, OutputSchema, ToolCall, ToolDefinition
from bedsheet.memory.base import Message

# Beta header for structured outputs
STRUCTURED_OUTPUTS_BETA = "structured-outputs-2025-11-13"


class AnthropicClient:
    """LLM client for Anthropic's Claude models."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def chat(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
        output_schema: OutputSchema | None = None,
    ) -> LLMResponse:
        """Send messages to Claude and get a response."""
        # Convert messages to Anthropic format
        anthropic_messages = self._convert_messages(messages)

        # Convert tools to Anthropic format
        anthropic_tools = None
        if tools:
            anthropic_tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
                for tool in tools
            ]

        # Build base kwargs
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": anthropic_messages,
        }

        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        # Handle structured outputs (beta feature)
        if output_schema:
            # Use beta client for structured outputs
            kwargs["betas"] = [STRUCTURED_OUTPUTS_BETA]
            kwargs["output_format"] = {
                "type": "json_schema",
                "schema": output_schema.schema,
            }
            response = await self._client.beta.messages.create(**kwargs)  # type: ignore[arg-type]
        else:
            response = await self._client.messages.create(**kwargs)  # type: ignore[arg-type]

        # Parse response
        return self._parse_response(response, output_schema)

    async def chat_stream(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition] | None = None,
        output_schema: OutputSchema | None = None,
    ) -> AsyncIterator[str | LLMResponse]:
        """Stream response from Claude.

        Note: Structured outputs with output_schema use non-streaming for now,
        as the beta API streaming support may be limited.
        """
        # For structured outputs, fall back to non-streaming
        if output_schema:
            response = await self.chat(messages, system, tools, output_schema)
            if response.text:
                yield response.text
            yield response
            return

        anthropic_messages = self._convert_messages(messages)

        # Convert tools to Anthropic format
        anthropic_tools = None
        if tools:
            anthropic_tools = [
                {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema}
                for tool in tools
            ]

        if anthropic_tools:
            stream_ctx = self._client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=anthropic_messages,  # type: ignore[arg-type]
                tools=anthropic_tools,  # type: ignore[arg-type]
            )
        else:
            stream_ctx = self._client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=anthropic_messages,  # type: ignore[arg-type]
            )

        async with stream_ctx as stream:
            async for text in stream.text_stream:
                yield text

            final = await stream.get_final_message()
            yield self._parse_response(final)

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert internal messages to Anthropic format."""
        result: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == "user":
                result.append({"role": "user", "content": msg.content})

            elif msg.role == "assistant":
                if msg.tool_calls:
                    # Assistant message with tool use
                    content = []
                    for tc in msg.tool_calls:
                        content.append({
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["name"],
                            "input": tc["input"],
                        })
                    result.append({"role": "assistant", "content": content})
                else:
                    result.append({"role": "assistant", "content": msg.content})

            elif msg.role == "tool_result":
                result.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content,
                        }
                    ],
                })

        return result

    def _parse_response(
        self, response, output_schema: OutputSchema | None = None
    ) -> LLMResponse:
        """Parse Anthropic response to internal format."""
        text = None
        tool_calls = []
        parsed_output = None

        for block in response.content:
            if block.type == "text":
                text = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        input=block.input,
                    )
                )

        # Parse structured output if schema was provided
        if output_schema and text:
            try:
                parsed_data = json.loads(text)
                # If we have a Pydantic model, validate and instantiate
                if output_schema._pydantic_model:
                    parsed_output = output_schema._pydantic_model.model_validate(parsed_data)
                else:
                    parsed_output = parsed_data
            except (json.JSONDecodeError, Exception):
                # If parsing fails, keep parsed_output as None
                pass

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason,
            parsed_output=parsed_output,
        )
