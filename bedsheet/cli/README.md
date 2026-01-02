# Bedsheet CLI

Command-line interface for managing Bedsheet agent deployments.

## Installation

```bash
uv pip install bedsheet[deploy]
```

Or install from source:

```bash
uv pip install -e .
```

## Commands

### version

Show the current version of Bedsheet:

```bash
bedsheet version
```

### init

Initialize a new Bedsheet agent project by creating a `bedsheet.yaml` configuration file:

```bash
# Local development
bedsheet init --name my-agent --target local

# GCP deployment (will prompt for project ID)
bedsheet init --name my-agent --target gcp

# AWS deployment (will prompt for region)
bedsheet init --name my-agent --target aws
```

Options:
- `--name, -n`: Project name (required, or will prompt)
- `--module, -m`: Python module path (default: `agents.main`)
- `--class, -c`: Agent class name (default: `Agent`)
- `--target, -t`: Deployment target - `local`, `gcp`, or `aws` (default: `local`)
- `--force, -f`: Overwrite existing bedsheet.yaml

### validate

Validate your `bedsheet.yaml` configuration file:

```bash
bedsheet validate

# Or specify a custom config file
bedsheet validate --config custom.yaml
```

This will check:
- YAML syntax is valid
- All required fields are present
- Target configurations are correct
- Agent configurations are valid

### deploy

Deploy your agent to the specified target:

```bash
# Deploy using the target specified in bedsheet.yaml
bedsheet deploy

# Override the target
bedsheet deploy --target gcp

# Dry run (show what would be deployed without deploying)
bedsheet deploy --dry-run

# Use a custom config file
bedsheet deploy --config custom.yaml
```

Options:
- `--target, -t`: Override deployment target from config
- `--config, -c`: Path to config file (default: `bedsheet.yaml`)
- `--dry-run`: Show deployment plan without executing

## Example Workflow

```bash
# 1. Initialize a new project
bedsheet init --name customer-support --target local

# 2. Edit the generated bedsheet.yaml to customize
vim bedsheet.yaml

# 3. Validate your configuration
bedsheet validate

# 4. Deploy (dry run first)
bedsheet deploy --dry-run

# 5. Deploy for real
bedsheet deploy
```

## Configuration File

The `bedsheet.yaml` file uses the following structure:

```yaml
version: '1.0'
name: my-agent
agents:
  - name: main
    module: agents.main
    class_name: Agent
    description: Main agent
target: local
targets:
  local:
    port: 8000
    hot_reload: true
enhancements:
  trace: false
  metrics: false
  auth: false
```

### Multi-target Configuration

You can configure multiple targets in the same file:

```yaml
version: '1.0'
name: my-agent
agents:
  - name: main
    module: agents.main
    class_name: Agent
target: local  # Active target

targets:
  local:
    port: 8000
    hot_reload: true

  gcp:
    project: my-gcp-project
    region: us-central1
    cloud_run_memory: 512Mi
    model: claude-sonnet-4-5@20250929
    style: cloud_run

  aws:
    region: us-east-1
    lambda_memory: 512
    bedrock_model: anthropic.claude-sonnet-4-5-v2:0
    style: serverless
```

Then deploy to different targets:

```bash
bedsheet deploy --target local   # Local dev
bedsheet deploy --target gcp      # GCP Cloud Run
bedsheet deploy --target aws      # AWS Lambda
```

### Environment Variables

The config supports environment variable interpolation:

```yaml
targets:
  gcp:
    project: ${GCP_PROJECT_ID}
    region: ${GCP_REGION:-us-central1}  # With default
```

## Development Status

Currently implemented:
- Configuration validation
- Multi-target configuration
- Environment variable interpolation
- Rich CLI output with colors and formatting

Coming soon:
- Actual deployment implementation (local, GCP, AWS)
- Agent introspection and metadata extraction
- Docker container generation
- Terraform/CDK generation for cloud deployments

## Requirements

- Python 3.11+
- typer
- rich
- pyyaml
- pydantic
