"""Tests for bedsheet.deploy.targets.aws module."""
import tempfile
from pathlib import Path

import pytest

from bedsheet import Agent, ActionGroup, Supervisor
from bedsheet.deploy import (
    AgentConfig,
    BedsheetConfig,
    AWSTargetConfig,
)
from bedsheet.deploy.introspect import extract_agent_metadata
from bedsheet.deploy.targets import AWSTarget, GeneratedFile
from bedsheet.testing import MockLLMClient, MockResponse


@pytest.fixture
def mock_aws_config():
    """Create a mock BedsheetConfig for AWS testing."""
    return BedsheetConfig(
        name="test-agent",
        agents=[
            AgentConfig(
                name="calculator",
                module="myapp.agents.calculator",
                class_name="CalculatorAgent",
                description="A calculator agent",
            )
        ],
        target="aws",
        targets={
            "aws": AWSTargetConfig(
                region="us-east-1",
                lambda_memory=512,
                bedrock_model="anthropic.claude-sonnet-4-5-v2:0",
            ),
        },
    )


@pytest.fixture
async def mock_single_agent_metadata():
    """Create a mock AgentMetadata for a single agent."""
    mock = MockLLMClient([MockResponse(text="ok")])

    agent = Agent(
        name="TestAgent",
        instruction="Test agent for AWS deployment",
        model_client=mock,
    )

    group = ActionGroup(name="TestGroup", description="Test actions")

    @group.action(name="add", description="Add two numbers")
    async def add(a: int, b: int) -> int:
        return a + b

    @group.action(name="multiply", description="Multiply two numbers")
    async def multiply(x: int, y: int) -> int:
        return x * y

    agent.add_action_group(group)

    return extract_agent_metadata(agent)


@pytest.fixture
async def mock_supervisor_metadata():
    """Create a mock AgentMetadata for a supervisor with collaborators."""
    mock = MockLLMClient([MockResponse(text="ok")])

    # Create collaborator agents
    calculator = Agent(
        name="Calculator",
        instruction="Do math calculations",
        model_client=mock,
    )
    calc_group = ActionGroup(name="MathOps", description="Math operations")

    @calc_group.action(name="add", description="Add numbers")
    async def add(a: int, b: int) -> int:
        return a + b

    calculator.add_action_group(calc_group)

    weather = Agent(
        name="Weather",
        instruction="Get weather info",
        model_client=mock,
    )
    weather_group = ActionGroup(name="WeatherOps", description="Weather operations")

    @weather_group.action(name="get_weather", description="Get current weather")
    async def get_weather(city: str) -> str:
        return f"Weather in {city}"

    weather.add_action_group(weather_group)

    # Create supervisor
    supervisor = Supervisor(
        name="MultiAgent",
        instruction="Coordinate multiple agents",
        model_client=mock,
        collaborators=[calculator, weather],
    )

    return extract_agent_metadata(supervisor)


def test_aws_target_name():
    """Test AWSTarget.name property."""
    target = AWSTarget()
    assert target.name == "aws"


def test_aws_target_validate_valid_config(mock_aws_config):
    """Test AWSTarget.validate with valid config."""
    target = AWSTarget()
    errors = target.validate(mock_aws_config)
    assert errors == []


def test_aws_target_validate_invalid_lambda_memory_too_low():
    """Test AWSTarget.validate with Lambda memory too low."""
    # Pydantic validation should catch this before it reaches our validator
    with pytest.raises(ValueError, match="greater than or equal to 128"):
        BedsheetConfig(
            name="test",
            agents=[
                AgentConfig(
                    name="test",
                    module="test.agent",
                    class_name="TestAgent",
                )
            ],
            target="aws",
            targets={
                "aws": AWSTargetConfig(region="us-east-1", lambda_memory=64),
            },
        )


def test_aws_target_validate_invalid_lambda_memory_too_high():
    """Test AWSTarget.validate with Lambda memory too high."""
    # Pydantic validation should catch this before it reaches our validator
    with pytest.raises(ValueError, match="less than or equal to 10240"):
        BedsheetConfig(
            name="test",
            agents=[
                AgentConfig(
                    name="test",
                    module="test.agent",
                    class_name="TestAgent",
                )
            ],
            target="aws",
            targets={
                "aws": AWSTargetConfig(region="us-east-1", lambda_memory=20000),
            },
        )


def test_aws_target_validate_invalid_region():
    """Test AWSTarget.validate with invalid region format."""
    # This should be caught by Pydantic validation first
    with pytest.raises(ValueError, match="Invalid AWS region format"):
        BedsheetConfig(
            name="test",
            agents=[
                AgentConfig(
                    name="test",
                    module="test.agent",
                    class_name="TestAgent",
                )
            ],
            target="aws",
            targets={
                "aws": AWSTargetConfig(region="invalid-region-format"),
            },
        )


def test_aws_target_validate_no_aws_config():
    """Test AWSTarget.validate when no AWS config exists."""
    config = BedsheetConfig(
        name="test",
        agents=[
            AgentConfig(
                name="test",
                module="test.agent",
                class_name="TestAgent",
            )
        ],
        target="aws",
        targets={
            "aws": AWSTargetConfig(region="us-east-1"),
        },
    )

    target = AWSTarget()
    errors = target.validate(config)
    assert errors == []


@pytest.mark.asyncio
async def test_aws_target_generate_creates_all_files(mock_aws_config, mock_single_agent_metadata):
    """Test AWSTarget.generate creates all expected files."""
    target = AWSTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_aws_config, mock_single_agent_metadata, output_dir)

        # Check we got all expected files
        # Common: 5, Stacks: 2, Lambda: 3, Schemas: 1, Debug UI: 2, GitHub: 2 = 14 total
        assert len(files) == 14

        file_names = [f.path.name for f in files]
        assert "pyproject.toml" in file_names
        assert "Makefile" in file_names
        assert ".env.example" in file_names
        assert "app.py" in file_names
        assert "cdk.json" in file_names
        assert "agent_stack.py" in [f.path.name for f in files if f.path.parent.name == "stacks"]
        assert "__init__.py" in [f.path.name for f in files if f.path.parent.name == "stacks"]
        assert "handler.py" in [f.path.name for f in files if f.path.parent.name == "lambda"]
        assert "__init__.py" in [f.path.name for f in files if f.path.parent.name == "lambda"]
        assert "requirements.txt" in [f.path.name for f in files if f.path.parent.name == "lambda"]
        assert "openapi.yaml" in [f.path.name for f in files if f.path.parent.name == "schemas"]

        # Check all are GeneratedFile instances
        for file in files:
            assert isinstance(file, GeneratedFile)
            assert isinstance(file.path, Path)
            assert isinstance(file.content, str)
            # Some files like __init__.py can be empty
            assert file.content is not None


@pytest.mark.asyncio
async def test_aws_target_generate_cdk_stack_content(mock_aws_config, mock_single_agent_metadata):
    """Test AWSTarget.generate creates CDK stack with Bedrock constructs."""
    target = AWSTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_aws_config, mock_single_agent_metadata, output_dir)

        stack_file = next(f for f in files if f.path.name == "agent_stack.py")
        content = stack_file.content

        # Check for expected CDK imports
        assert "from aws_cdk import" in content or "import aws_cdk" in content

        # Check for Bedrock-related constructs
        assert "bedrock" in content.lower() or "agent" in content.lower()

        # Check for Lambda constructs (for action groups)
        assert "lambda" in content.lower() or "function" in content.lower()


@pytest.mark.asyncio
async def test_aws_target_generate_lambda_handler_uses_powertools(
    mock_aws_config, mock_single_agent_metadata
):
    """Test AWSTarget.generate creates Lambda handler with Powertools pattern."""
    target = AWSTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_aws_config, mock_single_agent_metadata, output_dir)

        handler_file = next(f for f in files if f.path.name == "handler.py" and f.path.parent.name == "lambda")
        content = handler_file.content

        # Check for AWS Powertools imports or patterns
        assert "aws_lambda_powertools" in content or "powertools" in content or "logger" in content.lower()

        # Check for Lambda handler function
        assert "def handler" in content or "def lambda_handler" in content

        # Check for event/context parameters
        assert "event" in content and "context" in content


@pytest.mark.asyncio
async def test_aws_target_generate_openapi_schema_has_correct_paths(
    mock_aws_config, mock_single_agent_metadata
):
    """Test AWSTarget.generate creates OpenAPI schema with correct paths."""
    target = AWSTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_aws_config, mock_single_agent_metadata, output_dir)

        openapi_file = next(f for f in files if f.path.name == "openapi.yaml")
        content = openapi_file.content

        # Check for OpenAPI structure
        assert "openapi:" in content or "swagger:" in content
        assert "paths:" in content

        # Check for tool definitions (add and multiply from our test agent)
        assert "add" in content.lower() or "/add" in content
        assert "multiply" in content.lower() or "/multiply" in content


@pytest.mark.asyncio
async def test_aws_target_generate_cdk_app_content(mock_aws_config, mock_single_agent_metadata):
    """Test AWSTarget.generate creates CDK app.py with correct content."""
    target = AWSTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_aws_config, mock_single_agent_metadata, output_dir)

        app_file = next(f for f in files if f.path.name == "app.py" and f.path.parent == output_dir)
        content = app_file.content

        # Check for CDK app initialization
        assert "import aws_cdk" in content or "from aws_cdk import" in content
        assert "App()" in content or "cdk.App()" in content

        # Check for stack import
        assert "from stacks" in content or "import stacks" in content


@pytest.mark.asyncio
async def test_aws_target_generate_pyproject_toml_content(
    mock_aws_config, mock_single_agent_metadata
):
    """Test AWSTarget.generate creates pyproject.toml with correct dependencies."""
    target = AWSTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_aws_config, mock_single_agent_metadata, output_dir)

        pyproject_file = next(f for f in files if f.path.name == "pyproject.toml" and f.path.parent == output_dir)
        content = pyproject_file.content

        # Check for expected dependencies
        assert "aws-cdk-lib" in content
        assert "constructs" in content


@pytest.mark.asyncio
async def test_aws_target_generate_lambda_requirements_txt_content(
    mock_aws_config, mock_single_agent_metadata
):
    """Test AWSTarget.generate creates Lambda requirements.txt with correct dependencies."""
    target = AWSTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_aws_config, mock_single_agent_metadata, output_dir)

        lambda_req_file = next(
            f for f in files if f.path.name == "requirements.txt" and f.path.parent.name == "lambda"
        )
        content = lambda_req_file.content

        # Lambda template includes helpful comments about common dependencies
        assert "Lambda dependencies" in content
        assert "Add your dependencies below" in content


@pytest.mark.asyncio
async def test_aws_target_generate_env_example_content(mock_aws_config, mock_single_agent_metadata):
    """Test AWSTarget.generate creates .env.example with correct content."""
    target = AWSTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_aws_config, mock_single_agent_metadata, output_dir)

        env_file = next(f for f in files if f.path.name == ".env.example")
        content = env_file.content

        # Check for expected env vars
        assert "AWS" in content or "REGION" in content
        assert "us-east-1" in content  # From config


@pytest.mark.asyncio
async def test_aws_target_generate_makefile_content(mock_aws_config, mock_single_agent_metadata):
    """Test AWSTarget.generate creates Makefile with correct content."""
    target = AWSTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_aws_config, mock_single_agent_metadata, output_dir)

        makefile = next(f for f in files if f.path.name == "Makefile")
        content = makefile.content

        # Check for expected Makefile targets
        assert ".PHONY:" in content
        assert "cdk" in content.lower() or "deploy" in content.lower()


@pytest.mark.asyncio
async def test_aws_target_generate_with_default_config(mock_single_agent_metadata):
    """Test AWSTarget.generate uses default AWS config when target config is not AWS."""
    # Create config with AWS target but minimal settings
    config = BedsheetConfig(
        name="minimal-aws-test",
        agents=[
            AgentConfig(
                name="test",
                module="test.agent",
                class_name="TestAgent",
            )
        ],
        target="aws",
        targets={
            "aws": AWSTargetConfig(region="us-west-2"),
        },
    )

    target = AWSTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(config, mock_single_agent_metadata, output_dir)

        # Should still generate all files with defaults (includes debug-ui)
        assert len(files) == 14

        # Check that default Bedrock model is used
        stack_file = next(f for f in files if f.path.name == "agent_stack.py")
        # Default model should be claude from Bedrock
        assert "claude" in stack_file.content.lower() or "model" in stack_file.content.lower()


@pytest.mark.asyncio
async def test_aws_target_generate_supervisor_architecture(
    mock_aws_config, mock_supervisor_metadata
):
    """Test AWSTarget.generate creates appropriate architecture for supervisor."""
    target = AWSTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_aws_config, mock_supervisor_metadata, output_dir)

        stack_file = next(f for f in files if f.path.name == "agent_stack.py")
        content = stack_file.content

        # Check for multi-agent/orchestration patterns
        # The instruction contains "Coordinate multiple agents"
        assert "coordinate" in content.lower() or "multiagent" in content.lower()

        # Should still have Bedrock agent setup
        assert "bedrock" in content.lower() and "agent" in content.lower()
