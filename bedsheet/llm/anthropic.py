"""Anthropic Claude LLM client implementation."""
import anthropic

from bedsheet.llm.base import LLMClient, LLMResponse, ToolCall, ToolDefinition
from bedsheet.memory.base import Message


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
    ) -> LLMResponse:
        """Send messages to Claude and get a response."""
        # Convert messages to Anthropic format
        anthropic_messages = self._convert_messages(messages)

        # Build request kwargs
        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": anthropic_messages,
        }

        # Add tools if provided
        if tools:
            kwargs["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
                for tool in tools
            ]

        # Make API call
        response = await self._client.messages.create(**kwargs)

        # Parse response
        return self._parse_response(response)

    def _convert_messages(self, messages: list[Message]) -> list[dict]:
        """Convert internal messages to Anthropic format."""
        result = []

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

    def _parse_response(self, response) -> LLMResponse:
        """Parse Anthropic response to internal format."""
        text = None
        tool_calls = []

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

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason,
        )
