"""Amazon Bedrock AgentCore deployment target generator.

Generates Terraform + AgentCore Runtime artifacts for deploying Bedsheet agents
to Amazon Bedrock AgentCore with Gateway integration for tools.

.. warning:: EXPERIMENTAL
   This deployment target is experimental and subject to change.
   The AgentCore service is in preview and APIs may change without notice.
   Use in production at your own risk.

   Report bugs at: https://github.com/sivang/bedsheet/issues
"""
from dataclasses import replace
from pathlib import Path
from jinja2 import Environment, PackageLoader, select_autoescape

from bedsheet.deploy.config import BedsheetConfig, AgentCoreTargetConfig
from bedsheet.deploy.introspect import AgentMetadata
from .base import DeploymentTarget, GeneratedFile


class AgentCoreTarget(DeploymentTarget):
    """Generate AgentCore Terraform + Runtime deployment artifacts."""

    def __init__(self):
        self.env = Environment(
            loader=PackageLoader("bedsheet.deploy", "templates/agentcore"),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @property
    def name(self) -> str:
        return "agentcore"

    def generate(
        self,
        config: BedsheetConfig,
        agent_metadata: AgentMetadata,
        output_dir: Path
    ) -> list[GeneratedFile]:
        """Generate AgentCore deployment files."""
        files = []

        # Get AgentCore config with defaults
        agentcore_config = config.get_active_target_config()
        if not isinstance(agentcore_config, AgentCoreTargetConfig):
            agentcore_config = AgentCoreTargetConfig(region="us-east-1")

        # For Supervisors with collaborators, filter out the 'delegate' tool
        # AgentCore uses native agent-to-agent protocol for multi-agent collaboration
        filtered_agent = agent_metadata
        if agent_metadata.is_supervisor and agent_metadata.collaborators:
            filtered_tools = [
                tool for tool in agent_metadata.tools
                if tool.name != "delegate"
            ]
            filtered_agent = replace(agent_metadata, tools=filtered_tools)

        context = {
            "config": config,
            "agentcore": agentcore_config,
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

        # Runtime container files
        runtime_templates = [
            ("runtime/Dockerfile.j2", "runtime/Dockerfile", False),
            ("runtime/app.py.j2", "runtime/app.py", False),
            ("runtime/requirements.txt.j2", "runtime/requirements.txt", False),
        ]

        for template_name, output_name, executable in runtime_templates:
            template = self.env.get_template(template_name)
            content = template.render(**context)
            files.append(GeneratedFile(
                path=output_dir / output_name,
                content=content,
                executable=executable,
            ))

        # Generate Lambda handlers for action groups (if tools exist after filtering)
        if filtered_agent.tools:
            handler_template = self.env.get_template("lambda/handler.py.j2")
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
            lambda_req = self.env.get_template("lambda/requirements.txt.j2")
            files.append(GeneratedFile(
                path=output_dir / "lambda" / "requirements.txt",
                content=lambda_req.render(**context),
                executable=False,
            ))

        # Generate OpenAPI schema for Gateway tools
        openapi_template = self.env.get_template("schemas/openapi.yaml.j2")
        files.append(GeneratedFile(
            path=output_dir / "schemas" / "openapi.yaml",
            content=openapi_template.render(**context),
            executable=False,
        ))

        # Generate GitHub Actions CI/CD workflows
        github_templates = [
            ("github/workflows/ci.yaml.j2", ".github/workflows/ci.yaml"),
            ("github/workflows/deploy.yaml.j2", ".github/workflows/deploy.yaml"),
        ]
        for template_name, output_name in github_templates:
            template = self.env.get_template(template_name)
            files.append(GeneratedFile(
                path=output_dir / output_name,
                content=template.render(**context),
                executable=False,
            ))

        return files

    def validate(self, config: BedsheetConfig) -> list[str]:
        """Validate AgentCore target configuration."""
        errors = []
        if config.targets and "agentcore" in config.targets:
            agentcore = config.targets["agentcore"]
            if isinstance(agentcore, AgentCoreTargetConfig):
                # Validate Lambda memory
                if agentcore.lambda_memory and (agentcore.lambda_memory < 128 or agentcore.lambda_memory > 10240):
                    errors.append(f"Lambda memory must be between 128-10240 MB: {agentcore.lambda_memory}")
                # Validate Runtime memory
                if agentcore.runtime_memory and (agentcore.runtime_memory < 512 or agentcore.runtime_memory > 8192):
                    errors.append(f"Runtime memory must be between 512-8192 MB: {agentcore.runtime_memory}")
                # Validate Runtime vCPU
                if agentcore.runtime_vcpu and (agentcore.runtime_vcpu < 0.25 or agentcore.runtime_vcpu > 4):
                    errors.append(f"Runtime vCPU must be between 0.25-4: {agentcore.runtime_vcpu}")
        return errors
