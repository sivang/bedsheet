# Bedsheet Agents - Claude Code Context

## What Is This Project?

**Bedsheet** is a cloud-agnostic Python framework for building AI agents. Named as a playful jab at AWS Bedrock - it "covers" the same concepts (agents, action groups, orchestration) while letting you define agents in code, not through a cluttered web UI.

## Quick Facts

- **Version:** 0.4.7 (Released on PyPI), codename "Hermes"
- **Tests:** 265 passing (`pytest -v`)
- **Demo:** `uvx bedsheet demo` (requires `ANTHROPIC_API_KEY`, uses REAL DATA from Yahoo Finance + DuckDuckGo)
- **Default Model:** `claude-sonnet-4-5-20250929`
- **Demo deps:** `pip install bedsheet[demo]` (adds yfinance, ddgs)

## Key Features

1. **Single Agents** - Agent class with tools via `@action` decorator
2. **Multi-Agent** - Supervisor pattern for orchestrating multiple agents
3. **Parallel Delegation** - Run multiple agents simultaneously
4. **Event Streaming** - Full visibility: ToolCallEvent, TextTokenEvent, CompletionEvent, etc.
5. **Token Streaming** - `stream=True` for word-by-word LLM output
6. **Structured Outputs** - Pydantic-based output schemas with Anthropic beta integration
7. **CLI (v0.4)** - `bedsheet init`, `generate`, `validate`, `deploy` commands
8. **Multi-Target Deployment (v0.4)** - Local (Docker), GCP (Terraform), AWS (CDK)

## Architecture

```
bedsheet/
├── __init__.py        # Exports: Agent, Supervisor, ActionGroup
├── __main__.py        # Demo: uvx bedsheet
├── agent.py           # Single agent with ReAct loop
├── supervisor.py      # Multi-agent coordination (extends Agent)
├── action_group.py    # @action decorator, tool registration
├── events.py          # 11 event types for streaming
├── llm/
│   ├── base.py        # LLMClient protocol
│   └── anthropic.py   # Claude integration with streaming
├── memory/
│   ├── base.py        # Memory protocol
│   ├── in_memory.py   # Dict-based (dev)
│   └── redis.py       # Redis-based (prod)
├── testing.py         # MockLLMClient for tests
├── cli/               # NEW in v0.4
│   └── main.py        # Typer CLI (init, generate, validate, deploy)
└── deploy/            # NEW in v0.4
    ├── config.py      # bedsheet.yaml Pydantic schema
    ├── introspect.py  # Agent metadata extraction
    ├── targets/       # Deployment generators
    │   ├── base.py    # DeploymentTarget protocol
    │   ├── local.py   # Docker/FastAPI
    │   ├── gcp.py     # ADK/Terraform
    │   └── aws.py     # CDK/Bedrock
    └── templates/     # Jinja2 templates (local/, gcp/, aws/)
```

## Documentation

| File | Purpose |
|------|---------|
| `docs/user-guide.html` | Progressive 12-lesson tutorial |
| `docs/technical-guide.html` | Python patterns deep dive |
| `docs/deployment-guide.html` | Local, GCP, and AWS deployment |
| `docs/gcp-deployment-deep-dive.html` | GCP architecture, troubleshooting, best practices |
| `docs/multi-agent-guide.html` | Supervisor patterns |
| `PROJECT_STATUS.md` | Detailed project status and session history |

## Common Commands

```bash
# Run tests
pytest -v

# Run demo (requires API key)
export ANTHROPIC_API_KEY=your-key
uvx bedsheet demo

# CLI commands (v0.4)
bedsheet init my-agent             # Create new agent project
bedsheet generate --target aws     # Generate deployment artifacts
bedsheet validate                  # Validate bedsheet.yaml
bedsheet deploy --target gcp       # Deploy to target

# Open documentation
open docs/user-guide.html
open docs/technical-guide.html
```

## Python Environment Rules

- **Always use `uvx`** when testing published packages (e.g., `uvx bedsheet demo`)
- **Always use a venv** - never install into system Python
- **Prefer `uv` over `pip`** - use `uv pip install` or `uv add` instead of `pip install`
- **For E2E testing published packages:** use `uvx <package>` which auto-creates isolated env

```bash
# GOOD - testing published package
uvx bedsheet demo
uvx bedsheet init my-agent

# GOOD - development with venv
uv venv && source .venv/bin/activate
uv pip install -e .

# AVOID - don't use pip directly
pip install bedsheet  # NO - use uv pip install or uvx
```

## Code Style

- Python 3.11+
- Type hints everywhere
- Async/await for all I/O
- Protocols for extensibility (not ABCs)
- Dataclasses for events and data structures
- `@action` decorator for defining tools

## Important Patterns

1. **Events not returns** - `invoke()` yields events, doesn't return a response
2. **Parallel by default** - Multiple tool calls run concurrently via `asyncio.gather`
3. **Supervisor IS-A Agent** - Inheritance, not composition
4. **Collaborators are isolated** - They don't share supervisor's memory

## Session History

See `PROJECT_STATUS.md` for detailed session summaries and what was done when.
