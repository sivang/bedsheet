# Bedsheet Deploy Module

Configuration and deployment utilities for Bedsheet agents.

## Overview

The deploy module provides:

1. **Configuration Models** - Pydantic v2 models for `bedsheet.yaml`
2. **Environment Variable Interpolation** - Support for `${VAR_NAME}` and `${VAR_NAME:-default}` syntax
3. **Multi-Target Support** - Configure local, AWS, and GCP deployments in a single file
4. **Validation** - Strong typing and validation for all configuration options

## Configuration Structure

A `bedsheet.yaml` file defines:

- **Project metadata** - Name and version
- **Agents** - List of agents to deploy with their module paths
- **Target** - Active deployment target (local, aws, or gcp)
- **Targets** - Configuration for each deployment target
- **Enhancements** - Optional features like tracing, metrics, auth

## Example Configuration

```yaml
version: "1.0"
name: customer-support-system

agents:
  - name: calculator
    module: myapp.agents.calculator
    class_name: CalculatorAgent
    description: Performs calculations

  - name: weather
    module: myapp.agents.weather
    class_name: WeatherAgent
    description: Weather forecasts

target: local

targets:
  local:
    port: 8000
    hot_reload: true

  aws:
    region: us-east-1
    lambda_memory: 512
    bedrock_model: anthropic.claude-sonnet-4-5-v2:0
    style: serverless

  gcp:
    project: ${GCP_PROJECT_ID:-my-project}
    region: us-central1
    cloud_run_memory: 512Mi
    model: claude-sonnet-4-5@20250929
    style: cloud_run

enhancements:
  trace: false
  metrics: false
  auth: false
```

## Usage

### Loading Configuration

```python
from bedsheet.deploy import load_config

# Load from YAML file
config = load_config("bedsheet.yaml")

# Access project info
print(config.name)
print(config.target)

# Get active target configuration
target_config = config.get_active_target_config()
if isinstance(target_config, LocalTargetConfig):
    print(f"Running on port {target_config.port}")
```

### Creating Configuration Programmatically

```python
from bedsheet.deploy import (
    BedsheetConfig,
    AgentConfig,
    LocalTargetConfig,
    AWSTargetConfig,
    save_config,
)

config = BedsheetConfig(
    name="my-system",
    agents=[
        AgentConfig(
            name="agent1",
            module="myapp.agent",
            class_name="Agent1",
        )
    ],
    target="local",
    targets={
        "local": LocalTargetConfig(port=8080),
        "aws": AWSTargetConfig(region="us-west-2"),
    },
)

# Save to file
save_config(config, "bedsheet.yaml")
```

### Environment Variables

The config loader supports environment variable interpolation:

```yaml
targets:
  gcp:
    project: ${GCP_PROJECT_ID}              # Required - fails if not set
    region: ${GCP_REGION:-us-central1}      # Optional - uses default if not set
```

## Target Types

### Local Target

For local development:

```python
LocalTargetConfig(
    port=8000,         # Port number (1-65535)
    hot_reload=True,   # Enable hot reload
)
```

### AWS Target

For AWS deployments:

```python
AWSTargetConfig(
    region="us-east-1",                              # AWS region
    lambda_memory=512,                               # Lambda memory in MB (128-10240)
    bedrock_model="anthropic.claude-sonnet-4-5-v2:0",  # Bedrock model ID
    style=AWSDeploymentStyle.SERVERLESS,             # Deployment style
)
```

Deployment styles:
- `bedrock_native` - AWS Bedrock Agents
- `serverless` - Lambda + API Gateway
- `containers` - ECS/Fargate

### GCP Target

For GCP deployments:

```python
GCPTargetConfig(
    project="my-gcp-project",                    # GCP project ID
    region="us-central1",                        # GCP region
    cloud_run_memory="512Mi",                    # Memory limit (e.g., "512Mi", "1Gi")
    model="claude-sonnet-4-5@20250929",          # Vertex AI model
    style=GCPDeploymentStyle.CLOUD_RUN,          # Deployment style
)
```

Deployment styles:
- `agent_engine` - Vertex AI Agent Engine
- `cloud_run` - Cloud Run containers
- `cloud_functions` - Cloud Functions

## Validation

All configurations are validated using Pydantic v2:

- **Type checking** - Ensures correct types for all fields
- **Value constraints** - Port ranges, memory limits, etc.
- **Format validation** - AWS regions, GCP memory formats
- **Required fields** - Errors if required fields missing
- **No extra fields** - Rejects unknown configuration options

## API Reference

### Classes

- `BedsheetConfig` - Root configuration model
- `AgentConfig` - Single agent configuration
- `LocalTargetConfig` - Local deployment settings
- `AWSTargetConfig` - AWS deployment settings
- `GCPTargetConfig` - GCP deployment settings
- `EnhancementsConfig` - Optional enhancements
- `AWSDeploymentStyle` - AWS deployment style enum
- `GCPDeploymentStyle` - GCP deployment style enum

### Functions

- `load_config(path: str | Path) -> BedsheetConfig` - Load and validate YAML config
- `save_config(config: BedsheetConfig, path: str | Path) -> None` - Save config to YAML

## Examples

See:
- `/examples/bedsheet.yaml` - Example configuration file
- `/examples/config_usage.py` - Programmatic usage examples
- `/tests/test_deploy_config.py` - Comprehensive test suite
