"""Tests for Anthropic LLM client implementation."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bedsheet.llm.anthropic import AnthropicClient
from bedsheet.llm.base import LLMClient, ToolDefinition
from bedsheet.memory.base import Message


def test_anthropic_client_implements_protocol():
    with patch("bedsheet.llm.anthropic.anthropic"):
        client = AnthropicClient(api_key="test-key")
        assert isinstance(client, LLMClient)


def test_anthropic_client_default_model():
    with patch("bedsheet.llm.anthropic.anthropic"):
        client = AnthropicClient(api_key="test-key")
        assert client.model == "claude-sonnet-4-5-20250929"


def test_anthropic_client_custom_model():
    with patch("bedsheet.llm.anthropic.anthropic"):
        client = AnthropicClient(api_key="test-key", model="claude-3-haiku-20240307")
        assert client.model == "claude-3-haiku-20240307"


@pytest.mark.asyncio
async def test_anthropic_client_chat_text_response():
    with patch("bedsheet.llm.anthropic.anthropic") as mock_anthropic:
        # Setup mock
        mock_client = MagicMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Hello!")]
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        client = AnthropicClient(api_key="test-key")
        response = await client.chat(
            messages=[Message(role="user", content="Hi")],
            system="Be helpful.",
        )

        assert response.text == "Hello!"
        assert response.tool_calls == []
        assert response.stop_reason == "end_turn"


@pytest.mark.asyncio
async def test_anthropic_client_chat_tool_call():
    with patch("bedsheet.llm.anthropic.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        mock_tool_use = MagicMock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.id = "call_123"
        mock_tool_use.name = "get_weather"
        mock_tool_use.input = {"city": "SF"}

        mock_response = MagicMock()
        mock_response.content = [mock_tool_use]
        mock_response.stop_reason = "tool_use"
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        client = AnthropicClient(api_key="test-key")
        tools = [
            ToolDefinition(
                name="get_weather",
                description="Get weather",
                input_schema={"type": "object", "properties": {"city": {"type": "string"}}}
            )
        ]

        response = await client.chat(
            messages=[Message(role="user", content="Weather?")],
            system="Be helpful.",
            tools=tools,
        )

        assert response.text is None
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "get_weather"
        assert response.tool_calls[0].input == {"city": "SF"}
        assert response.stop_reason == "tool_use"


@pytest.mark.asyncio
async def test_anthropic_client_message_conversion():
    """Test that messages are converted to Anthropic format correctly."""
    with patch("bedsheet.llm.anthropic.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Done")]
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        client = AnthropicClient(api_key="test-key")

        # Test with user, assistant, and tool_result messages
        messages = [
            Message(role="user", content="Hi"),
            Message(role="assistant", content=None, tool_calls=[
                {"id": "call_1", "name": "test", "input": {"x": 1}}
            ]),
            Message(role="tool_result", content='{"result": "ok"}', tool_call_id="call_1"),
        ]

        await client.chat(messages=messages, system="Test")

        # Verify the call was made with correct format
        call_args = mock_client.messages.create.call_args
        converted_messages = call_args.kwargs["messages"]

        # Check user message
        assert converted_messages[0]["role"] == "user"
        assert converted_messages[0]["content"] == "Hi"

        # Check assistant message with tool use
        assert converted_messages[1]["role"] == "assistant"
        assert isinstance(converted_messages[1]["content"], list)
        assert converted_messages[1]["content"][0]["type"] == "tool_use"

        # Check tool result
        assert converted_messages[2]["role"] == "user"
        assert converted_messages[2]["content"][0]["type"] == "tool_result"
        assert converted_messages[2]["content"][0]["tool_use_id"] == "call_1"


@pytest.mark.asyncio
async def test_anthropic_client_mixed_content_response():
    """Test response with both text and tool_use blocks."""
    with patch("bedsheet.llm.anthropic.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        # Response with text followed by tool_use
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Let me check that."

        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "call_1"
        mock_tool_block.name = "search"
        mock_tool_block.input = {"query": "test"}

        mock_response = MagicMock()
        mock_response.content = [mock_text_block, mock_tool_block]
        mock_response.stop_reason = "tool_use"
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        client = AnthropicClient(api_key="test-key")
        response = await client.chat(
            messages=[Message(role="user", content="Search for test")],
            system="Be helpful.",
        )

        assert response.text == "Let me check that."
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "search"
        assert response.stop_reason == "tool_use"
