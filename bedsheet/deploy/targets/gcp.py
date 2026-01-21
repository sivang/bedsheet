"""GCP deployment target generator - generates ADK-compatible code."""
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from bedsheet.deploy.config import BedsheetConfig, GCPTargetConfig
from bedsheet.deploy.introspect import AgentMetadata

from .base import DeploymentTarget, GeneratedFile


class GCPTarget(DeploymentTarget):
    """Generate Google ADK-compatible deployment artifacts."""

    def __init__(self):
        self.env = Environment(
            loader=PackageLoader("bedsheet.deploy", "templates/gcp"),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @property
    def name(self) -> str:
        return "gcp"

    def generate(
        self,
        config: BedsheetConfig,
        agent_metadata: AgentMetadata,
        output_dir: Path,
    ) -> list[GeneratedFile]:
        """Generate GCP deployment files."""
        files = []

        # Get GCP config with defaults
        gcp_config = config.get_active_target_config()
        if not isinstance(gcp_config, GCPTargetConfig):
            gcp_config = GCPTargetConfig(project="my-project")

        # Determine orchestration type
        orchestration = self._determine_orchestration(agent_metadata)

        context = {
            "config": config,
            "gcp": gcp_config,
            "agent": agent_metadata,
            "project_name": config.name.replace("-", "_").replace(" ", "_"),
            "orchestration": orchestration,  # "single", "sequential", or "parallel"
        }

        # Generate each file
        templates = [
            # ADK agent code
            ("agent.py.j2", "agent/agent.py", False),
            ("__init__.py.j2", "agent/__init__.py", False),
            # Docker/Cloud Build
            ("pyproject.toml.j2", "pyproject.toml", False),
            ("Dockerfile.j2", "Dockerfile", False),
            ("cloudbuild.yaml.j2", "cloudbuild.yaml", False),
            # Terraform IaC
            ("main.tf.j2", "terraform/main.tf", False),
            ("terraform/backend.tf.j2", "terraform/backend.tf", False),
            ("variables.tf.j2", "terraform/variables.tf", False),
            ("outputs.tf.j2", "terraform/outputs.tf", False),
            ("terraform.tfvars.example.j2", "terraform/terraform.tfvars.example", False),
            # GitHub Actions CI/CD
            ("github_workflows_ci.yaml.j2", ".github/workflows/ci.yaml", False),
            ("github_workflows_deploy.yaml.j2", ".github/workflows/deploy.yaml", False),
            # Development
            ("Makefile.j2", "Makefile", False),
            ("env.example.j2", ".env.example", False),
            # Documentation
            ("DEPLOYMENT_GUIDE.md.j2", "DEPLOYMENT_GUIDE.md", False),
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

        return files

    def _determine_orchestration(self, agent_metadata: AgentMetadata) -> str:
        """Determine ADK orchestration type from agent metadata.

        Maps Bedsheet patterns to ADK orchestration:
        - Single agent → "single" (LlmAgent)
        - Supervisor with collaborators → "parallel" (ParallelAgent)
          The supervisor pattern typically delegates in parallel
        """
        if not agent_metadata.collaborators:
            return "single"
        # Use parallel for supervisor pattern (parallel delegation)
        return "parallel"

    def validate(self, config: BedsheetConfig) -> list[str]:
        """Validate GCP target configuration."""
        errors = []
        if config.targets and "gcp" in config.targets:
            gcp = config.targets["gcp"]
            if isinstance(gcp, GCPTargetConfig):
                # Validate project ID format
                if gcp.project:
                    # GCP project IDs must be 6-30 chars, lowercase letters, digits, hyphens
                    # Must start with letter, cannot end with hyphen
                    if not gcp.project:
                        errors.append("GCP project ID cannot be empty")
                    elif len(gcp.project) < 6 or len(gcp.project) > 30:
                        errors.append(
                            f"Invalid GCP project ID length: {gcp.project} (must be 6-30 characters)"
                        )
                    elif not gcp.project[0].isalpha():
                        errors.append(
                            f"Invalid GCP project ID: {gcp.project} (must start with a letter)"
                        )
                    elif gcp.project.endswith("-"):
                        errors.append(
                            f"Invalid GCP project ID: {gcp.project} (cannot end with hyphen)"
                        )
                    elif not all(c.islower() or c.isdigit() or c == "-" for c in gcp.project):
                        errors.append(
                            f"Invalid GCP project ID: {gcp.project} "
                            "(must contain only lowercase letters, digits, and hyphens)"
                        )
                # Validate region is not empty
                if gcp.region and not gcp.region.strip():
                    errors.append("GCP region cannot be empty if specified")
        return errors
