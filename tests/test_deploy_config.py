"""Tests for bedsheet.deploy.config module."""

import os
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from bedsheet.deploy import (
    AgentConfig,
    AWSDeploymentStyle,
    AWSTargetConfig,
    BedsheetConfig,
    EnhancementsConfig,
    GCPDeploymentStyle,
    GCPTargetConfig,
    LocalTargetConfig,
    load_config,
    save_config,
)


def test_local_target_config():
    """Test LocalTargetConfig validation."""
    config = LocalTargetConfig(port=8080, hot_reload=False)
    assert config.port == 8080
    assert config.hot_reload is False

    # Test defaults
    config = LocalTargetConfig()
    assert config.port == 8000
    assert config.hot_reload is True

    # Test validation
    with pytest.raises(ValidationError):
        LocalTargetConfig(port=99999)  # Invalid port


def test_aws_target_config():
    """Test AWSTargetConfig validation."""
    config = AWSTargetConfig(
        region="us-east-1",
        lambda_memory=1024,
        bedrock_model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        style=AWSDeploymentStyle.BEDROCK_NATIVE,
    )
    assert config.region == "us-east-1"
    assert config.lambda_memory == 1024
    assert config.style == AWSDeploymentStyle.BEDROCK_NATIVE

    # Test defaults
    config = AWSTargetConfig(region="eu-west-1")
    assert config.lambda_memory == 512
    assert config.style == AWSDeploymentStyle.SERVERLESS

    # Test invalid region
    with pytest.raises(ValidationError):
        AWSTargetConfig(region="invalid-region")


def test_gcp_target_config():
    """Test GCPTargetConfig validation."""
    config = GCPTargetConfig(
        project="my-project",
        region="us-central1",
        cloud_run_memory="1Gi",
        style=GCPDeploymentStyle.AGENT_ENGINE,
    )
    assert config.project == "my-project"
    assert config.cloud_run_memory == "1Gi"
    assert config.style == GCPDeploymentStyle.AGENT_ENGINE

    # Test defaults
    config = GCPTargetConfig(project="test-project")
    assert config.region == "europe-west1"
    assert config.cloud_run_memory == "512Mi"
    assert config.style == GCPDeploymentStyle.CLOUD_RUN

    # Test invalid memory format
    with pytest.raises(ValidationError):
        GCPTargetConfig(project="test", cloud_run_memory="512MB")  # Should be Mi or Gi


def test_agent_config():
    """Test AgentConfig validation."""
    config = AgentConfig(
        name="calculator",
        module="myapp.agents.calculator",
        class_name="CalculatorAgent",
        description="A calculator agent",
    )
    assert config.name == "calculator"
    assert config.module == "myapp.agents.calculator"
    assert config.class_name == "CalculatorAgent"
    assert config.description == "A calculator agent"

    # Test without optional description
    config = AgentConfig(
        name="weather",
        module="myapp.agents.weather",
        class_name="WeatherAgent",
    )
    assert config.description is None


def test_enhancements_config():
    """Test EnhancementsConfig validation."""
    config = EnhancementsConfig(trace=True, metrics=True, auth=False)
    assert config.trace is True
    assert config.metrics is True
    assert config.auth is False

    # Test defaults
    config = EnhancementsConfig()
    assert config.trace is False
    assert config.metrics is False
    assert config.auth is False


def test_bedsheet_config_validation():
    """Test BedsheetConfig validation."""
    config = BedsheetConfig(
        name="my-agent-system",
        agents=[
            AgentConfig(
                name="calculator",
                module="myapp.agents.calculator",
                class_name="CalculatorAgent",
            )
        ],
        target="local",
        targets={
            "local": LocalTargetConfig(port=8080),
        },
    )
    assert config.name == "my-agent-system"
    assert len(config.agents) == 1
    assert config.target == "local"
    assert isinstance(config.targets["local"], LocalTargetConfig)

    # Test that active target must exist
    with pytest.raises(ValidationError):
        BedsheetConfig(
            name="test",
            agents=[
                AgentConfig(name="test", module="test.agent", class_name="TestAgent")
            ],
            target="aws",  # Target doesn't exist in targets dict
            targets={"local": LocalTargetConfig()},
        )


def test_bedsheet_config_target_type_validation():
    """Test that target configs match their keys."""
    # This should work
    config = BedsheetConfig(
        name="test",
        agents=[AgentConfig(name="test", module="test.agent", class_name="TestAgent")],
        target="local",
        targets={
            "local": LocalTargetConfig(),
            "aws": AWSTargetConfig(region="us-east-1"),
        },
    )
    assert isinstance(config.targets["local"], LocalTargetConfig)
    assert isinstance(config.targets["aws"], AWSTargetConfig)

    # This should fail - wrong type for key
    with pytest.raises(ValidationError):
        BedsheetConfig(
            name="test",
            agents=[AgentConfig(name="test", module="test.agent", class_name="TestAgent")],
            target="local",
            targets={
                "local": AWSTargetConfig(region="us-east-1"),  # Wrong type!
            },
        )


def test_get_active_target_config():
    """Test getting active target config."""
    config = BedsheetConfig(
        name="test",
        agents=[AgentConfig(name="test", module="test.agent", class_name="TestAgent")],
        target="aws",
        targets={
            "local": LocalTargetConfig(),
            "aws": AWSTargetConfig(region="us-west-2"),
        },
    )

    active = config.get_active_target_config()
    assert isinstance(active, AWSTargetConfig)
    assert active.region == "us-west-2"


def test_save_and_load_config():
    """Test saving and loading config to/from YAML."""
    config = BedsheetConfig(
        name="test-agent",
        agents=[
            AgentConfig(
                name="calculator",
                module="myapp.agents.calculator",
                class_name="CalculatorAgent",
                description="Does math",
            ),
            AgentConfig(
                name="weather",
                module="myapp.agents.weather",
                class_name="WeatherAgent",
            ),
        ],
        target="local",
        targets={
            "local": LocalTargetConfig(port=8080, hot_reload=True),
            "aws": AWSTargetConfig(
                region="us-east-1",
                lambda_memory=1024,
                style=AWSDeploymentStyle.SERVERLESS,
            ),
            "gcp": GCPTargetConfig(
                project="my-project",
                region="us-central1",
                style=GCPDeploymentStyle.CLOUD_RUN,
            ),
        },
        enhancements=EnhancementsConfig(trace=True, metrics=False, auth=True),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "bedsheet.yaml"

        # Save
        save_config(config, config_path)
        assert config_path.exists()

        # Load
        loaded_config = load_config(config_path)
        assert loaded_config.name == config.name
        assert len(loaded_config.agents) == 2
        assert loaded_config.target == "local"
        assert loaded_config.enhancements.trace is True

        # Verify target configs
        assert isinstance(loaded_config.targets["local"], LocalTargetConfig)
        assert loaded_config.targets["local"].port == 8080
        assert isinstance(loaded_config.targets["aws"], AWSTargetConfig)
        assert loaded_config.targets["aws"].region == "us-east-1"
        assert isinstance(loaded_config.targets["gcp"], GCPTargetConfig)
        assert loaded_config.targets["gcp"].project == "my-project"


def test_env_var_interpolation():
    """Test environment variable interpolation in config."""
    # Set test env vars
    os.environ["TEST_PROJECT"] = "my-gcp-project"
    os.environ["TEST_REGION"] = "us-west-1"

    yaml_content = """
version: "1.0"
name: test-agent
agents:
  - name: test
    module: test.agent
    class_name: TestAgent
target: gcp
targets:
  gcp:
    project: ${TEST_PROJECT}
    region: ${TEST_REGION}
    cloud_run_memory: 512Mi
    model: claude-sonnet-4-5@20250929
    style: cloud_run
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "bedsheet.yaml"
        config_path.write_text(yaml_content)

        config = load_config(config_path)
        gcp_config = config.targets["gcp"]
        assert isinstance(gcp_config, GCPTargetConfig)
        assert gcp_config.project == "my-gcp-project"
        assert gcp_config.region == "us-west-1"

    # Clean up env vars
    del os.environ["TEST_PROJECT"]
    del os.environ["TEST_REGION"]


def test_env_var_with_default():
    """Test environment variable interpolation with default values."""
    yaml_content = """
version: "1.0"
name: test-agent
agents:
  - name: test
    module: test.agent
    class_name: TestAgent
target: gcp
targets:
  gcp:
    project: ${NONEXISTENT_VAR:-default-project}
    region: us-central1
    cloud_run_memory: 512Mi
    model: claude-sonnet-4-5@20250929
    style: cloud_run
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "bedsheet.yaml"
        config_path.write_text(yaml_content)

        config = load_config(config_path)
        gcp_config = config.targets["gcp"]
        assert isinstance(gcp_config, GCPTargetConfig)
        assert gcp_config.project == "default-project"


def test_env_var_missing_raises_error():
    """Test that missing env var without default raises error."""
    yaml_content = """
version: "1.0"
name: test-agent
agents:
  - name: test
    module: test.agent
    class_name: TestAgent
target: gcp
targets:
  gcp:
    project: ${NONEXISTENT_VAR}
    region: us-central1
    cloud_run_memory: 512Mi
    model: claude-sonnet-4-5@20250929
    style: cloud_run
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "bedsheet.yaml"
        config_path.write_text(yaml_content)

        with pytest.raises(ValueError, match="Environment variable 'NONEXISTENT_VAR' is not set"):
            load_config(config_path)


def test_load_config_file_not_found():
    """Test loading non-existent config file."""
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/bedsheet.yaml")


def test_load_config_empty_file():
    """Test loading empty config file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "empty.yaml"
        config_path.write_text("")

        with pytest.raises(ValueError, match="Empty config file"):
            load_config(config_path)


def test_extra_fields_forbidden():
    """Test that extra fields are not allowed."""
    with pytest.raises(ValidationError):
        LocalTargetConfig(port=8000, unknown_field="value")

    with pytest.raises(ValidationError):
        AWSTargetConfig(region="us-east-1", unknown_field="value")

    with pytest.raises(ValidationError):
        GCPTargetConfig(project="test", unknown_field="value")
