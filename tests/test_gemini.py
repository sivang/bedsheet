"""Tests for Gemini LLM client implementation.

Covers the critical paths that were previously untested:
- chat_stream: must make ONE API call per turn (regression test for the
  duplicate-call bug where the final response was re-fetched via self.chat())
- chat_stream: accumulated text must match final LLMResponse.text
- chat_stream: falls back to non-streaming when tools are present
- _call_with_retry: 429 backoff and non-rate-limit propagation
- _parse_response: thought-signature raw parts stashed on tool-call responses
  (required for Gemini 3.x — missing the stash causes 400 errors mid-conversation)
- _convert_messages: assistant messages with stashed _gemini_parts are echoed back
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bedsheet.llm.base import LLMClient, LLMResponse, ToolDefinition
from bedsheet.memory.base import Message


class _FakeAsyncIter:
    """Minimal async iterator over a fixed list of items."""

    def __init__(self, items: list) -> None:
        self._items = list(items)

    def __aiter__(self) -> "_FakeAsyncIter":
        return self

    async def __anext__(self):
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


def _make_text_part(text: str) -> MagicMock:
    part = MagicMock()
    part.text = text
    part.function_call = None
    return part


def _make_function_call_part(name: str, args: dict) -> MagicMock:
    part = MagicMock()
    part.text = None
    fc = MagicMock()
    fc.name = name
    fc.args = args
    part.function_call = fc
    return part


def _make_response(parts: list) -> MagicMock:
    """Build a fake Gemini response object with the given parts."""
    candidate = MagicMock()
    candidate.content.parts = parts
    response = MagicMock()
    response.candidates = [candidate]
    return response


def test_gemini_client_implements_protocol():
    with patch("bedsheet.llm.gemini.genai"):
        from bedsheet.llm.gemini import GeminiClient

        client = GeminiClient(api_key="test-key")
        assert isinstance(client, LLMClient)


def test_gemini_client_default_model():
    with patch("bedsheet.llm.gemini.genai"):
        from bedsheet.llm.gemini import GeminiClient

        client = GeminiClient(api_key="test-key")
        assert client.model == "gemini-3-flash-preview"


def test_gemini_client_custom_model():
    with patch("bedsheet.llm.gemini.genai"):
        from bedsheet.llm.gemini import GeminiClient

        client = GeminiClient(api_key="test-key", model="gemini-3-pro-preview")
        assert client.model == "gemini-3-pro-preview"


@pytest.mark.asyncio
async def test_gemini_chat_text_response():
    with patch("bedsheet.llm.gemini.genai") as mock_genai:
        from bedsheet.llm.gemini import GeminiClient

        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        fake_response = _make_response([_make_text_part("Hello!")])
        mock_client.aio.models.generate_content = AsyncMock(return_value=fake_response)

        client = GeminiClient(api_key="test-key")
        response = await client.chat(
            messages=[Message(role="user", content="Hi")],
            system="Be helpful.",
        )

        assert response.text == "Hello!"
        assert response.tool_calls == []
        assert response.stop_reason == "end_turn"


@pytest.mark.asyncio
async def test_gemini_chat_tool_call_stashes_raw_parts():
    """Gemini 3.x requires the raw parts (with thought_signature) to be echoed
    back on the next turn. _parse_response must stash them on the LLMResponse."""
    with patch("bedsheet.llm.gemini.genai") as mock_genai:
        from bedsheet.llm.gemini import GeminiClient

        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        fc_part = _make_function_call_part("get_weather", {"city": "SF"})
        fake_response = _make_response([fc_part])
        mock_client.aio.models.generate_content = AsyncMock(return_value=fake_response)

        client = GeminiClient(api_key="test-key")
        tools = [
            ToolDefinition(
                name="get_weather",
                description="Get weather",
                input_schema={
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                },
            )
        ]
        response = await client.chat(
            messages=[Message(role="user", content="Weather?")],
            system="",
            tools=tools,
        )

        assert response.tool_calls[0].name == "get_weather"
        assert response.tool_calls[0].input == {"city": "SF"}
        assert response.stop_reason == "tool_use"
        # Raw parts stash (critical for Gemini 3.x thought_signature preservation)
        assert response._gemini_raw_parts is not None
        assert fc_part in response._gemini_raw_parts


def test_gemini_convert_messages_preserves_stashed_parts():
    """Assistant messages with _gemini_parts must be echoed back as-is (not
    reconstructed from tool_calls). This preserves thought_signature."""
    with (
        patch("bedsheet.llm.gemini.genai"),
        patch("bedsheet.llm.gemini.gtypes") as mock_gtypes,
    ):
        from bedsheet.llm.gemini import GeminiClient

        mock_gtypes.Content = MagicMock(
            side_effect=lambda role, parts: {"role": role, "parts": parts}
        )
        mock_gtypes.Part.from_text = MagicMock(side_effect=lambda text: {"text": text})

        client = GeminiClient(api_key="test-key")

        sentinel_parts = [MagicMock(name="raw_part_with_thought_sig")]
        msg = Message(
            role="assistant",
            content=None,
            tool_calls=[{"name": "x", "input": {}}],
            _gemini_parts=sentinel_parts,
        )
        contents = client._convert_messages([msg])

        # Must have used the stashed parts, not rebuilt from tool_calls
        assert len(contents) == 1
        assert contents[0]["role"] == "model"
        assert contents[0]["parts"] is sentinel_parts


@pytest.mark.asyncio
async def test_gemini_chat_stream_makes_single_api_call():
    """REGRESSION TEST for B1: chat_stream used to call generate_content_stream
    (to stream tokens) AND then self.chat() again (to get the final LLMResponse),
    making every streaming turn cost 2x API calls and causing the text persisted
    in memory to diverge from what the user saw streamed."""
    with patch("bedsheet.llm.gemini.genai") as mock_genai:
        from bedsheet.llm.gemini import GeminiClient

        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        # Streaming: yield two text chunks, then stop
        async def fake_stream(**kwargs):
            chunk_a = MagicMock()
            chunk_a.text = "Hello "
            chunk_b = MagicMock()
            chunk_b.text = "world"
            return _FakeAsyncIter([chunk_a, chunk_b])

        mock_client.aio.models.generate_content_stream = fake_stream
        mock_client.aio.models.generate_content = AsyncMock()

        client = GeminiClient(api_key="test-key")

        tokens: list[str] = []
        final: LLMResponse | None = None
        async for item in client.chat_stream(
            messages=[Message(role="user", content="Hi")],
            system="",
        ):
            if isinstance(item, str):
                tokens.append(item)
            else:
                final = item

        # Exactly one API call — the stream. generate_content must NOT be called.
        mock_client.aio.models.generate_content.assert_not_called()

        assert tokens == ["Hello ", "world"]
        assert final is not None
        assert final.text == "Hello world"
        assert final.tool_calls == []
        assert final.stop_reason == "end_turn"


@pytest.mark.asyncio
async def test_gemini_chat_stream_empty_stream():
    """Empty stream yields no tokens and a final LLMResponse with text=None."""
    with patch("bedsheet.llm.gemini.genai") as mock_genai:
        from bedsheet.llm.gemini import GeminiClient

        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        async def fake_stream(**kwargs):
            return _FakeAsyncIter([])

        mock_client.aio.models.generate_content_stream = fake_stream
        mock_client.aio.models.generate_content = AsyncMock()

        client = GeminiClient(api_key="test-key")

        items = []
        async for item in client.chat_stream(
            messages=[Message(role="user", content="Hi")],
            system="",
        ):
            items.append(item)

        mock_client.aio.models.generate_content.assert_not_called()
        assert len(items) == 1
        assert isinstance(items[0], LLMResponse)
        assert items[0].text is None


@pytest.mark.asyncio
async def test_gemini_chat_stream_with_tools_falls_back_to_chat():
    """When tools are present, streaming is skipped and chat() handles the turn.
    This avoids partial function-call assembly across chunks."""
    with patch("bedsheet.llm.gemini.genai") as mock_genai:
        from bedsheet.llm.gemini import GeminiClient

        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        fc_part = _make_function_call_part("search", {"q": "test"})
        fake_response = _make_response([fc_part])
        mock_client.aio.models.generate_content = AsyncMock(return_value=fake_response)
        # Stream must not be called at all
        mock_client.aio.models.generate_content_stream = MagicMock(
            side_effect=AssertionError(
                "stream must not be called when tools are present"
            )
        )

        client = GeminiClient(api_key="test-key")
        tools = [
            ToolDefinition(
                name="search",
                description="Search",
                input_schema={
                    "type": "object",
                    "properties": {"q": {"type": "string"}},
                },
            )
        ]
        items = []
        async for item in client.chat_stream(
            messages=[Message(role="user", content="Find")],
            system="",
            tools=tools,
        ):
            items.append(item)

        # The final LLMResponse with the tool call must be yielded
        llm_responses = [i for i in items if isinstance(i, LLMResponse)]
        assert len(llm_responses) == 1
        assert llm_responses[0].tool_calls[0].name == "search"


@pytest.mark.asyncio
async def test_gemini_call_with_retry_backs_off_on_rate_limit():
    """429 / RESOURCE_EXHAUSTED errors trigger exponential backoff and retry."""
    with (
        patch("bedsheet.llm.gemini.genai") as mock_genai,
        patch("bedsheet.llm.gemini.asyncio.sleep", new=AsyncMock()) as mock_sleep,
    ):
        from bedsheet.llm.gemini import GeminiClient

        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        # First call raises 429, second call succeeds
        call_count = {"n": 0}

        async def fake_generate(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception("429 RESOURCE_EXHAUSTED: quota exceeded")
            return _make_response([_make_text_part("ok")])

        mock_client.aio.models.generate_content = fake_generate

        client = GeminiClient(api_key="test-key", max_retries=3)
        response = await client.chat(
            messages=[Message(role="user", content="Hi")],
            system="",
        )

        assert response.text == "ok"
        assert call_count["n"] == 2
        # At least one sleep must have happened for the backoff
        assert mock_sleep.await_count >= 1


@pytest.mark.asyncio
async def test_gemini_call_with_retry_propagates_non_rate_limit():
    """Non-rate-limit errors (e.g., 400 bad request) must propagate immediately
    without retrying, to avoid masking real bugs."""
    with (
        patch("bedsheet.llm.gemini.genai") as mock_genai,
        patch("bedsheet.llm.gemini.asyncio.sleep", new=AsyncMock()) as mock_sleep,
    ):
        from bedsheet.llm.gemini import GeminiClient

        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        call_count = {"n": 0}

        async def fake_generate(**kwargs):
            call_count["n"] += 1
            raise ValueError("400 INVALID_ARGUMENT: malformed request")

        mock_client.aio.models.generate_content = fake_generate

        client = GeminiClient(api_key="test-key", max_retries=3)

        with pytest.raises(ValueError, match="400"):
            await client.chat(
                messages=[Message(role="user", content="Hi")],
                system="",
            )

        # No retries, no sleeps
        assert call_count["n"] == 1
        mock_sleep.assert_not_awaited()
