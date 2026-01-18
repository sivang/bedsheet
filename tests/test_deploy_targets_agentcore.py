"""Tests for bedsheet.deploy.targets.agentcore module."""
import tempfile
from pathlib import Path

import pytest

from bedsheet import Agent, ActionGroup, Supervisor
from bedsheet.deploy import (
    AgentConfig,
    BedsheetConfig,
    AgentCoreTargetConfig,
)
from bedsheet.deploy.introspect import extract_agent_metadata
from bedsheet.deploy.targets import AgentCoreTarget, GeneratedFile
from bedsheet.testing import MockLLMClient, MockResponse


@pytest.fixture
def mock_agentcore_config():
    """Create a mock BedsheetConfig for AgentCore testing."""
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
        target="agentcore",
        targets={
            "agentcore": AgentCoreTargetConfig(
                region="us-east-1",
                runtime_memory=1024,
                runtime_vcpu=0.5,
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
        instruction="Test agent for AgentCore deployment",
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


def test_agentcore_target_name():
    """Test AgentCoreTarget.name property."""
    target = AgentCoreTarget()
    assert target.name == "agentcore"


def test_agentcore_target_validate_valid_config(mock_agentcore_config):
    """Test AgentCoreTarget.validate with valid config."""
    target = AgentCoreTarget()
    errors = target.validate(mock_agentcore_config)
    assert errors == []


def test_agentcore_target_validate_invalid_lambda_memory_too_low():
    """Test AgentCoreTarget.validate with Lambda memory too low."""
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
            target="agentcore",
            targets={
                "agentcore": AgentCoreTargetConfig(region="us-east-1", lambda_memory=64),
            },
        )


def test_agentcore_target_validate_invalid_lambda_memory_too_high():
    """Test AgentCoreTarget.validate with Lambda memory too high."""
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
            target="agentcore",
            targets={
                "agentcore": AgentCoreTargetConfig(region="us-east-1", lambda_memory=20000),
            },
        )


def test_agentcore_target_validate_invalid_runtime_memory_too_low():
    """Test AgentCoreTarget.validate with Runtime memory too low."""
    with pytest.raises(ValueError, match="greater than or equal to 512"):
        BedsheetConfig(
            name="test",
            agents=[
                AgentConfig(
                    name="test",
                    module="test.agent",
                    class_name="TestAgent",
                )
            ],
            target="agentcore",
            targets={
                "agentcore": AgentCoreTargetConfig(region="us-east-1", runtime_memory=256),
            },
        )


def test_agentcore_target_validate_invalid_runtime_memory_too_high():
    """Test AgentCoreTarget.validate with Runtime memory too high."""
    with pytest.raises(ValueError, match="less than or equal to 8192"):
        BedsheetConfig(
            name="test",
            agents=[
                AgentConfig(
                    name="test",
                    module="test.agent",
                    class_name="TestAgent",
                )
            ],
            target="agentcore",
            targets={
                "agentcore": AgentCoreTargetConfig(region="us-east-1", runtime_memory=16384),
            },
        )


def test_agentcore_target_validate_invalid_runtime_vcpu():
    """Test AgentCoreTarget.validate with invalid Runtime vCPU."""
    with pytest.raises(ValueError, match="greater than or equal to 0.25"):
        BedsheetConfig(
            name="test",
            agents=[
                AgentConfig(
                    name="test",
                    module="test.agent",
                    class_name="TestAgent",
                )
            ],
            target="agentcore",
            targets={
                "agentcore": AgentCoreTargetConfig(region="us-east-1", runtime_vcpu=0.1),
            },
        )


def test_agentcore_target_validate_invalid_region():
    """Test AgentCoreTarget.validate with invalid region format."""
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
            target="agentcore",
            targets={
                "agentcore": AgentCoreTargetConfig(region="invalid-region-format"),
            },
        )


def test_agentcore_target_validate_no_agentcore_config():
    """Test AgentCoreTarget.validate when no AgentCore config exists."""
    config = BedsheetConfig(
        name="test",
        agents=[
            AgentConfig(
                name="test",
                module="test.agent",
                class_name="TestAgent",
            )
        ],
        target="agentcore",
        targets={
            "agentcore": AgentCoreTargetConfig(region="us-east-1"),
        },
    )

    target = AgentCoreTarget()
    errors = target.validate(config)
    assert errors == []


@pytest.mark.asyncio
async def test_agentcore_target_generate_creates_all_files(mock_agentcore_config, mock_single_agent_metadata):
    """Test AgentCoreTarget.generate creates all expected files."""
    target = AgentCoreTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_agentcore_config, mock_single_agent_metadata, output_dir)

        # Check we got all expected files
        # Terraform: 4, Common: 3, Runtime: 3, Lambda: 3, Schemas: 1, GitHub: 2 = 16 total
        assert len(files) == 16

        file_names = [f.path.name for f in files]
        # Terraform files
        assert "main.tf" in file_names
        assert "variables.tf" in file_names
        assert "outputs.tf" in file_names
        assert "terraform.tfvars.example" in file_names
        # Common files
        assert "pyproject.toml" in file_names
        assert "Makefile" in file_names
        assert ".env.example" in file_names
        # Runtime files
        assert "Dockerfile" in [f.path.name for f in files if f.path.parent.name == "runtime"]
        assert "app.py" in [f.path.name for f in files if f.path.parent.name == "runtime"]
        assert "requirements.txt" in [f.path.name for f in files if f.path.parent.name == "runtime"]
        # Lambda files
        assert "handler.py" in [f.path.name for f in files if f.path.parent.name == "lambda"]
        assert "__init__.py" in [f.path.name for f in files if f.path.parent.name == "lambda"]
        assert "requirements.txt" in [f.path.name for f in files if f.path.parent.name == "lambda"]
        # Schema files
        assert "openapi.yaml" in [f.path.name for f in files if f.path.parent.name == "schemas"]
        # GitHub workflow files
        assert "ci.yaml" in [f.path.name for f in files if f.path.parent.name == "workflows"]
        assert "deploy.yaml" in [f.path.name for f in files if f.path.parent.name == "workflows"]

        # Check all are GeneratedFile instances
        for file in files:
            assert isinstance(file, GeneratedFile)
            assert isinstance(file.path, Path)
            assert isinstance(file.content, str)
            # Some files like __init__.py can be empty
            assert file.content is not None


@pytest.mark.asyncio
async def test_agentcore_target_generate_terraform_main_content(mock_agentcore_config, mock_single_agent_metadata):
    """Test AgentCoreTarget.generate creates Terraform main.tf with AgentCore resources."""
    target = AgentCoreTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_agentcore_config, mock_single_agent_metadata, output_dir)

        main_tf = next(f for f in files if f.path.name == "main.tf")
        content = main_tf.content

        # Check for Terraform structure
        assert "terraform" in content.lower()
        assert "required_providers" in content or "provider" in content

        # Check for AgentCore resources
        assert "aws_bedrockagentcore" in content or "bedrockagentcore" in content or "agentcore" in content.lower()

        # Check for ECR repository
        assert "ecr" in content.lower()

        # Check for Lambda (for tools)
        assert "lambda" in content.lower()

        # Check for IAM roles
        assert "iam" in content.lower()


@pytest.mark.asyncio
async def test_agentcore_target_generate_runtime_dockerfile_content(mock_agentcore_config, mock_single_agent_metadata):
    """Test AgentCoreTarget.generate creates ARM64 Dockerfile for AgentCore."""
    target = AgentCoreTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_agentcore_config, mock_single_agent_metadata, output_dir)

        dockerfile = next(f for f in files if f.path.name == "Dockerfile" and f.path.parent.name == "runtime")
        content = dockerfile.content

        # Check for ARM64 platform (required by AgentCore)
        assert "arm64" in content.lower() or "aarch64" in content.lower() or "--platform" in content

        # Check for Python base image
        assert "python" in content.lower()

        # Check for port 8080 exposure (AgentCore requirement)
        assert "8080" in content


@pytest.mark.asyncio
async def test_agentcore_target_generate_runtime_app_content(mock_agentcore_config, mock_single_agent_metadata):
    """Test AgentCoreTarget.generate creates runtime app with AgentCore endpoints."""
    target = AgentCoreTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_agentcore_config, mock_single_agent_metadata, output_dir)

        app_file = next(f for f in files if f.path.name == "app.py" and f.path.parent.name == "runtime")
        content = app_file.content

        # Check for FastAPI or similar framework
        assert "fastapi" in content.lower() or "starlette" in content.lower() or "flask" in content.lower()

        # Check for AgentCore HTTP protocol endpoints
        assert "/invocations" in content  # POST endpoint
        assert "/ping" in content or "ping" in content  # GET health check

        # Check for SSE streaming (AgentCore requirement)
        assert "stream" in content.lower() or "event" in content.lower()


@pytest.mark.asyncio
async def test_agentcore_target_generate_lambda_handler_content(mock_agentcore_config, mock_single_agent_metadata):
    """Test AgentCoreTarget.generate creates Lambda handler for tools."""
    target = AgentCoreTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_agentcore_config, mock_single_agent_metadata, output_dir)

        handler_file = next(f for f in files if f.path.name == "handler.py" and f.path.parent.name == "lambda")
        content = handler_file.content

        # Check for Lambda handler function
        assert "def handler" in content or "def lambda_handler" in content

        # Check for event/context parameters
        assert "event" in content

        # Check for tool handlers from our test agent (add and multiply)
        assert "add" in content.lower() or "multiply" in content.lower()


@pytest.mark.asyncio
async def test_agentcore_target_generate_openapi_schema_has_correct_paths(
    mock_agentcore_config, mock_single_agent_metadata
):
    """Test AgentCoreTarget.generate creates OpenAPI schema with correct paths."""
    target = AgentCoreTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_agentcore_config, mock_single_agent_metadata, output_dir)

        openapi_file = next(f for f in files if f.path.name == "openapi.yaml")
        content = openapi_file.content

        # Check for OpenAPI structure
        assert "openapi:" in content or "swagger:" in content
        assert "paths:" in content

        # Check for tool definitions (add and multiply from our test agent)
        assert "add" in content.lower() or "/add" in content
        assert "multiply" in content.lower() or "/multiply" in content


@pytest.mark.asyncio
async def test_agentcore_target_generate_outputs_tf_content(mock_agentcore_config, mock_single_agent_metadata):
    """Test AgentCoreTarget.generate creates outputs.tf with correct outputs."""
    target = AgentCoreTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_agentcore_config, mock_single_agent_metadata, output_dir)

        outputs_file = next(f for f in files if f.path.name == "outputs.tf")
        content = outputs_file.content

        # Check for expected outputs
        assert "output" in content
        assert "runtime" in content.lower() or "endpoint" in content.lower()


@pytest.mark.asyncio
async def test_agentcore_target_generate_variables_tf_content(mock_agentcore_config, mock_single_agent_metadata):
    """Test AgentCoreTarget.generate creates variables.tf with correct variables."""
    target = AgentCoreTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_agentcore_config, mock_single_agent_metadata, output_dir)

        variables_file = next(f for f in files if f.path.name == "variables.tf")
        content = variables_file.content

        # Check for variable definitions
        assert "variable" in content
        assert "region" in content.lower() or "aws_region" in content.lower()


@pytest.mark.asyncio
async def test_agentcore_target_generate_pyproject_toml_content(mock_agentcore_config, mock_single_agent_metadata):
    """Test AgentCoreTarget.generate creates pyproject.toml with correct dependencies."""
    target = AgentCoreTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_agentcore_config, mock_single_agent_metadata, output_dir)

        pyproject_file = next(f for f in files if f.path.name == "pyproject.toml" and f.path.parent == output_dir)
        content = pyproject_file.content

        # Check for project name
        assert "test-agent" in content or "test_agent" in content

        # Check for dependencies section
        assert "dependencies" in content


@pytest.mark.asyncio
async def test_agentcore_target_generate_makefile_content(mock_agentcore_config, mock_single_agent_metadata):
    """Test AgentCoreTarget.generate creates Makefile with correct targets."""
    target = AgentCoreTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_agentcore_config, mock_single_agent_metadata, output_dir)

        makefile = next(f for f in files if f.path.name == "Makefile")
        content = makefile.content

        # Check for expected Makefile targets
        assert ".PHONY:" in content
        assert "terraform" in content.lower() or "deploy" in content.lower() or "build" in content.lower()


@pytest.mark.asyncio
async def test_agentcore_target_generate_env_example_content(mock_agentcore_config, mock_single_agent_metadata):
    """Test AgentCoreTarget.generate creates .env.example with correct content."""
    target = AgentCoreTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_agentcore_config, mock_single_agent_metadata, output_dir)

        env_file = next(f for f in files if f.path.name == ".env.example")
        content = env_file.content

        # Check for expected env vars
        assert "AWS" in content or "REGION" in content
        assert "us-east-1" in content  # From config


@pytest.mark.asyncio
async def test_agentcore_target_generate_ci_workflow_content(mock_agentcore_config, mock_single_agent_metadata):
    """Test AgentCoreTarget.generate creates CI workflow with correct content."""
    target = AgentCoreTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_agentcore_config, mock_single_agent_metadata, output_dir)

        ci_file = next(f for f in files if f.path.name == "ci.yaml")
        content = ci_file.content

        # Check for GitHub Actions structure
        assert "name:" in content
        assert "on:" in content
        assert "jobs:" in content

        # Check for CI steps
        assert "test" in content.lower() or "lint" in content.lower()


@pytest.mark.asyncio
async def test_agentcore_target_generate_deploy_workflow_content(mock_agentcore_config, mock_single_agent_metadata):
    """Test AgentCoreTarget.generate creates deploy workflow with correct content."""
    target = AgentCoreTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_agentcore_config, mock_single_agent_metadata, output_dir)

        deploy_file = next(f for f in files if f.path.name == "deploy.yaml")
        content = deploy_file.content

        # Check for GitHub Actions structure
        assert "name:" in content
        assert "on:" in content
        assert "jobs:" in content

        # Check for deploy steps
        assert "terraform" in content.lower() or "deploy" in content.lower()
        assert "aws" in content.lower()


@pytest.mark.asyncio
async def test_agentcore_target_generate_with_default_config(mock_single_agent_metadata):
    """Test AgentCoreTarget.generate uses default AgentCore config when target config is not AgentCore."""
    # Create config with AgentCore target but minimal settings
    config = BedsheetConfig(
        name="minimal-agentcore-test",
        agents=[
            AgentConfig(
                name="test",
                module="test.agent",
                class_name="TestAgent",
            )
        ],
        target="agentcore",
        targets={
            "agentcore": AgentCoreTargetConfig(region="us-west-2"),
        },
    )

    target = AgentCoreTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(config, mock_single_agent_metadata, output_dir)

        # Should still generate all files with defaults
        assert len(files) == 16


@pytest.mark.asyncio
async def test_agentcore_target_generate_supervisor_filters_delegate_tool(
    mock_agentcore_config, mock_supervisor_metadata
):
    """Test AgentCoreTarget.generate filters out delegate tool for supervisors."""
    target = AgentCoreTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_agentcore_config, mock_supervisor_metadata, output_dir)

        # The supervisor only has the 'delegate' tool which gets filtered out
        # AgentCore uses native agent-to-agent protocol, so no Lambda handler is generated
        # when there are no other tools
        lambda_handlers = [f for f in files if f.path.name == "handler.py" and f.path.parent.name == "lambda"]

        # Since delegate is the only tool and it's filtered, no Lambda files should exist
        assert len(lambda_handlers) == 0

        # Check OpenAPI schema doesn't have delegate tool
        openapi_file = next(f for f in files if f.path.name == "openapi.yaml")
        openapi_content = openapi_file.content.lower()
        # delegate should not be in the OpenAPI schema since it's filtered
        # Note: The schema is generated from filtered_agent, not original agent
        assert "delegate" not in openapi_content


@pytest.mark.asyncio
async def test_agentcore_target_generate_supervisor_architecture(
    mock_agentcore_config, mock_supervisor_metadata
):
    """Test AgentCoreTarget.generate creates appropriate architecture for supervisor."""
    target = AgentCoreTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_agentcore_config, mock_supervisor_metadata, output_dir)

        # Check runtime app contains supervisor-related content
        app_file = next(f for f in files if f.path.name == "app.py" and f.path.parent.name == "runtime")
        content = app_file.content

        # The app should handle invocations (agents are coordinated by AgentCore)
        assert "/invocations" in content


@pytest.mark.asyncio
async def test_agentcore_target_generate_agent_without_tools():
    """Test AgentCoreTarget.generate for an agent without any tools."""
    mock = MockLLMClient([MockResponse(text="ok")])

    # Agent with no action groups (no tools)
    agent = Agent(
        name="NoToolsAgent",
        instruction="I have no tools",
        model_client=mock,
    )

    metadata = extract_agent_metadata(agent)

    config = BedsheetConfig(
        name="no-tools-test",
        agents=[
            AgentConfig(
                name="notools",
                module="test.agent",
                class_name="NoToolsAgent",
            )
        ],
        target="agentcore",
        targets={
            "agentcore": AgentCoreTargetConfig(region="us-east-1"),
        },
    )

    target = AgentCoreTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(config, metadata, output_dir)

        # Should generate fewer files (no Lambda files)
        # Terraform: 4, Common: 3, Runtime: 3, Schemas: 1, GitHub: 2 = 13 total (no Lambda)
        assert len(files) == 13

        file_names = [f.path.name for f in files]
        # Lambda files should NOT be present
        lambda_files = [f.path.name for f in files if f.path.parent.name == "lambda"]
        assert "handler.py" not in lambda_files
        assert "handler.py" not in file_names or len(lambda_files) == 0
