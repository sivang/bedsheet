"""
Example: Using Bedsheet deployment configuration.

This example demonstrates how to:
1. Create configurations programmatically
2. Load configurations from YAML files
3. Access target-specific settings
4. Use environment variable interpolation
"""

from pathlib import Path

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


def example_create_config_programmatically():
    """Create a Bedsheet configuration programmatically."""
    print("=== Creating Config Programmatically ===\n")

    config = BedsheetConfig(
        name="my-agent-system",
        agents=[
            AgentConfig(
                name="calculator",
                module="myapp.agents.calculator",
                class_name="CalculatorAgent",
                description="Performs mathematical operations",
            ),
            AgentConfig(
                name="weather",
                module="myapp.agents.weather",
                class_name="WeatherAgent",
                description="Provides weather forecasts",
            ),
        ],
        target="local",
        targets={
            "local": LocalTargetConfig(
                port=8080,
                hot_reload=True,
            ),
            "aws": AWSTargetConfig(
                region="us-west-2",
                lambda_memory=1024,
                bedrock_model="anthropic.claude-sonnet-4-5-v2:0",
                style=AWSDeploymentStyle.SERVERLESS,
            ),
            "gcp": GCPTargetConfig(
                project="my-gcp-project",
                region="us-central1",
                cloud_run_memory="1Gi",
                model="claude-sonnet-4-5@20250929",
                style=GCPDeploymentStyle.CLOUD_RUN,
            ),
        },
        enhancements=EnhancementsConfig(
            trace=True,
            metrics=True,
            auth=False,
        ),
    )

    print(f"Project: {config.name}")
    print(f"Active target: {config.target}")
    print(f"Number of agents: {len(config.agents)}")
    print(f"Tracing enabled: {config.enhancements.trace}")
    print()

    return config


def example_save_and_load_config():
    """Save a config to YAML and load it back."""
    print("=== Save and Load Config ===\n")

    # Create config
    config = BedsheetConfig(
        name="test-system",
        agents=[
            AgentConfig(
                name="test-agent",
                module="test.agent",
                class_name="TestAgent",
            )
        ],
        target="aws",
        targets={
            "aws": AWSTargetConfig(
                region="eu-west-1",
                lambda_memory=512,
                style=AWSDeploymentStyle.BEDROCK_NATIVE,
            )
        },
    )

    # Save to file
    config_path = Path("test_bedsheet.yaml")
    save_config(config, config_path)
    print(f"Saved config to {config_path}")

    # Load from file
    loaded_config = load_config(config_path)
    print(f"Loaded config: {loaded_config.name}")
    print(f"Active target: {loaded_config.target}")

    # Access target-specific config
    aws_config = loaded_config.get_active_target_config()
    print(f"AWS Region: {aws_config.region}")
    print(f"Lambda Memory: {aws_config.lambda_memory} MB")
    print(f"Deployment Style: {aws_config.style.value}")
    print()

    # Clean up
    config_path.unlink()


def example_load_with_env_vars():
    """Load a config with environment variable interpolation."""
    print("=== Environment Variable Interpolation ===\n")

    # Create a YAML file with env var placeholders
    yaml_content = """
version: "1.0"
name: production-system
agents:
  - name: support-agent
    module: myapp.agents.support
    class_name: SupportAgent
target: gcp
targets:
  gcp:
    project: ${GCP_PROJECT_ID:-default-project}
    region: ${GCP_REGION:-us-central1}
    cloud_run_memory: 512Mi
    model: claude-sonnet-4-5@20250929
    style: cloud_run
"""

    config_path = Path("env_test_bedsheet.yaml")
    config_path.write_text(yaml_content)

    # Load config - env vars will be interpolated
    # If GCP_PROJECT_ID and GCP_REGION are not set, defaults will be used
    config = load_config(config_path)

    print(f"Project: {config.name}")
    gcp_config = config.get_active_target_config()
    print(f"GCP Project: {gcp_config.project}")
    print(f"GCP Region: {gcp_config.region}")
    print()

    # Clean up
    config_path.unlink()


def example_switch_targets():
    """Demonstrate switching between deployment targets."""
    print("=== Switching Between Targets ===\n")

    # Create config with multiple targets
    config = BedsheetConfig(
        name="multi-target-system",
        agents=[
            AgentConfig(
                name="agent",
                module="myapp.agent",
                class_name="Agent",
            )
        ],
        target="local",
        targets={
            "local": LocalTargetConfig(port=8000),
            "aws": AWSTargetConfig(region="us-east-1"),
            "gcp": GCPTargetConfig(project="my-project"),
        },
    )

    # Show different target configs
    for target_name in ["local", "aws", "gcp"]:
        target_config = config.targets[target_name]
        print(f"Target: {target_name}")
        print(f"  Type: {type(target_config).__name__}")

        if isinstance(target_config, LocalTargetConfig):
            print(f"  Port: {target_config.port}")
            print(f"  Hot reload: {target_config.hot_reload}")
        elif isinstance(target_config, AWSTargetConfig):
            print(f"  Region: {target_config.region}")
            print(f"  Lambda memory: {target_config.lambda_memory} MB")
            print(f"  Style: {target_config.style.value}")
        elif isinstance(target_config, GCPTargetConfig):
            print(f"  Project: {target_config.project}")
            print(f"  Region: {target_config.region}")
            print(f"  Style: {target_config.style.value}")
        print()


def main():
    """Run all examples."""
    print("Bedsheet Configuration Examples")
    print("=" * 50)
    print()

    example_create_config_programmatically()
    example_save_and_load_config()
    example_load_with_env_vars()
    example_switch_targets()

    print("All examples completed!")


if __name__ == "__main__":
    main()
