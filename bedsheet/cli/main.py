"""Main CLI application for Bedsheet.

This module provides the command-line interface for managing Bedsheet
agent deployments. Use `bedsheet --help` to see available commands.
"""
import importlib
import sys
from pathlib import Path
from typing import Literal, Optional, cast

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel

from bedsheet.deploy.config import (
    BedsheetConfig,
    AgentConfig,
    LocalTargetConfig,
    AWSTargetConfig,
    GCPTargetConfig,
    AgentCoreTargetConfig,
    load_config,
    save_config,
)
from bedsheet.deploy.introspect import AgentMetadata, extract_agent_metadata
from bedsheet.deploy.targets import (
    LocalTarget,
    GCPTarget,
    AWSTarget,
    AWSTerraformTarget,
    AgentCoreTarget,
    DeploymentTarget,
)

# Initialize Typer app
app = typer.Typer(
    name="bedsheet",
    help="Bedsheet - Cloud-agnostic agent orchestration framework",
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()

# Version - dynamically read from package metadata
try:
    from importlib.metadata import version as get_version
    __version__ = get_version("bedsheet")
except Exception:
    __version__ = "0.4.3"  # fallback


# Target mapping
# Note: "agentcore" is EXPERIMENTAL - AgentCore is in preview and APIs may change
TARGETS: dict[str, type[DeploymentTarget]] = {
    "local": LocalTarget,
    "gcp": GCPTarget,
    "aws": AWSTarget,
    "aws-terraform": AWSTerraformTarget,
    "agentcore": AgentCoreTarget,  # EXPERIMENTAL
}


def _get_target(target_name: str) -> DeploymentTarget:
    """Get a target instance by name."""
    if target_name not in TARGETS:
        raise ValueError(f"Unknown target: {target_name}")
    return TARGETS[target_name]()


TargetType = Literal["local", "gcp", "aws"]


def _get_introspection_target(target_name: str) -> TargetType:
    """Map deployment target names to introspection targets.

    The introspection system only supports local/gcp/aws for code transformation.
    AWS-based targets (aws-terraform, agentcore) map to "aws".
    """
    if target_name in ("aws", "aws-terraform", "agentcore"):
        return "aws"
    elif target_name == "gcp":
        return "gcp"
    return "local"


def _load_and_introspect_agent(
    agent_config: AgentConfig,
    console: Console,
    target: TargetType = "local",
) -> tuple[AgentMetadata | None, str | None]:
    """Dynamically load an agent module and introspect it.

    Args:
        agent_config: The agent configuration from bedsheet.yaml
        console: Rich console for output
        target: Deployment target for code transformation ("local", "gcp", "aws")

    Returns:
        Tuple of (AgentMetadata, None) on success, or (None, error_message) on failure.
    """
    module_path = agent_config.module
    class_name = agent_config.class_name

    # Add current directory to path for local imports
    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    try:
        # Import the module
        console.print(f"  [dim]Importing {module_path}...[/dim]")
        module = importlib.import_module(module_path)

        # Get the agent class or instance
        if not hasattr(module, class_name):
            # Try to find an agent instance (common pattern: module-level agent)
            # Look for common names like 'agent', 'advisor', or the lowercase class name
            agent_instance = None
            for attr_name in [class_name.lower(), 'agent', 'advisor', 'root_agent']:
                if hasattr(module, attr_name):
                    attr = getattr(module, attr_name)
                    # Check if it's an Agent instance
                    from bedsheet.agent import Agent
                    if isinstance(attr, Agent):
                        agent_instance = attr
                        console.print(f"  [dim]Found agent instance: {attr_name}[/dim]")
                        break

            if agent_instance is None:
                return None, f"Class '{class_name}' not found in module '{module_path}'"

            # Introspect the existing instance
            metadata = extract_agent_metadata(agent_instance, target=target)
            return metadata, None

        agent_class = getattr(module, class_name)

        # Check if it's already an instance (module-level agent)
        from bedsheet.agent import Agent
        if isinstance(agent_class, Agent):
            console.print(f"  [dim]Found agent instance: {class_name}[/dim]")
            metadata = extract_agent_metadata(agent_class, target=target)
            return metadata, None

        # It's a class - we need to instantiate it
        # Check if it's a callable (class or factory function)
        if not callable(agent_class):
            return None, f"'{class_name}' in module '{module_path}' is not callable"

        # Try to instantiate with a mock LLM client
        console.print(f"  [dim]Instantiating {class_name}...[/dim]")

        # Import MockLLMClient for introspection
        from bedsheet.testing import MockLLMClient, MockResponse

        # Create a mock client that returns empty responses
        mock_client = MockLLMClient([MockResponse(text="introspection")])

        # Try different instantiation strategies
        agent_instance = None

        # Strategy 1: Check if it's a factory function (returns an agent)
        import inspect
        sig = inspect.signature(agent_class)
        params = sig.parameters

        if len(params) == 0:
            # No-arg factory function
            try:
                result = agent_class()
                if isinstance(result, Agent):
                    agent_instance = result
            except Exception:
                pass

        # Strategy 2: Try with model_client parameter
        if agent_instance is None and 'model_client' in params:
            try:
                agent_instance = agent_class(model_client=mock_client)
            except Exception:
                pass

        # Strategy 3: Try with common parameter patterns
        if agent_instance is None:
            common_patterns = [
                {'model_client': mock_client},
                {'llm_client': mock_client},
                {'client': mock_client},
            ]
            for kwargs in common_patterns:
                try:
                    agent_instance = agent_class(**kwargs)
                    if isinstance(agent_instance, Agent):
                        break
                except Exception:
                    continue

        if agent_instance is None or not isinstance(agent_instance, Agent):
            return None, (
                f"Could not instantiate '{class_name}'. "
                "Ensure your agent class accepts a 'model_client' parameter, "
                "or export an agent instance at module level."
            )

        # Introspect the agent
        console.print("  [dim]Introspecting agent...[/dim]")
        metadata = extract_agent_metadata(agent_instance, target=target)
        return metadata, None

    except ImportError as e:
        return None, f"Failed to import module '{module_path}': {e}"
    except Exception as e:
        return None, f"Error introspecting agent: {e}"


@app.command()
def version():
    """Show Bedsheet version."""
    rprint(f"[bold cyan]Bedsheet[/bold cyan] version [bold]{__version__}[/bold]")


@app.command()
def demo():
    """Run the multi-agent investment advisor demo.

    Shows parallel delegation, event streaming, and supervisor synthesis.
    Requires ANTHROPIC_API_KEY environment variable.

    Example:
        bedsheet demo
    """
    from bedsheet.__main__ import main as demo_main
    demo_main()


@app.command()
def init(
    project_name: str = typer.Argument(
        None,
        help="Name of your agent project (creates a directory)"
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
        help="Overwrite existing project"
    ),
):
    """Initialize a new Bedsheet agent project.

    Creates a new project directory with a complete scaffold including
    bedsheet.yaml, sample agent code, and requirements.

    Example:
        bedsheet init my-agent
        bedsheet init my-agent --target gcp
    """
    # Prompt for project name if not provided
    if not project_name:
        project_name = typer.prompt("Project name")

    # Validate project name (no spaces, valid directory name)
    if " " in project_name or "/" in project_name:
        rprint("[bold red]Error:[/bold red] Project name cannot contain spaces or slashes")
        raise typer.Exit(1)

    # Validate target
    if target not in ["local", "gcp", "aws", "agentcore"]:
        rprint(f"[bold red]Error:[/bold red] Invalid target '{target}'")
        rprint("Valid targets: local, gcp, aws, agentcore")
        raise typer.Exit(1)

    # Create project directory
    project_dir = Path(project_name)
    if project_dir.exists() and not force:
        rprint(f"[bold red]Error:[/bold red] Directory '{project_name}' already exists!")
        rprint("Use --force to overwrite.")
        raise typer.Exit(1)

    # Create directory structure
    project_dir.mkdir(exist_ok=True)
    agents_dir = project_dir / "agents"
    agents_dir.mkdir(exist_ok=True)

    # Create agents/__init__.py
    (agents_dir / "__init__.py").write_text("")

    # Create agents/assistant.py with sample agent
    assistant_code = '''"""Sample assistant agent."""
from bedsheet import Agent, ActionGroup
from bedsheet.llm import AnthropicClient


# Create tools for the assistant
tools = ActionGroup(
    name="AssistantTools",
    description="Tools for the assistant agent"
)


@tools.action(
    name="greet",
    description="Greet the user by name"
)
async def greet(name: str) -> str:
    """Greet a user."""
    return f"Hello, {name}! How can I help you today?"


@tools.action(
    name="get_time",
    description="Get the current time"
)
async def get_time() -> str:
    """Get current time."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_assistant() -> Agent:
    """Create and configure the assistant agent."""
    agent = Agent(
        name="Assistant",
        instruction="""You are a helpful assistant.

Use your tools to help users with their requests.
Be friendly and concise in your responses.""",
        model_client=AnthropicClient(),
    )
    agent.add_action_group(tools)
    return agent


# Export for bedsheet introspection
assistant = create_assistant()
'''
    (agents_dir / "assistant.py").write_text(assistant_code)

    # Create pyproject.toml (no build-system - this is not a distributable package)
    pyproject = f'''[project]
name = "{project_name}"
version = "0.1.0"
description = "A Bedsheet agent project"
requires-python = ">=3.11"
dependencies = [
    "bedsheet>=0.4.0",
    "anthropic>=0.18.0",
]
'''
    (project_dir / "pyproject.toml").write_text(pyproject)

    # Create target configurations
    targets: dict[str, LocalTargetConfig | AWSTargetConfig | GCPTargetConfig | AgentCoreTargetConfig] = {}

    if target == "local":
        targets["local"] = LocalTargetConfig(port=8000, hot_reload=True)
    elif target == "gcp":
        gcp_project = typer.prompt("GCP Project ID")
        gcp_region = typer.prompt("GCP Region", default="europe-west1")
        targets["gcp"] = GCPTargetConfig(
            project=gcp_project,
            region=gcp_region,
            cloud_run_memory="512Mi",
            model="gemini-3-flash-preview",
        )
    elif target == "aws":
        aws_region = typer.prompt("AWS Region", default="eu-central-1")
        targets["aws"] = AWSTargetConfig(
            region=aws_region,
            lambda_memory=512,
            bedrock_model="anthropic.claude-sonnet-4-5-v2:0",
        )
    elif target == "agentcore":
        aws_region = typer.prompt("AWS Region", default="us-east-1")
        targets["agentcore"] = AgentCoreTargetConfig(
            region=aws_region,
            runtime_memory=1024,
            lambda_memory=512,
            bedrock_model="anthropic.claude-sonnet-4-5-v2:0",
        )

    # Create agent config pointing to the sample assistant
    agent_config = AgentConfig(
        name="assistant",
        module="agents.assistant",
        class_name="Assistant",
        description="Sample assistant agent"
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
    config_path = project_dir / "bedsheet.yaml"
    save_config(config, config_path)

    # Show success message with tree structure
    console.print()
    console.print(f"[bold green]Created project: {project_name}[/bold green]")
    console.print("[dim]├── bedsheet.yaml      # Configuration[/dim]")
    console.print("[dim]├── pyproject.toml     # Dependencies[/dim]")
    console.print("[dim]└── agents/            # Your agent code[/dim]")
    console.print("[dim]    └── assistant.py   # Example agent[/dim]")
    console.print()

    console.print("[bold]Next steps:[/bold]")
    console.print(f"  1. [cyan]cd {project_name}[/cyan]")
    console.print("  2. [cyan]uv sync[/cyan]  (or pip install -e .)")
    console.print("  3. Edit agents/assistant.py to customize your agent")
    console.print(f"  4. [cyan]bedsheet generate --target {target}[/cyan]")
    console.print()


@app.command()
def deploy(
    config_file: Path = typer.Argument(
        "bedsheet.yaml",
        help="Path to bedsheet.yaml configuration file"
    ),
    target: Optional[str] = typer.Option(
        None,
        "--target",
        "-t",
        help="Deployment target (local, gcp, aws). Overrides bedsheet.yaml"
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
        bedsheet deploy path/to/bedsheet.yaml --target gcp
        bedsheet deploy --dry-run
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
        _deploy_local(config, cast(LocalTargetConfig, target_config), dry_run)
    elif config.target == "gcp":
        _deploy_gcp(config, cast(GCPTargetConfig, target_config), dry_run)
    elif config.target == "aws":
        _deploy_aws(config, cast(AWSTargetConfig, target_config), dry_run)


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
    config_file: Path = typer.Argument(
        "bedsheet.yaml",
        help="Path to bedsheet.yaml configuration file"
    ),
):
    """Validate your bedsheet.yaml configuration.

    Checks that the configuration file is valid and all required
    fields are present for the specified deployment target.

    Example:
        bedsheet validate
        bedsheet validate path/to/bedsheet.yaml
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
        rprint("[bold red]✗[/bold red] Configuration validation failed:")
        rprint(f"  {e}")
        raise typer.Exit(1)


@app.command()
def generate(
    config_file: Path = typer.Argument(
        "bedsheet.yaml",
        help="Path to bedsheet.yaml configuration file"
    ),
    target: Optional[str] = typer.Option(
        None,
        "--target",
        "-t",
        help="Deployment target (local, gcp, aws). Overrides bedsheet.yaml"
    ),
    output_dir: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for generated files. Defaults to deploy/<target>/"
    ),
    agent_name: Optional[str] = typer.Option(
        None,
        "--agent",
        "-a",
        help="Name of a specific agent to generate for (from bedsheet.yaml)"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be generated without writing files"
    ),
):
    """Generate deployment artifacts for the specified target.

    This command generates all the files needed to deploy your Bedsheet
    agent to a specific platform (local Docker, GCP, or AWS).

    Example:
        bedsheet generate bedsheet.yaml --target local
        bedsheet generate path/to/bedsheet.yaml --target gcp --output my-deploy/
        bedsheet generate --target aws --dry-run
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

    # Determine target
    target_name = target or config.target
    if target_name not in TARGETS:
        rprint(f"[bold red]Error:[/bold red] Invalid target '{target_name}'")
        rprint(f"Valid targets: {', '.join(TARGETS.keys())}")
        raise typer.Exit(1)

    # Set output directory
    if output_dir is None:
        output_dir = Path("deploy") / target_name

    # Get target generator
    target_generator = _get_target(target_name)

    # Warn about experimental targets
    if target_name == "agentcore":
        rprint(Panel(
            "[bold yellow]⚠️  EXPERIMENTAL TARGET[/bold yellow]\n\n"
            "The AgentCore deployment target is experimental.\n"
            "Amazon Bedrock AgentCore is in preview and APIs may change without notice.\n"
            "Use in production at your own risk.\n\n"
            "Please report bugs at: [link=https://github.com/sivang/bedsheet/issues]github.com/sivang/bedsheet/issues[/link]",
            title="Warning",
            border_style="yellow",
        ))

    # Validate configuration for this target
    validation_errors = target_generator.validate(config)
    if validation_errors:
        rprint("[bold red]Error:[/bold red] Configuration validation failed:")
        for error in validation_errors:
            rprint(f"  - {error}")
        raise typer.Exit(1)

    # Get agent configuration
    if not config.agents:
        rprint("[bold red]Error:[/bold red] No agents defined in bedsheet.yaml")
        raise typer.Exit(1)

    agent_config = config.agents[0]
    if agent_name:
        matching = [a for a in config.agents if a.name == agent_name]
        if not matching:
            rprint(f"[bold red]Error:[/bold red] Agent '{agent_name}' not found in config")
            rprint(f"Available agents: {', '.join(a.name for a in config.agents)}")
            raise typer.Exit(1)
        agent_config = matching[0]

    # Try to introspect the actual agent
    console.print("[bold]Introspecting agent...[/bold]")
    introspected_metadata, introspection_error = _load_and_introspect_agent(
        agent_config, console, target=_get_introspection_target(target_name)
    )

    if introspection_error or introspected_metadata is None:
        # Introspection failed - fall back to config-based metadata with warning
        console.print(f"[bold yellow]Warning:[/bold yellow] {introspection_error}")
        console.print("[dim]Falling back to config-based metadata (tools will be empty)[/dim]")
        console.print()

        agent_metadata = AgentMetadata(
            name=agent_config.name,
            instruction=agent_config.description or f"Agent: {agent_config.name}",
            tools=[],
            collaborators=[],
            is_supervisor=False,
        )
    else:
        agent_metadata = introspected_metadata
        # Show what we found
        tool_count = len(agent_metadata.tools)
        collab_count = len(agent_metadata.collaborators)
        agent_type = "Supervisor" if agent_metadata.is_supervisor else "Agent"

        console.print(f"  [green]✓[/green] Found {agent_type}: [cyan]{agent_metadata.name}[/cyan]")
        console.print(f"  [green]✓[/green] Tools: [cyan]{tool_count}[/cyan]")
        if agent_metadata.is_supervisor:
            console.print(f"  [green]✓[/green] Collaborators: [cyan]{collab_count}[/cyan]")
            for collab in agent_metadata.collaborators:
                console.print(f"      - {collab.name} ({len(collab.tools)} tools)")
        console.print()

    # Show generation info
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]Project:[/bold cyan] {config.name}\n"
        f"[bold cyan]Target:[/bold cyan] {target_name}\n"
        f"[bold cyan]Output:[/bold cyan] {output_dir}",
        title="[bold]Code Generation[/bold]",
        border_style="cyan",
    ))
    console.print()

    # Generate files
    try:
        generated_files = target_generator.generate(config, agent_metadata, output_dir)
    except Exception as e:
        rprint(f"[bold red]Error:[/bold red] Generation failed: {e}")
        raise typer.Exit(1)

    if dry_run:
        console.print("[bold yellow]DRY RUN MODE[/bold yellow] - Files that would be generated:")
        console.print()
        for gf in generated_files:
            console.print(f"  [cyan]{gf.path}[/cyan]")
        console.print()
        console.print(f"Total: {len(generated_files)} files")
        return

    # Write files to disk
    files_written = 0
    for gf in generated_files:
        # Create parent directories
        gf.path.parent.mkdir(parents=True, exist_ok=True)
        # Write content
        gf.path.write_text(gf.content)
        # Set executable if needed
        if gf.executable:
            gf.path.chmod(gf.path.stat().st_mode | 0o111)
        files_written += 1
        console.print(f"  [green]✓[/green] {gf.path}")

    console.print()
    console.print(Panel.fit(
        f"[bold green]✓[/bold green] Generated {files_written} files in {output_dir}/",
        border_style="green",
    ))
    console.print()

    # Show next steps based on target
    console.print("[bold]Next steps:[/bold]")
    if target_name == "local":
        console.print(f"  cd {output_dir}")
        console.print("  docker-compose up")
    elif target_name == "gcp":
        console.print(f"  cd {output_dir}")
        console.print("  make init     # One-time setup (auth, APIs, infrastructure)")
        console.print("  make deploy   # Deploy to Cloud Run")
        console.print("")
        console.print("  [dim]Or test locally first: make dev[/dim]")
    elif target_name in ("aws", "aws-terraform"):
        console.print(f"  cd {output_dir}")
        console.print("  make setup && make deploy")
    elif target_name == "agentcore":
        console.print(f"  cd {output_dir}")
        console.print("  cp .env.example .env")
        console.print("  cp terraform.tfvars.example terraform.tfvars")
        console.print("  make init            # Initialize Terraform")
        console.print("  make dev             # Local development server")
        console.print("  make deploy          # Deploy to AgentCore")
    console.print()


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
