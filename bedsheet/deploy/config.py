"""
Pydantic models for bedsheet.yaml configuration.

Supports environment variable interpolation using ${VAR_NAME} syntax.
"""

import os
import re
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field, field_validator, model_validator


class AWSDeploymentStyle(str, Enum):
    """AWS deployment styles."""

    BEDROCK_NATIVE = "bedrock_native"
    SERVERLESS = "serverless"
    CONTAINERS = "containers"


class GCPDeploymentStyle(str, Enum):
    """GCP deployment styles."""

    AGENT_ENGINE = "agent_engine"
    CLOUD_RUN = "cloud_run"
    CLOUD_FUNCTIONS = "cloud_functions"


class LocalTargetConfig(BaseModel):
    """Configuration for local development target."""

    port: int = Field(default=8000, ge=1, le=65535)
    hot_reload: bool = Field(default=True)

    model_config = {"extra": "forbid"}


class AWSTargetConfig(BaseModel):
    """Configuration for AWS deployment target."""

    region: str = Field(..., description="AWS region (e.g., us-east-1)")
    lambda_memory: int = Field(default=512, ge=128, le=10240, description="Lambda memory in MB")
    bedrock_model: str = Field(
        default="anthropic.claude-sonnet-4-5-v2:0",
        description="Bedrock model ID",
    )
    style: AWSDeploymentStyle = Field(
        default=AWSDeploymentStyle.SERVERLESS,
        description="Deployment style: bedrock_native, serverless, or containers",
    )
    enable_delegate_for_supervisors: bool = Field(
        default=True,
        description="Enable delegate action for supervisor agents to improve trace visibility. "
        "Can be disabled when AWS improves native multi-agent collaboration traces.",
    )

    model_config = {"extra": "forbid"}

    @field_validator("region")
    @classmethod
    def validate_region(cls, v: str) -> str:
        """Validate AWS region format."""
        # Basic validation - AWS regions follow pattern like us-east-1, eu-west-2
        if not re.match(r"^[a-z]{2}-[a-z]+-\d+$", v):
            raise ValueError(f"Invalid AWS region format: {v}")
        return v


class GCPTargetConfig(BaseModel):
    """Configuration for GCP deployment target."""

    project: str = Field(..., description="GCP project ID")
    region: str = Field(default="europe-west1", description="GCP region")
    cloud_run_memory: str = Field(default="512Mi", description="Cloud Run memory limit")
    model: str = Field(
        default="gemini-2.0-flash-001",
        description="Model ID (gemini-2.0-flash recommended via global endpoint)",
    )
    style: GCPDeploymentStyle = Field(
        default=GCPDeploymentStyle.CLOUD_RUN,
        description="Deployment style: agent_engine, cloud_run, or cloud_functions",
    )
    builtin_tools: list[str] = Field(
        default=[],
        description="ADK built-in tools to enable: google_search, code_execution",
    )

    model_config = {"extra": "forbid"}

    @field_validator("cloud_run_memory")
    @classmethod
    def validate_memory(cls, v: str) -> str:
        """Validate Cloud Run memory format."""
        if not re.match(r"^\d+(Mi|Gi)$", v):
            raise ValueError(f"Invalid memory format: {v}. Use format like '512Mi' or '1Gi'")
        return v

    @field_validator("builtin_tools")
    @classmethod
    def validate_builtin_tools(cls, v: list[str]) -> list[str]:
        """Validate ADK built-in tool names."""
        valid_tools = {"google_search", "code_execution"}
        for tool in v:
            if tool not in valid_tools:
                raise ValueError(
                    f"Invalid built-in tool: {tool}. Valid options: {', '.join(sorted(valid_tools))}"
                )
        return v


class AgentCoreTargetConfig(BaseModel):
    """Configuration for Amazon Bedrock AgentCore deployment target.

    .. warning:: EXPERIMENTAL
       This target is experimental. AgentCore is in preview and APIs may change.
       Report bugs at: https://github.com/sivang/bedsheet/issues
    """

    region: str = Field(..., description="AWS region (e.g., us-east-1)")
    runtime_memory: int = Field(
        default=1024,
        ge=512,
        le=8192,
        description="AgentCore Runtime memory in MB",
    )
    runtime_vcpu: float = Field(
        default=0.5,
        ge=0.25,
        le=4,
        description="AgentCore Runtime vCPU allocation",
    )
    lambda_memory: int = Field(
        default=512,
        ge=128,
        le=10240,
        description="Lambda memory in MB for Gateway tools",
    )
    bedrock_model: str = Field(
        default="anthropic.claude-sonnet-4-5-v2:0",
        description="Bedrock model ID for the agent",
    )
    ecr_repository: str = Field(
        default="",
        description="ECR repository name (auto-generated if empty)",
    )

    model_config = {"extra": "forbid"}

    @field_validator("region")
    @classmethod
    def validate_region(cls, v: str) -> str:
        """Validate AWS region format."""
        if not re.match(r"^[a-z]{2}-[a-z]+-\d+$", v):
            raise ValueError(f"Invalid AWS region format: {v}")
        return v


class AgentConfig(BaseModel):
    """Configuration for a single agent."""

    name: str = Field(..., description="Agent name")
    module: str = Field(..., description="Python module path (e.g., myapp.agents.calculator)")
    class_name: str = Field(..., description="Agent class name")
    description: Optional[str] = Field(None, description="Agent description for supervisor")

    model_config = {"extra": "forbid"}


class EnhancementsConfig(BaseModel):
    """Optional enhancements configuration."""

    trace: bool = Field(default=False, description="Enable tracing/observability")
    metrics: bool = Field(default=False, description="Enable metrics collection")
    auth: bool = Field(default=False, description="Enable authentication")

    model_config = {"extra": "forbid"}


class BedsheetConfig(BaseModel):
    """Root configuration for Bedsheet deployment."""

    version: Literal["1.0"] = Field(default="1.0", description="Config version")
    name: str = Field(..., description="Project name")
    agents: list[AgentConfig] = Field(..., description="List of agents to deploy")
    target: str = Field(..., description="Active target: local, aws, or gcp")
    targets: dict[str, LocalTargetConfig | AWSTargetConfig | GCPTargetConfig | AgentCoreTargetConfig] = Field(
        ..., description="Target configurations"
    )
    enhancements: EnhancementsConfig = Field(
        default_factory=EnhancementsConfig,
        description="Optional enhancements",
    )

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def validate_target_exists(self) -> "BedsheetConfig":
        """Validate that active target exists in targets dict."""
        if self.target not in self.targets:
            raise ValueError(
                f"Active target '{self.target}' not found in targets. "
                f"Available targets: {', '.join(self.targets.keys())}"
            )
        return self

    @model_validator(mode="after")
    def validate_target_types(self) -> "BedsheetConfig":
        """Validate that target configs match their keys."""
        for key, config in self.targets.items():
            if key == "local" and not isinstance(config, LocalTargetConfig):
                raise ValueError("Target 'local' must use LocalTargetConfig")
            elif key == "aws" and not isinstance(config, AWSTargetConfig):
                raise ValueError("Target 'aws' must use AWSTargetConfig")
            elif key == "gcp" and not isinstance(config, GCPTargetConfig):
                raise ValueError("Target 'gcp' must use GCPTargetConfig")
            elif key == "agentcore" and not isinstance(config, AgentCoreTargetConfig):
                raise ValueError("Target 'agentcore' must use AgentCoreTargetConfig")
        return self

    def get_active_target_config(
        self,
    ) -> LocalTargetConfig | AWSTargetConfig | GCPTargetConfig | AgentCoreTargetConfig:
        """Get the configuration for the active target."""
        return self.targets[self.target]


def _interpolate_env_vars(data: Any) -> Any:
    """
    Recursively interpolate environment variables in data structures.

    Supports ${VAR_NAME} and ${VAR_NAME:-default} syntax.

    Args:
        data: Data structure (dict, list, str, etc.) to interpolate

    Returns:
        Data with environment variables replaced

    Raises:
        ValueError: If required environment variable is not set
    """
    if isinstance(data, dict):
        return {key: _interpolate_env_vars(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_interpolate_env_vars(item) for item in data]
    elif isinstance(data, str):
        # Pattern matches ${VAR} or ${VAR:-default}
        pattern = r"\$\{([^}:]+)(?::-([^}]*))?\}"

        def replace_var(match: re.Match) -> str:
            var_name = match.group(1)
            default_value = match.group(2)

            value = os.environ.get(var_name)
            if value is None:
                if default_value is not None:
                    return default_value
                raise ValueError(
                    f"Environment variable '{var_name}' is not set and no default provided"
                )
            return value

        return re.sub(pattern, replace_var, data)
    else:
        return data


def load_config(path: str | Path) -> BedsheetConfig:
    """
    Load and validate Bedsheet configuration from YAML file.

    Supports environment variable interpolation using ${VAR_NAME} or ${VAR_NAME:-default}.

    Args:
        path: Path to bedsheet.yaml file

    Returns:
        Validated BedsheetConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid or env vars missing
        yaml.YAMLError: If YAML is malformed
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r") as f:
        raw_data = yaml.safe_load(f)

    if raw_data is None:
        raise ValueError(f"Empty config file: {path}")

    # Interpolate environment variables
    interpolated_data = _interpolate_env_vars(raw_data)

    # Parse targets with proper type discrimination
    if "targets" in interpolated_data:
        targets: dict[str, LocalTargetConfig | AWSTargetConfig | GCPTargetConfig | AgentCoreTargetConfig] = {}
        for key, config in interpolated_data["targets"].items():
            if key == "local":
                targets[key] = LocalTargetConfig(**config)
            elif key in ("aws", "aws-terraform"):
                targets[key] = AWSTargetConfig(**config)
            elif key == "gcp":
                targets[key] = GCPTargetConfig(**config)
            elif key == "agentcore":
                targets[key] = AgentCoreTargetConfig(**config)
            else:
                raise ValueError(f"Unknown target type: {key}. Must be 'local', 'aws', 'aws-terraform', 'gcp', or 'agentcore'")
        interpolated_data["targets"] = targets

    return BedsheetConfig(**interpolated_data)


def save_config(config: BedsheetConfig, path: str | Path) -> None:
    """
    Save Bedsheet configuration to YAML file.

    Args:
        config: BedsheetConfig instance to save
        path: Path to save bedsheet.yaml file

    Raises:
        OSError: If file cannot be written
    """
    path = Path(path)

    # Convert to dict using Pydantic's model_dump
    data = config.model_dump(mode="json", exclude_none=True)

    # Write YAML with nice formatting
    with path.open("w") as f:
        yaml.safe_dump(
            data,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            indent=2,
        )
