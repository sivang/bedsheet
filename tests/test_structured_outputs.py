"""Tests for structured outputs (OutputSchema)."""
import pytest
from bedsheet.llm.base import OutputSchema, LLMResponse


class TestOutputSchema:
    """Tests for OutputSchema class."""

    def test_from_dict_creates_schema(self):
        """Test creating OutputSchema from a dict."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name", "age"],
        }
        output_schema = OutputSchema.from_dict(schema)

        assert output_schema.schema == schema
        assert output_schema._pydantic_model is None

    def test_from_pydantic_creates_schema(self):
        """Test creating OutputSchema from a Pydantic model."""
        # Only run if pydantic is available
        pytest.importorskip("pydantic")
        from pydantic import BaseModel

        class Person(BaseModel):
            name: str
            age: int

        output_schema = OutputSchema.from_pydantic(Person)

        assert "properties" in output_schema.schema
        assert "name" in output_schema.schema["properties"]
        assert "age" in output_schema.schema["properties"]
        assert output_schema._pydantic_model is Person

    def test_schema_contains_required_fields(self):
        """Test that Pydantic schema includes required fields."""
        pytest.importorskip("pydantic")
        from pydantic import BaseModel

        class StockAnalysis(BaseModel):
            symbol: str
            recommendation: str
            confidence: float

        output_schema = OutputSchema.from_pydantic(StockAnalysis)

        assert "required" in output_schema.schema
        assert "symbol" in output_schema.schema["required"]
        assert "recommendation" in output_schema.schema["required"]
        assert "confidence" in output_schema.schema["required"]


class TestLLMResponseParsedOutput:
    """Tests for LLMResponse.parsed_output field."""

    def test_llm_response_includes_parsed_output(self):
        """Test that LLMResponse can include parsed_output."""
        response = LLMResponse(
            text='{"name": "Test", "value": 42}',
            tool_calls=[],
            parsed_output={"name": "Test", "value": 42},
        )

        assert response.parsed_output == {"name": "Test", "value": 42}

    def test_llm_response_parsed_output_defaults_to_none(self):
        """Test that parsed_output defaults to None."""
        response = LLMResponse(
            text="Hello",
            tool_calls=[],
        )

        assert response.parsed_output is None

    def test_llm_response_with_pydantic_instance(self):
        """Test that parsed_output can be a Pydantic model instance."""
        pytest.importorskip("pydantic")
        from pydantic import BaseModel

        class Result(BaseModel):
            status: str
            count: int

        result = Result(status="success", count=5)
        response = LLMResponse(
            text='{"status": "success", "count": 5}',
            tool_calls=[],
            parsed_output=result,
        )

        assert response.parsed_output.status == "success"
        assert response.parsed_output.count == 5


class TestMockClientStructuredOutputs:
    """Tests for MockLLMClient structured output support."""

    def test_mock_client_accepts_output_schema(self):
        """Test that MockLLMClient accepts output_schema parameter."""
        from bedsheet.testing import MockLLMClient, MockResponse

        mock_client = MockLLMClient([
            MockResponse(
                text='{"result": "test"}',
                parsed_output={"result": "test"},
            )
        ])

        schema = OutputSchema.from_dict({
            "type": "object",
            "properties": {"result": {"type": "string"}},
        })

        # Should not raise
        import asyncio
        response = asyncio.run(mock_client.chat(
            messages=[],
            system="test",
            output_schema=schema,
        ))

        assert response.parsed_output == {"result": "test"}

    @pytest.mark.asyncio
    async def test_mock_client_stream_with_output_schema(self):
        """Test that MockLLMClient stream accepts output_schema."""
        from bedsheet.testing import MockLLMClient, MockResponse

        mock_client = MockLLMClient([
            MockResponse(
                text='{"data": "streamed"}',
                parsed_output={"data": "streamed"},
            )
        ])

        schema = OutputSchema.from_dict({
            "type": "object",
            "properties": {"data": {"type": "string"}},
        })

        chunks = []
        async for chunk in mock_client.chat_stream(
            messages=[],
            system="test",
            output_schema=schema,
        ):
            chunks.append(chunk)

        # Last chunk should be LLMResponse with parsed_output
        final_response = chunks[-1]
        assert isinstance(final_response, LLMResponse)
        assert final_response.parsed_output == {"data": "streamed"}
