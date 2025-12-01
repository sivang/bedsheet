# Bedsheet Agents - Claude Code Context

## What Is This Project?

**Bedsheet** is a cloud-agnostic Python framework for building AI agents. Named as a playful jab at AWS Bedrock - it "covers" the same concepts (agents, action groups, orchestration) while letting you define agents in code, not through a cluttered web UI.

## Quick Facts

- **Version:** 0.2 (Multi-Agent)
- **Tests:** 99 passing (`pytest -v`)
- **Demo:** `python -m bedsheet` (requires `ANTHROPIC_API_KEY`, uses Claude Sonnet 4.5)
- **Default Model:** `claude-sonnet-4-5-20250929`

## Key Features

1. **Single Agents** - Agent class with tools via `@action` decorator
2. **Multi-Agent** - Supervisor pattern for orchestrating multiple agents
3. **Parallel Delegation** - Run multiple agents simultaneously
4. **Event Streaming** - Full visibility: ToolCallEvent, TextTokenEvent, CompletionEvent, etc.
5. **Token Streaming** - `stream=True` for word-by-word LLM output

## Architecture

```
bedsheet/
├── __init__.py        # Exports: Agent, Supervisor, ActionGroup
├── __main__.py        # Demo: python -m bedsheet
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
└── testing.py         # MockLLMClient for tests
```

## Documentation

| File | Purpose |
|------|---------|
| `docs/user-guide.html` | Progressive 12-lesson tutorial |
| `docs/technical-guide.html` | Python patterns deep dive |
| `docs/multi-agent-guide.md` | Supervisor patterns |
| `PROJECT_STATUS.md` | Detailed project status and session history |

## Common Commands

```bash
# Run tests
pytest -v

# Run demo (requires API key)
export ANTHROPIC_API_KEY=your-key
python -m bedsheet

# Open documentation
open docs/user-guide.html
open docs/technical-guide.html
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
