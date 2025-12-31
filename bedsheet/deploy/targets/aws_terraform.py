"""AWS Terraform deployment target generator - generates Terraform + Bedrock artifacts."""
from dataclasses import replace
from pathlib import Path
from jinja2 import Environment, PackageLoader, select_autoescape

from bedsheet.deploy.config import BedsheetConfig, AWSTargetConfig
from bedsheet.deploy.introspect import AgentMetadata
from .base import DeploymentTarget, GeneratedFile


class AWSTerraformTarget(DeploymentTarget):
    """Generate AWS Terraform + Bedrock deployment artifacts."""

    def __init__(self):
        self.env = Environment(
            loader=PackageLoader("bedsheet.deploy", "templates/aws-terraform"),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @property
    def name(self) -> str:
        return "aws-terraform"

    def generate(
        self,
        config: BedsheetConfig,
        agent_metadata: AgentMetadata,
        output_dir: Path
    ) -> list[GeneratedFile]:
        """Generate AWS Terraform deployment files."""
        files = []

        # Get AWS config with defaults
        aws_config = config.get_active_target_config()
        if not isinstance(aws_config, AWSTargetConfig):
            aws_config = AWSTargetConfig(region="eu-central-1")

        # For Supervisors with collaborators, optionally filter out the 'delegate' tool
        # When enable_delegate_for_supervisors is True, keep delegate for better trace visibility
        # When False, use Bedrock's native delegation via aws_bedrockagent_agent_collaborator
        filtered_agent = agent_metadata
        if agent_metadata.is_supervisor and agent_metadata.collaborators:
            if not aws_config.enable_delegate_for_supervisors:
                # Filter out delegate - use native collaboration only
                filtered_tools = [
                    tool for tool in agent_metadata.tools
                    if tool.name != "delegate"
                ]
                filtered_agent = replace(agent_metadata, tools=filtered_tools)
            # else: keep delegate action for improved trace visibility

        context = {
            "config": config,
            "aws": aws_config,
            "agent": filtered_agent,
            "project_name": config.name.replace("-", "_").replace(" ", "_"),
        }

        # Core Terraform files
        terraform_templates = [
            ("main.tf.j2", "main.tf", False),
            ("variables.tf.j2", "variables.tf", False),
            ("outputs.tf.j2", "outputs.tf", False),
            ("terraform.tfvars.example.j2", "terraform.tfvars.example", False),
        ]

        for template_name, output_name, executable in terraform_templates:
            template = self.env.get_template(template_name)
            content = template.render(**context)
            files.append(GeneratedFile(
                path=output_dir / output_name,
                content=content,
                executable=executable,
            ))

        # Common files
        common_templates = [
            ("pyproject.toml.j2", "pyproject.toml", False),
            ("Makefile.j2", "Makefile", False),
            ("env.example.j2", ".env.example", False),
        ]

        for template_name, output_name, executable in common_templates:
            template = self.env.get_template(template_name)
            content = template.render(**context)
            files.append(GeneratedFile(
                path=output_dir / output_name,
                content=content,
                executable=executable,
            ))

        # Generate Lambda handlers for action groups (if tools exist after filtering)
        if filtered_agent.tools:
            handler_template = self.env.get_template("lambda_handler.py.j2")
            files.append(GeneratedFile(
                path=output_dir / "lambda" / "handler.py",
                content=handler_template.render(**context),
                executable=False,
            ))

            # Lambda __init__.py
            files.append(GeneratedFile(
                path=output_dir / "lambda" / "__init__.py",
                content="",
                executable=False,
            ))

            # Lambda requirements
            lambda_req = self.env.get_template("lambda_requirements.txt.j2")
            files.append(GeneratedFile(
                path=output_dir / "lambda" / "requirements.txt",
                content=lambda_req.render(**context),
                executable=False,
            ))

        # Generate OpenAPI schema (uses filtered_agent from context)
        openapi_template = self.env.get_template("openapi.yaml.j2")
        files.append(GeneratedFile(
            path=output_dir / "schemas" / "openapi.yaml",
            content=openapi_template.render(**context),
            executable=False,
        ))

        # Generate GitHub Actions CI/CD workflows
        github_templates = [
            ("github_workflows_ci.yaml.j2", ".github/workflows/ci.yaml"),
            ("github_workflows_deploy.yaml.j2", ".github/workflows/deploy.yaml"),
        ]
        for template_name, output_name in github_templates:
            template = self.env.get_template(template_name)
            files.append(GeneratedFile(
                path=output_dir / output_name,
                content=template.render(**context),
                executable=False,
            ))

        # Generate Debug UI server
        debug_ui_template = self.env.get_template("debug-ui/server.py.j2")
        files.append(GeneratedFile(
            path=output_dir / "debug-ui" / "server.py",
            content=debug_ui_template.render(**context),
            executable=False,
        ))

        return files

    def validate(self, config: BedsheetConfig) -> list[str]:
        """Validate AWS Terraform target configuration."""
        errors = []
        if config.targets and "aws-terraform" in config.targets:
            aws = config.targets["aws-terraform"]
            if isinstance(aws, AWSTargetConfig):
                # Validate Lambda memory
                if aws.lambda_memory and (aws.lambda_memory < 128 or aws.lambda_memory > 10240):
                    errors.append(f"Lambda memory must be between 128-10240 MB: {aws.lambda_memory}")
        return errors
