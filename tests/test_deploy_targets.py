"""Tests for bedsheet.deploy.targets module."""
import tempfile
from pathlib import Path

import pytest

from bedsheet import Agent, ActionGroup
from bedsheet.deploy import (
    AgentConfig,
    BedsheetConfig,
    LocalTargetConfig,
)
from bedsheet.deploy.introspect import extract_agent_metadata
from bedsheet.deploy.targets import DeploymentTarget, GeneratedFile, LocalTarget
from bedsheet.testing import MockLLMClient, MockResponse


@pytest.fixture
def mock_config():
    """Create a mock BedsheetConfig for testing."""
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
        target="local",
        targets={
            "local": LocalTargetConfig(port=8080, hot_reload=True),
        },
    )


@pytest.fixture
async def mock_agent_metadata():
    """Create a mock AgentMetadata for testing."""
    mock = MockLLMClient([MockResponse(text="ok")])

    agent = Agent(
        name="TestAgent",
        instruction="Test agent for deployment",
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


def test_generated_file_dataclass():
    """Test GeneratedFile dataclass."""
    file = GeneratedFile(
        path=Path("/tmp/test.py"),
        content="print('hello')",
        executable=False,
    )
    assert file.path == Path("/tmp/test.py")
    assert file.content == "print('hello')"
    assert file.executable is False

    # Test default executable value
    file2 = GeneratedFile(path=Path("/tmp/script.sh"), content="#!/bin/bash")
    assert file2.executable is False


def test_local_target_name():
    """Test LocalTarget.name property."""
    target = LocalTarget()
    assert target.name == "local"


def test_local_target_validate_valid_config(mock_config):
    """Test LocalTarget.validate with valid config."""
    target = LocalTarget()
    errors = target.validate(mock_config)
    assert errors == []


def test_local_target_validate_invalid_port():
    """Test LocalTarget.validate with invalid port."""
    from pydantic import ValidationError

    # Pydantic validation should catch invalid port during config creation
    with pytest.raises(ValidationError):
        BedsheetConfig(
            name="test",
            agents=[
                AgentConfig(
                    name="test",
                    module="test.agent",
                    class_name="TestAgent",
                )
            ],
            target="local",
            targets={
                "local": LocalTargetConfig(port=99999),  # Invalid port
            },
        )


def test_local_target_validate_no_local_config():
    """Test LocalTarget.validate when no local config exists."""
    config = BedsheetConfig(
        name="test",
        agents=[
            AgentConfig(
                name="test",
                module="test.agent",
                class_name="TestAgent",
            )
        ],
        target="local",
        targets={
            "local": LocalTargetConfig(),  # Default config
        },
    )

    target = LocalTarget()
    errors = target.validate(config)
    assert errors == []


@pytest.mark.asyncio
async def test_local_target_generate_creates_all_files(mock_config, mock_agent_metadata):
    """Test LocalTarget.generate creates all expected files."""
    target = LocalTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_config, mock_agent_metadata, output_dir)

        # Check we got all expected files
        assert len(files) == 6

        file_names = [f.path.name for f in files]
        assert "Dockerfile" in file_names
        assert "docker-compose.yaml" in file_names
        assert "Makefile" in file_names
        assert ".env.example" in file_names
        assert "app.py" in file_names
        assert "pyproject.toml" in file_names

        # Check all are GeneratedFile instances
        for file in files:
            assert isinstance(file, GeneratedFile)
            assert isinstance(file.path, Path)
            assert isinstance(file.content, str)
            assert len(file.content) > 0


@pytest.mark.asyncio
async def test_local_target_generate_dockerfile_content(mock_config, mock_agent_metadata):
    """Test LocalTarget.generate creates Dockerfile with correct content."""
    target = LocalTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_config, mock_agent_metadata, output_dir)

        dockerfile = next(f for f in files if f.path.name == "Dockerfile")
        content = dockerfile.content

        # Check for expected Dockerfile elements
        assert "FROM python:3.11" in content
        assert "WORKDIR /app" in content
        assert "COPY deploy/local/pyproject.toml" in content
        assert "uv pip install" in content
        assert "COPY agents/" in content
        assert "COPY deploy/local/app.py" in content
        assert "EXPOSE 8080" in content  # From mock_config port
        assert 'CMD ["uvicorn"' in content


@pytest.mark.asyncio
async def test_local_target_generate_docker_compose_content(mock_config, mock_agent_metadata):
    """Test LocalTarget.generate creates docker-compose.yaml with correct content."""
    target = LocalTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_config, mock_agent_metadata, output_dir)

        compose_file = next(f for f in files if f.path.name == "docker-compose.yaml")
        content = compose_file.content

        # Check for expected docker-compose elements
        assert "version:" in content
        assert "services:" in content
        assert "test_agent:" in content  # Project name with underscores
        assert "8080:8080" in content  # Port mapping
        assert "ANTHROPIC_API_KEY" in content
        assert "context: ../.." in content  # Build context is project root
        assert "dockerfile: deploy/local/Dockerfile" in content
        # Since hot_reload is True in mock_config, should have volumes
        assert "volumes:" in content
        assert "../../agents:/app/agents" in content


@pytest.mark.asyncio
async def test_local_target_generate_app_py_content(mock_config, mock_agent_metadata):
    """Test LocalTarget.generate creates app.py with correct content."""
    target = LocalTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_config, mock_agent_metadata, output_dir)

        app_file = next(f for f in files if f.path.name == "app.py")
        content = app_file.content

        # Check for expected FastAPI app elements
        assert "from fastapi import FastAPI" in content
        assert 'title="test-agent"' in content  # Config name
        # New dynamic import pattern (injects AnthropicClient for target-agnostic agents)
        assert "import myapp.agents.calculator as _agent_module" in content
        assert "_configure_agent" in content  # AnthropicClient injection
        assert "AnthropicClient" in content
        assert "agent.name" in content  # Dynamic agent name
        assert "/invoke" in content
        assert "agent.invoke" in content  # Actually invokes the agent


@pytest.mark.asyncio
async def test_local_target_generate_app_py_sse_endpoint(mock_config, mock_agent_metadata):
    """Test LocalTarget.generate creates app.py with SSE streaming endpoint."""
    target = LocalTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_config, mock_agent_metadata, output_dir)

        app_file = next(f for f in files if f.path.name == "app.py")
        content = app_file.content

        # Check for SSE streaming endpoint
        assert "/invoke/stream" in content
        assert "StreamingResponse" in content
        assert "text/event-stream" in content
        assert "event_generator" in content
        assert "serialize_event" in content
        assert "CollaboratorEvent" in content
        # Check for proper SSE format
        assert 'data:' in content
        assert '"type": "done"' in content or "'type': 'done'" in content


@pytest.mark.asyncio
async def test_local_target_generate_env_example_content(mock_config, mock_agent_metadata):
    """Test LocalTarget.generate creates .env.example with correct content."""
    target = LocalTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_config, mock_agent_metadata, output_dir)

        env_file = next(f for f in files if f.path.name == ".env.example")
        content = env_file.content

        # Check for expected env vars
        assert "ANTHROPIC_API_KEY" in content
        assert "PORT=8080" in content  # From mock_config


@pytest.mark.asyncio
async def test_local_target_generate_pyproject_toml_content(mock_config, mock_agent_metadata):
    """Test LocalTarget.generate creates pyproject.toml with correct content."""
    target = LocalTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_config, mock_agent_metadata, output_dir)

        pyproject_file = next(f for f in files if f.path.name == "pyproject.toml")
        content = pyproject_file.content

        # Check for expected dependencies
        assert "fastapi" in content
        assert "uvicorn" in content
        assert "pydantic" in content
        assert "anthropic" in content
        assert "bedsheet" in content


@pytest.mark.asyncio
async def test_local_target_generate_makefile_content(mock_config, mock_agent_metadata):
    """Test LocalTarget.generate creates Makefile with correct content."""
    target = LocalTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(mock_config, mock_agent_metadata, output_dir)

        makefile = next(f for f in files if f.path.name == "Makefile")
        content = makefile.content

        # Check for expected Makefile targets
        assert ".PHONY:" in content
        assert "build:" in content
        assert "run:" in content
        assert "stop:" in content
        assert "clean:" in content
        assert "docker-compose" in content


@pytest.mark.asyncio
async def test_local_target_generate_with_default_port(mock_agent_metadata):
    """Test LocalTarget.generate uses default port when not specified."""
    config = BedsheetConfig(
        name="default-port-test",
        agents=[
            AgentConfig(
                name="test",
                module="test.agent",
                class_name="TestAgent",
            )
        ],
        target="local",
        targets={
            "local": LocalTargetConfig(),  # Default port (8000)
        },
    )

    target = LocalTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(config, mock_agent_metadata, output_dir)

        dockerfile = next(f for f in files if f.path.name == "Dockerfile")
        # Should use default port 8000
        assert "EXPOSE 8000" in dockerfile.content


@pytest.mark.asyncio
async def test_local_target_generate_without_hot_reload(mock_agent_metadata):
    """Test LocalTarget.generate without hot reload."""
    config = BedsheetConfig(
        name="no-hot-reload",
        agents=[
            AgentConfig(
                name="test",
                module="test.agent",
                class_name="TestAgent",
            )
        ],
        target="local",
        targets={
            "local": LocalTargetConfig(hot_reload=False),
        },
    )

    target = LocalTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        files = target.generate(config, mock_agent_metadata, output_dir)

        compose_file = next(f for f in files if f.path.name == "docker-compose.yaml")
        # Should NOT have volumes when hot_reload is False
        assert "volumes:" not in compose_file.content


def test_deployment_target_is_abstract():
    """Test that DeploymentTarget is abstract and cannot be instantiated."""
    with pytest.raises(TypeError):
        DeploymentTarget()  # Should raise TypeError for abstract class
