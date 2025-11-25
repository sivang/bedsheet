"""Test MockLLMClient and MockResponse."""
import pytest
from bedsheet.testing import MockLLMClient, MockResponse
from bedsheet.llm.base import LLMClient, ToolCall
from bedsheet.memory.base import Message


def test_mock_llm_client_implements_protocol():
    mock = MockLLMClient(responses=[])
    assert isinstance(mock, LLMClient)


@pytest.mark.asyncio
async def test_mock_llm_client_text_response():
    mock = MockLLMClient(responses=[
        MockResponse(text="Hello!")
    ])

    response = await mock.chat(
        messages=[Message(role="user", content="Hi")],
        system="You are helpful.",
    )

    assert response.text == "Hello!"
    assert response.tool_calls == []


@pytest.mark.asyncio
async def test_mock_llm_client_tool_call_response():
    mock = MockLLMClient(responses=[
        MockResponse(tool_calls=[
            ToolCall(id="call_1", name="get_weather", input={"city": "SF"})
        ])
    ])

    response = await mock.chat(
        messages=[Message(role="user", content="Weather?")],
        system="You are helpful.",
    )

    assert response.text is None
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "get_weather"
    assert response.stop_reason == "tool_use"


@pytest.mark.asyncio
async def test_mock_llm_client_sequence():
    mock = MockLLMClient(responses=[
        MockResponse(tool_calls=[
            ToolCall(id="call_1", name="get_weather", input={"city": "SF"})
        ]),
        MockResponse(text="The weather is sunny."),
    ])

    # First call - tool use
    resp1 = await mock.chat([], "system")
    assert resp1.stop_reason == "tool_use"

    # Second call - completion
    resp2 = await mock.chat([], "system")
    assert resp2.text == "The weather is sunny."


@pytest.mark.asyncio
async def test_mock_llm_client_exhausted():
    mock = MockLLMClient(responses=[
        MockResponse(text="Only one")
    ])

    await mock.chat([], "system")

    with pytest.raises(RuntimeError):
        await mock.chat([], "system")
