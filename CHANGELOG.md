# Changelog

All notable changes to Bedsheet Agents will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.3.0]: https://github.com/sivang/bedsheet/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/sivang/bedsheet/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/sivang/bedsheet/releases/tag/v0.1.0
