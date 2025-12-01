import pytest
from bedsheet.action_group import ActionGroup, generate_schema


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


def test_action_group_creation():
    group = ActionGroup(name="TestGroup", description="Test actions")
    assert group.name == "TestGroup"
    assert group.description == "Test actions"


@pytest.mark.asyncio
async def test_action_decorator():
    group = ActionGroup(name="TestGroup")

    @group.action(name="greet", description="Greet someone")
    async def greet(name: str) -> str:
        return f"Hello, {name}!"

    action = group.get_action("greet")
    assert action is not None
    assert action.name == "greet"
    assert action.description == "Greet someone"

    result = await action.fn(name="Alice")
    assert result == "Hello, Alice!"


def test_action_decorator_with_explicit_schema():
    group = ActionGroup(name="TestGroup")

    custom_schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }

    @group.action(name="search", description="Search", parameters=custom_schema)
    async def search(query: str) -> dict:
        return {"results": []}

    action = group.get_action("search")
    assert action.input_schema == custom_schema


def test_get_actions():
    group = ActionGroup(name="TestGroup")

    @group.action(name="action1", description="First")
    async def action1() -> str:
        return "1"

    @group.action(name="action2", description="Second")
    async def action2() -> str:
        return "2"

    actions = group.get_actions()
    assert len(actions) == 2
    names = {a.name for a in actions}
    assert names == {"action1", "action2"}


def test_get_tool_definitions():
    group = ActionGroup(name="TestGroup")

    @group.action(name="get_weather", description="Get weather for a city")
    async def get_weather(city: str) -> dict:
        return {}

    tools = group.get_tool_definitions()
    assert len(tools) == 1
    assert tools[0].name == "get_weather"
    assert tools[0].description == "Get weather for a city"
    assert tools[0].input_schema["properties"]["city"]["type"] == "string"
