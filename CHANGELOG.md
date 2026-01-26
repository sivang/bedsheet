# Changelog

All notable changes to Bedsheet Agents will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.8] - 2026-01-26

### Changed

- **GCP Model Default** - Updated `bedsheet init --target gcp` to use `gemini-3-flash-preview` (was `gemini-2.5-flash`)
  - Reflects latest Gemini model availability

### Added

- **Demo Recording Plan** - Added comprehensive demo recording guide (`docs/DEMO_RECORDING_PLAN.md`)
  - 3-4 minute multi-cloud deployment demo script
  - Pre-recording checklist and dry-run tests
  - Contingency plans for common issues
- **GCP Deployment Deep Dive** - Added link to `gcp-deployment-deep-dive.html` in README and CLAUDE.md

## [0.4.7] - 2026-01-22

### Changed

- **`make ui` Improvements** - Better first-time experience
  - Checks if `cloud-run-proxy` component is installed before starting
  - Clear instructions if component missing: `gcloud components install cloud-run-proxy`
  - Opens browser directly to `/dev-ui/` path
  - No more interactive prompts during `make ui`

## [0.4.6] - 2026-01-22

### Added

- **`make ui` Command** - One-command access to deployed agent's Dev UI
  - Automatically handles Cloud Run authentication via `gcloud run services proxy`
  - Opens browser to `http://localhost:8080` with authenticated tunnel
  - No manual token handling required

## [0.4.5] - 2026-01-22

### Added

- **Project Consistency Check** - Preflight now detects mismatches between `terraform.tfvars` and `gcloud config`
  - Warns when projects don't match
  - Offers to auto-fix by running `gcloud config set project`
  - Prevents silent deployment to wrong project
- **Project Consistency Documentation** - Added warning section in `DEPLOYMENT_GUIDE.md`

## [0.4.4] - 2026-01-22

### Added

- **Credential Preflight Check** - New `make preflight` command warns if `GOOGLE_APPLICATION_CREDENTIALS` is set
  - Detects potential cross-project credential issues before deployment
  - Prevents silent 403 errors at runtime
  - Interactive prompt to continue or abort
- **Credential Warning in Docs** - Prominent warning box in `DEPLOYMENT_GUIDE.md` explaining SDK credential priority
- **Troubleshooting Guide** - Added "#1 gotcha" section for credential issues

### Changed

- `make deploy` and `make dev` now automatically run credential checks
- Updated preflight checks list in deployment guide

## [0.4.3] - 2026-01-22

### Fixed

- **CLI Version Display** - Now uses `importlib.metadata` to dynamically read version from package metadata instead of hardcoded string

## [0.4.2] - 2026-01-22

### Added

- **Comprehensive GCP Deployment Documentation** - Deep dive guide with Mermaid diagrams
  - `docs/gcp-deployment-deep-dive.md` and `.html`
  - Architecture diagrams, authentication flows, troubleshooting guides
  - "The Great Debugging" story documenting credential priority issues

### Fixed

- **GCP ADK Dev UI** - Dockerfile template now uses `web` mode instead of `api_server`
  - Dev UI accessible at `/dev-ui/` on Cloud Run deployments
  - Local development with `make dev` includes interactive UI
- **GCP Authentication Documentation** - Clarified SDK credential priority:
  1. `GOOGLE_APPLICATION_CREDENTIALS` environment variable (highest)
  2. Application Default Credentials (ADC)
  3. Compute Engine / Cloud Run service account
- **GCP Terraform** - Improved ADC handling and removed google_project_service resources
  - APIs now enabled via gcloud CLI (avoids ADC permission issues)
  - Terraform focuses on resource creation only

### Changed

- **Gemini Model** - Updated to `gemini-2.0-flash` (was `gemini-1.5-flash`)
- **Global Endpoint** - GCP target uses `global` location for Gemini 2.0+ models

## [0.4.0] - 2026-01-18

### Added

- **CLI Tool** - New `bedsheet` command-line interface
  - `bedsheet init <name>` - Initialize a new agent project
  - `bedsheet generate --target <target>` - Generate deployment artifacts
  - `bedsheet validate` - Validate bedsheet.yaml configuration
  - `bedsheet deploy --target <target>` - Deploy to cloud platform
- **Deployment Targets** - Multi-platform deployment support
  - **Local (Docker)** - FastAPI server with hot reload for development
  - **GCP (Terraform)** - Google Cloud Run with ADK (Agent Development Kit)
  - **AWS CDK** - Amazon Bedrock agents via AWS CDK
  - **AWS Terraform** - Amazon Bedrock agents via Terraform
- **Debug UI** - Real-time agent visualization for development
  - Embedded React UI with event streaming
  - Thinking/rationale event extraction from LLM traces
  - Deduplication of repeated thinking events
  - Tool call and collaborator activity tracking
- **Configuration System** - YAML-based project configuration
  - `bedsheet.yaml` schema with Pydantic validation
  - Multi-agent support with supervisor patterns
  - Per-target configuration (region, model, memory)
- **Resource Management** - Cloud resource identification
  - Consistent `bedsheet-` prefix for infrastructure resources
  - Tagging: ManagedBy, BedsheetVersion, Project, Environment, AgentType
- **Multi-Environment Support** - dev/staging/prod deployment patterns
  - GitHub Actions CI/CD workflows for each target
  - Environment-specific configuration

### Changed

- Filter delegate action for supervisors with collaborators (AWS)
- Supervisors use native platform collaboration instead of Lambda handlers

### Fixed

- Duplicate thinking events in Debug UI
- `<answer>` tag content incorrectly appearing in thinking panel
- Delegate action translation for multi-agent AWS deployments

## [0.3.0] - 2025-12-03

### Added

- **Structured Outputs** - New `OutputSchema` class for enforcing JSON schema compliance
  - `OutputSchema.from_pydantic(Model)` - Create from Pydantic BaseModel
  - `OutputSchema.from_dict(schema)` - Create from JSON schema dict
- **Anthropic Structured Outputs Beta** - Integration with Claude's constrained decoding
  - Uses `structured-outputs-2025-11-13` beta header
  - Guarantees 100% schema compliance via constrained token generation
- **LLMResponse.parsed_output** - New field for validated structured data
- **MockLLMClient structured output support** - For testing agents with output schemas

### Fixed

- **Optional Redis Import** - `RedisMemory` is now conditionally imported, allowing the package to work without redis installed (redis remains an optional dependency)
- **Lint Compliance** - Fixed ruff lint warning for optional import pattern

## [0.2.0] - 2024-11-28

### Added

- **Supervisor Agent** - New `Supervisor` class extending `Agent` for multi-agent coordination
- **Supervisor Mode** - Orchestrate multiple agents and synthesize their results
- **Router Mode** - Direct handoff to a single agent without synthesis
- **Parallel Delegation** - Delegate to multiple agents simultaneously with `asyncio.gather`
- **Built-in Delegate Tool** - Automatic `delegate` action for agent coordination
- **New Event Types**:
  - `RoutingEvent` - Emitted when router picks an agent
  - `DelegationEvent` - Emitted when supervisor delegates task(s)
  - `CollaboratorStartEvent` - Emitted when a collaborator begins
  - `CollaboratorEvent` - Wraps events from collaborators for visibility
  - `CollaboratorCompleteEvent` - Emitted when a collaborator finishes
- **Orchestration Templates** - `$collaborators_summary$` variable for system prompts
- **Investment Advisor Example** - Full multi-agent demo in `examples/`
- **Multi-Agent Guide** - Comprehensive documentation in `docs/`

### Changed

- Event union type now includes 10 event types (was 5)
- Updated project structure with `supervisor.py`

## [0.1.0] - 2024-11-25

### Added

- **Agent Class** - Core agent with ReAct loop and tool calling
- **ActionGroup** - Tool definitions with `@action` decorator
- **Automatic Schema Inference** - Type hints converted to JSON schema
- **Streaming Events**:
  - `ThinkingEvent` - LLM thinking/reasoning
  - `ToolCallEvent` - Tool invocation
  - `ToolResultEvent` - Tool results
  - `CompletionEvent` - Final response
  - `ErrorEvent` - Error handling
- **Parallel Tool Execution** - Multiple tools run concurrently
- **Pluggable Memory**:
  - `InMemory` - Dict-based for development
  - `RedisMemory` - Redis-based for production
- **Orchestration Template** - Customizable system prompt with variables
- **AnthropicClient** - Claude integration
- **Error Recovery** - Tool errors passed to LLM for retry
- **Max Iterations Safety** - Prevents infinite loops
- **MockLLMClient** - Testing utilities

[0.4.0]: https://github.com/sivang/bedsheet/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/sivang/bedsheet/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/sivang/bedsheet/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/sivang/bedsheet/releases/tag/v0.1.0
