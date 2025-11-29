# Bedsheet Agents - Project Status

## Current Version: v0.2.0 🚀 Release Ready

### Release Artifacts

| Artifact | Status |
|----------|--------|
| Source Code | ✅ Complete |
| Test Suite | ✅ 96 tests passing |
| README.md | ✅ Comprehensive with examples |
| CHANGELOG.md | ✅ v0.1.0 and v0.2.0 documented |
| CONTRIBUTING.md | ✅ Contributor guidelines |
| LICENSE | ✅ Apache 2.0 |
| CI/CD | ✅ GitHub Actions (test, lint, typecheck) |
| Documentation | ✅ Multi-agent guide |
| Examples | ✅ Investment advisor demo |
| Demo | ✅ `python -m bedsheet` (requires API key) |
| pyproject.toml | ✅ PyPI ready |

---

### v0.1 Features (Complete)

| Feature | Status | Notes |
|---------|--------|-------|
| Single Agent with ReAct loop | ✅ Done | `Agent` class with tool calling |
| ActionGroup + @action decorator | ✅ Done | Auto schema inference from type hints |
| Streaming Events | ✅ Done | ToolCallEvent, ToolResultEvent, CompletionEvent, ErrorEvent, ThinkingEvent |
| Parallel Tool Execution | ✅ Done | asyncio.gather for concurrent tools |
| Pluggable Memory | ✅ Done | InMemory, RedisMemory |
| Orchestration Template | ✅ Done | $instruction$, $agent_name$, $current_datetime$, $tools_summary$ |
| AnthropicClient | ✅ Done | Claude integration |
| Error Recovery | ✅ Done | Errors passed to LLM for retry |
| Max Iterations Safety | ✅ Done | Prevents infinite loops |

### v0.2 Features (Complete)

| Feature | Status | Notes |
|---------|--------|-------|
| Supervisor Agent | ✅ Done | Extends Agent, manages collaborators |
| Supervisor Mode | ✅ Done | Orchestration with synthesis |
| Router Mode | ✅ Done | Direct handoff, no synthesis |
| Collaborator Agents | ✅ Done | Regular Agents as collaborators |
| Delegate Tool | ✅ Done | Built-in tool for delegation |
| Parallel Delegation | ✅ Done | Delegate to multiple agents at once |
| Multi-Agent Events | ✅ Done | RoutingEvent, DelegationEvent, CollaboratorEvent, etc. |

**Tests:** 96 passing
**Code:** ~1000 lines

---

## Roadmap

### v0.3: Knowledge & Safety (Next)

| Feature | Status | Priority |
|---------|--------|----------|
| Knowledge Base Protocol | 🔮 Planned | High |
| RAG Integration | 🔮 Planned | High |
| Guardrails Protocol | 🔮 Planned | Medium |
| Content Filtering | 🔮 Planned | Medium |
| PII Detection | 🔮 Planned | Low |

### v0.4: Advanced Features

| Feature | Status | Priority |
|---------|--------|----------|
| AMAZON.UserInput equivalent | 🔮 Planned | Medium |
| Code Interpreter | 🔮 Planned | Medium |
| Inline Agents (runtime config) | 🔮 Planned | Low |
| MCP Integration | 🔮 Planned | Low |

---

## Architecture

```
bedsheet/
├── agent.py              # Agent class (single agent)
├── supervisor.py         # Supervisor class (multi-agent)
├── action_group.py       # ActionGroup + @action decorator
├── events.py             # Event types for streaming (10 types)
├── exceptions.py         # Custom exceptions
├── testing.py            # MockLLMClient for tests
├── llm/
│   ├── base.py           # LLMClient protocol
│   └── anthropic.py      # Claude implementation
└── memory/
    ├── base.py           # Memory protocol
    ├── in_memory.py      # Dict-based storage
    └── redis.py          # Redis storage
```

---

## Design Decisions Log

### v0.1 Decisions

1. **Bedrock-like API** - Mirror AWS Bedrock concepts (Agent, ActionGroup) for familiarity
2. **instruction vs orchestration_template** - Separate simple instruction from full prompt template
3. **Streaming-first** - Async iterator with events, not batch responses
4. **Parallel by default** - Multiple tool calls execute concurrently
5. **Protocol-based extensibility** - Memory and LLMClient as protocols

### v0.2 Decisions

1. **Supervisor IS-A Agent** - Extend Agent rather than separate class hierarchy
2. **Single delegate tool** - Match AWS's AgentCommunication::sendMessage pattern
3. **Isolated memory** - Collaborators don't share supervisor's conversation
4. **Error passback** - Collaborator errors go to supervisor LLM for handling
5. **Full event streaming** - Wrap collaborator events for visibility
6. **Router mode** - Direct handoff without synthesis for simple routing

---

## Links

- [v0.1 Design Doc](docs/plans/2025-11-25-bedsheet-v0.1-design.md)
- [v0.1 Implementation Plan](docs/plans/2025-11-25-bedsheet-v0.1-implementation.md)
- [v0.2 Multi-Agent Design Doc](docs/plans/2025-11-27-bedsheet-v0.2-multi-agent-design.md)
- [v0.2 Implementation Plan](docs/plans/2025-11-27-bedsheet-v0.2-implementation.md)
