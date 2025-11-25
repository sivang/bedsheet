import pytest
from bedsheet.action_group import ActionGroup, Action, generate_schema


def test_generate_schema_string():
    def fn(name: str) -> str:
        pass

    schema = generate_schema(fn)
    assert schema["type"] == "object"
    assert schema["properties"]["name"] == {"type": "string"}
    assert schema["required"] == ["name"]


def test_generate_schema_int():
    def fn(count: int) -> int:
        pass

    schema = generate_schema(fn)
    assert schema["properties"]["count"] == {"type": "integer"}


def test_generate_schema_float():
    def fn(price: float) -> float:
        pass

    schema = generate_schema(fn)
    assert schema["properties"]["price"] == {"type": "number"}


def test_generate_schema_bool():
    def fn(enabled: bool) -> bool:
        pass

    schema = generate_schema(fn)
    assert schema["properties"]["enabled"] == {"type": "boolean"}


def test_generate_schema_list():
    def fn(items: list) -> list:
        pass

    schema = generate_schema(fn)
    assert schema["properties"]["items"] == {"type": "array"}


def test_generate_schema_dict():
    def fn(data: dict) -> dict:
        pass

    schema = generate_schema(fn)
    assert schema["properties"]["data"] == {"type": "object"}


def test_generate_schema_optional_param():
    def fn(city: str, units: str = "celsius") -> dict:
        pass

    schema = generate_schema(fn)
    assert "city" in schema["required"]
    assert "units" not in schema["required"]
    assert schema["properties"]["units"] == {"type": "string", "default": "celsius"}


def test_generate_schema_multiple_params():
    def fn(city: str, lat: float, lon: float, detailed: bool = False) -> dict:
        pass

    schema = generate_schema(fn)
    assert set(schema["required"]) == {"city", "lat", "lon"}
    assert len(schema["properties"]) == 4
