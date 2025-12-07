"""Main CLI application for Bedsheet.

This module provides the command-line interface for managing Bedsheet
agent deployments. Use `bedsheet --help` to see available commands.
"""
import sys
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from bedsheet.deploy.config import (
    BedsheetConfig,
    AgentConfig,
    LocalTargetConfig,
    AWSTargetConfig,
    GCPTargetConfig,
    load_config,
    save_config,
)

# Initialize Typer app
app = typer.Typer(
    name="bedsheet",
    help="Bedsheet - Cloud-agnostic agent orchestration framework",
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()

# Version from pyproject.toml
__version__ = "0.3.0"


@app.command()
def version():
    """Show Bedsheet version."""
    rprint(f"[bold cyan]Bedsheet[/bold cyan] version [bold]{__version__}[/bold]")


@app.command()
def init(
    project_name: str = typer.Option(
        None,
        "--name",
        "-n",
        help="Name of your agent project"
    ),
    agent_module: str = typer.Option(
        "agents.main",
        "--module",
        "-m",
        help="Python module path to your agent"
    ),
    agent_class: str = typer.Option(
        "Agent",
        "--class",
        "-c",
        help="Agent class name"
    ),
    target: str = typer.Option(
        "local",
        "--target",
        "-t",
        help="Deployment target (local, gcp, aws)"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing bedsheet.yaml"
    ),
):
    """Initialize a new Bedsheet agent project.

    Creates a bedsheet.yaml configuration file in the current directory
    with sensible defaults for your deployment target.

    Example:
        bedsheet init --name my-agent --module agents.customer_support --target gcp
    """
    config_path = Path("bedsheet.yaml")

    # Check if config already exists
    if config_path.exists() and not force:
        rprint("[bold red]Error:[/bold red] bedsheet.yaml already exists!")
        rprint("Use --force to overwrite, or edit the existing file.")
        raise typer.Exit(1)

    # Prompt for project name if not provided
    if not project_name:
        project_name = typer.prompt("Project name")

    # Validate target
    if target not in ["local", "gcp", "aws"]:
        rprint(f"[bold red]Error:[/bold red] Invalid target '{target}'")
        rprint("Valid targets: local, gcp, aws")
        raise typer.Exit(1)

    # Create agent config
    agent_config = AgentConfig(
        name="main",
        module=agent_module,
        class_name=agent_class,
        description="Main agent"
    )

    # Create target configurations
    targets = {}

    if target == "local":
        targets["local"] = LocalTargetConfig(port=8000, hot_reload=True)
    elif target == "gcp":
        gcp_project = typer.prompt("GCP Project ID")
        targets["gcp"] = GCPTargetConfig(
            project=gcp_project,
            region="us-central1",
            cloud_run_memory="512Mi",
            model="claude-sonnet-4-5@20250929",
        )
    elif target == "aws":
        aws_region = typer.prompt("AWS Region", default="us-east-1")
        targets["aws"] = AWSTargetConfig(
            region=aws_region,
            lambda_memory=512,
            bedrock_model="anthropic.claude-sonnet-4-5-v2:0",
        )

    # Create main config
    config = BedsheetConfig(
        version="1.0",
        name=project_name,
        agents=[agent_config],
        target=target,
        targets=targets,
    )

    # Save config to YAML
    save_config(config, config_path)

    # Show success message
    console.print()
    console.print(Panel.fit(
        f"[bold green]✓[/bold green] Created bedsheet.yaml",
        title="[bold]Initialization Complete[/bold]",
        border_style="green",
    ))
    console.print()

    # Show the generated config
    with open(config_path) as f:
        config_content = f.read()

    syntax = Syntax(config_content, "yaml", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title="[bold]bedsheet.yaml[/bold]", border_style="cyan"))

    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print("  1. Edit bedsheet.yaml to customize your deployment")
    console.print("  2. Implement your agent in the specified module")
    console.print(f"  3. Run: [bold cyan]bedsheet deploy --target {target}[/bold cyan]")
    console.print()


@app.command()
def deploy(
    target: Optional[str] = typer.Option(
        None,
        "--target",
        "-t",
        help="Deployment target (local, gcp, aws). Overrides bedsheet.yaml"
    ),
    config_file: Path = typer.Option(
        "bedsheet.yaml",
        "--config",
        "-c",
        help="Path to bedsheet.yaml configuration file"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be deployed without actually deploying"
    ),
):
    """Deploy your Bedsheet agent to the specified target.

    Reads configuration from bedsheet.yaml and deploys your agent
    to the specified platform (local, GCP, or AWS).

    Example:
        bedsheet deploy --target gcp
        bedsheet deploy --config custom.yaml --dry-run
    """
    # Check if config file exists
    if not config_file.exists():
        rprint(f"[bold red]Error:[/bold red] Configuration file not found: {config_file}")
        rprint("Run [bold cyan]bedsheet init[/bold cyan] to create one.")
        raise typer.Exit(1)

    # Load and validate configuration
    try:
        config = load_config(config_file)
    except Exception as e:
        rprint(f"[bold red]Error:[/bold red] Invalid configuration: {e}")
        raise typer.Exit(1)

    # Override target if specified
    if target:
        if target not in ["local", "gcp", "aws"]:
            rprint(f"[bold red]Error:[/bold red] Invalid target '{target}'")
            rprint("Valid targets: local, gcp, aws")
            raise typer.Exit(1)
        if target not in config.targets:
            rprint(f"[bold red]Error:[/bold red] Target '{target}' not configured in bedsheet.yaml")
            rprint(f"Available targets: {', '.join(config.targets.keys())}")
            raise typer.Exit(1)
        config.target = target

    # Get active target config
    target_config = config.get_active_target_config()
    agent_names = ", ".join(agent.name for agent in config.agents)

    # Show deployment info
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]Project:[/bold cyan] {config.name}\n"
        f"[bold cyan]Target:[/bold cyan] {config.target}\n"
        f"[bold cyan]Agents:[/bold cyan] {agent_names}",
        title="[bold]Deployment Configuration[/bold]",
        border_style="cyan",
    ))
    console.print()

    if dry_run:
        console.print("[bold yellow]DRY RUN MODE[/bold yellow] - No changes will be made")
        console.print()

    # Deployment logic (skeleton)
    if config.target == "local":
        _deploy_local(config, target_config, dry_run)
    elif config.target == "gcp":
        _deploy_gcp(config, target_config, dry_run)
    elif config.target == "aws":
        _deploy_aws(config, target_config, dry_run)


def _deploy_local(config: BedsheetConfig, target_config: LocalTargetConfig, dry_run: bool):
    """Deploy agent to local environment."""
    console.print("[bold]Local Deployment[/bold]")
    console.print()

    # Show agent modules
    console.print("[bold]Agents to deploy:[/bold]")
    for agent in config.agents:
        console.print(f"  - {agent.name}: {agent.module}.{agent.class_name}")
    console.print()

    console.print("Steps to deploy locally:")
    console.print("  1. Validate agent modules can be imported")
    console.print("  2. Configure memory backend")
    console.print(f"  3. Start API server on port {target_config.port}")
    if target_config.hot_reload:
        console.print("  4. Enable hot reload for development")
    console.print()

    if dry_run:
        console.print("[dim]Dry run - skipping actual deployment[/dim]")
        return

    # TODO: Implement local deployment
    console.print("[bold yellow]⚠[/bold yellow] Local deployment not yet implemented")
    console.print("Coming in a future release!")


def _deploy_gcp(config: BedsheetConfig, target_config: GCPTargetConfig, dry_run: bool):
    """Deploy agent to Google Cloud Platform."""
    console.print("[bold]GCP Deployment[/bold]")
    console.print()

    # Show agent modules
    console.print("[bold]Agents to deploy:[/bold]")
    for agent in config.agents:
        console.print(f"  - {agent.name}: {agent.module}.{agent.class_name}")
    console.print()

    console.print("Steps to deploy to GCP:")
    console.print(f"  1. Create Cloud Run service in project: {target_config.project}")
    console.print(f"  2. Deploy to region: {target_config.region}")
    console.print(f"  3. Configure memory: {target_config.cloud_run_memory}")
    console.print(f"  4. Use model: {target_config.model}")
    console.print(f"  5. Deployment style: {target_config.style.value}")
    console.print()

    if dry_run:
        console.print("[dim]Dry run - skipping actual deployment[/dim]")
        return

    # TODO: Implement GCP deployment
    console.print("[bold yellow]⚠[/bold yellow] GCP deployment not yet implemented")
    console.print("Coming in a future release!")


def _deploy_aws(config: BedsheetConfig, target_config: AWSTargetConfig, dry_run: bool):
    """Deploy agent to Amazon Web Services."""
    console.print("[bold]AWS Deployment[/bold]")
    console.print()

    # Show agent modules
    console.print("[bold]Agents to deploy:[/bold]")
    for agent in config.agents:
        console.print(f"  - {agent.name}: {agent.module}.{agent.class_name}")
    console.print()

    console.print("Steps to deploy to AWS:")
    console.print(f"  1. Create Lambda function in region: {target_config.region}")
    console.print(f"  2. Configure Lambda memory: {target_config.lambda_memory}MB")
    console.print(f"  3. Use Bedrock model: {target_config.bedrock_model}")
    console.print(f"  4. Deployment style: {target_config.style.value}")
    console.print()

    if dry_run:
        console.print("[dim]Dry run - skipping actual deployment[/dim]")
        return

    # TODO: Implement AWS deployment
    console.print("[bold yellow]⚠[/bold yellow] AWS deployment not yet implemented")
    console.print("Coming in a future release!")


@app.command()
def validate(
    config_file: Path = typer.Option(
        "bedsheet.yaml",
        "--config",
        "-c",
        help="Path to bedsheet.yaml configuration file"
    ),
):
    """Validate your bedsheet.yaml configuration.

    Checks that the configuration file is valid and all required
    fields are present for the specified deployment target.
    """
    if not config_file.exists():
        rprint(f"[bold red]Error:[/bold red] Configuration file not found: {config_file}")
        raise typer.Exit(1)

    try:
        config = load_config(config_file)

        console.print()
        console.print(Panel.fit(
            "[bold green]✓[/bold green] Configuration is valid!",
            border_style="green",
        ))
        console.print()

        # Show parsed config summary
        console.print("[bold]Configuration Summary:[/bold]")
        console.print(f"  [cyan]Version:[/cyan] {config.version}")
        console.print(f"  [cyan]Project:[/cyan] {config.name}")
        console.print(f"  [cyan]Active Target:[/cyan] {config.target}")
        console.print(f"  [cyan]Number of Agents:[/cyan] {len(config.agents)}")
        console.print()

        # Show agents
        console.print("[bold]Agents:[/bold]")
        for agent in config.agents:
            console.print(f"  - [cyan]{agent.name}:[/cyan] {agent.module}.{agent.class_name}")
        console.print()

        # Show target configurations
        console.print("[bold]Configured Targets:[/bold]")
        for target_name in config.targets.keys():
            active = " (active)" if target_name == config.target else ""
            console.print(f"  - {target_name}{active}")
        console.print()

        # Show enhancements if any enabled
        if config.enhancements.trace or config.enhancements.metrics or config.enhancements.auth:
            console.print("[bold]Enabled Enhancements:[/bold]")
            if config.enhancements.trace:
                console.print("  - Tracing/Observability")
            if config.enhancements.metrics:
                console.print("  - Metrics Collection")
            if config.enhancements.auth:
                console.print("  - Authentication")
            console.print()

    except Exception as e:
        rprint(f"[bold red]✗[/bold red] Configuration validation failed:")
        rprint(f"  {e}")
        raise typer.Exit(1)


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
