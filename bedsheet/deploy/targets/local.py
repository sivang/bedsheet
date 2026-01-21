"""Local deployment target generator."""
import shutil
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from bedsheet.deploy.config import BedsheetConfig, LocalTargetConfig
from bedsheet.deploy.introspect import AgentMetadata

from .base import DeploymentTarget, GeneratedFile


class LocalTarget(DeploymentTarget):
    """Generate Docker-based local deployment artifacts."""

    def __init__(self):
        self.env = Environment(
            loader=PackageLoader("bedsheet.deploy", "templates/local"),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @property
    def name(self) -> str:
        return "local"

    def generate(
        self,
        config: BedsheetConfig,
        agent_metadata: AgentMetadata,
        output_dir: Path,
    ) -> list[GeneratedFile]:
        """Generate local deployment files."""
        files = []

        # Get local config with defaults
        local_config = config.get_active_target_config()
        if not isinstance(local_config, LocalTargetConfig):
            local_config = LocalTargetConfig()

        # Get agent config from bedsheet.yaml
        agent_config = config.agents[0] if config.agents else None

        context = {
            "config": config,
            "local": local_config,
            "agent": agent_metadata,
            "agent_config": agent_config,  # Has module, class_name, etc.
            "project_name": config.name.replace("-", "_").replace(" ", "_"),
        }

        # Generate each file
        templates = [
            ("Dockerfile.j2", "Dockerfile", False),
            ("docker-compose.yaml.j2", "docker-compose.yaml", False),
            ("Makefile.j2", "Makefile", False),
            ("env.example.j2", ".env.example", False),
            ("app.py.j2", "app.py", False),
            ("pyproject.toml.j2", "pyproject.toml", False),
        ]

        for template_name, output_name, executable in templates:
            template = self.env.get_template(template_name)
            content = template.render(**context)
            files.append(
                GeneratedFile(
                    path=output_dir / output_name,
                    content=content,
                    executable=executable,
                )
            )

        # Copy debug-ui directory (source files for Docker build)
        debug_ui_src = Path(__file__).parent.parent / "templates" / "local" / "debug-ui"
        debug_ui_dst = output_dir / "debug-ui"
        if debug_ui_src.exists():
            if debug_ui_dst.exists():
                shutil.rmtree(debug_ui_dst)
            shutil.copytree(
                debug_ui_src,
                debug_ui_dst,
                ignore=shutil.ignore_patterns("node_modules", "dist", ".git"),
            )

        return files

    def validate(self, config: BedsheetConfig) -> list[str]:
        """Validate local target configuration."""
        errors = []
        if config.targets and config.targets.get("local"):
            local = config.targets["local"]
            if isinstance(local, LocalTargetConfig):
                if local.port and (local.port < 1 or local.port > 65535):
                    errors.append(f"Invalid port: {local.port}")
        return errors
