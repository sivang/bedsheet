"""AWS deployment target generator - generates CDK + Bedrock artifacts."""
from pathlib import Path
from jinja2 import Environment, PackageLoader, select_autoescape

from bedsheet.deploy.config import BedsheetConfig, AWSTargetConfig
from bedsheet.deploy.introspect import AgentMetadata, ToolMetadata
from .base import DeploymentTarget, GeneratedFile


class AWSTarget(DeploymentTarget):
    """Generate AWS CDK + Bedrock deployment artifacts."""

    def __init__(self):
        self.env = Environment(
            loader=PackageLoader("bedsheet.deploy", "templates/aws"),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @property
    def name(self) -> str:
        return "aws"

    def generate(
        self,
        config: BedsheetConfig,
        agent_metadata: AgentMetadata,
        output_dir: Path
    ) -> list[GeneratedFile]:
        """Generate AWS deployment files."""
        files = []

        # Get AWS config with defaults
        aws_config = config.get_active_target_config()
        if not isinstance(aws_config, AWSTargetConfig):
            aws_config = AWSTargetConfig(region="us-east-1")

        # Determine deployment style
        style = aws_config.style.value if aws_config.style else "serverless"

        context = {
            "config": config,
            "aws": aws_config,
            "agent": agent_metadata,
            "project_name": config.name.replace("-", "_").replace(" ", "_"),
            "style": style,
        }

        # Always generate these
        common_templates = [
            ("pyproject.toml.j2", "pyproject.toml", False),
            ("Makefile.j2", "Makefile", False),
            ("env.example.j2", ".env.example", False),
            ("cdk_app.py.j2", "app.py", False),
            ("cdk_json.j2", "cdk.json", False),
        ]

        for template_name, output_name, executable in common_templates:
            template = self.env.get_template(template_name)
            content = template.render(**context)
            files.append(GeneratedFile(
                path=output_dir / output_name,
                content=content,
                executable=executable,
            ))

        # Generate CDK stack
        stack_template = self.env.get_template("cdk_stack.py.j2")
        files.append(GeneratedFile(
            path=output_dir / "stacks" / "agent_stack.py",
            content=stack_template.render(**context),
            executable=False,
        ))

        # Generate stacks/__init__.py
        stacks_init = self.env.get_template("stacks_init.py.j2")
        files.append(GeneratedFile(
            path=output_dir / "stacks" / "__init__.py",
            content=stacks_init.render(**context),
            executable=False,
        ))

        # Generate Lambda handlers for each action group
        if agent_metadata.tools:
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

        # Generate OpenAPI schema
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

        return files

    def validate(self, config: BedsheetConfig) -> list[str]:
        """Validate AWS target configuration."""
        errors = []
        if config.targets and "aws" in config.targets:
            aws = config.targets["aws"]
            if isinstance(aws, AWSTargetConfig):
                # Validate region format - already done in Pydantic validator
                # but we can add additional checks here if needed

                # Validate Lambda memory
                if aws.lambda_memory and (aws.lambda_memory < 128 or aws.lambda_memory > 10240):
                    errors.append(f"Lambda memory must be between 128-10240 MB: {aws.lambda_memory}")

                # Validate style (already validated by Pydantic enum, but double check)
                valid_styles = {"bedrock_native", "serverless", "containers"}
                if aws.style and aws.style.value not in valid_styles:
                    errors.append(f"Invalid AWS style: {aws.style.value}. Must be one of: {valid_styles}")
        return errors
