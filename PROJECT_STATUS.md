# Bedsheet Agents - Project Status

## Current Version: v0.1.0

### Completed Features

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

**Tests:** 74 passing
**Code:** ~700 lines

---

## Roadmap

### v0.2: Multi-Agent Collaboration (Next)

| Feature | Status | Priority |
|---------|--------|----------|
| Supervisor Agent | 🔮 Planned | High |
| Supervisor-Router Mode | 🔮 Planned | High |
| Collaborator Agents | 🔮 Planned | High |
| Agent-to-Agent Data Handoff | 🔮 Planned | High |
| Parallel Sub-Agent Execution | 🔮 Planned | Medium |
| DelegationEvent, RoutingEvent | 🔮 Planned | Medium |

### v0.3: Knowledge & Safety

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
├── action_group.py       # ActionGroup + @action decorator
├── events.py             # Event types for streaming
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

### Planned for v0.2

```
bedsheet/
├── supervisor.py         # Supervisor agent (extends Agent)
├── collaboration.py      # Collaboration modes, routing
└── events.py             # + DelegationEvent, RoutingEvent, CollaboratorResultEvent
```

---

## Design Decisions Log

### v0.1 Decisions

1. **Bedrock-like API** - Mirror AWS Bedrock concepts (Agent, ActionGroup) for familiarity
2. **instruction vs orchestration_template** - Separate simple instruction from full prompt template
3. **Streaming-first** - Async iterator with events, not batch responses
4. **Parallel by default** - Multiple tool calls execute concurrently
5. **Protocol-based extensibility** - Memory and LLMClient as protocols

---

## Links

- [v0.1 Design Doc](docs/plans/2025-11-25-bedsheet-v0.1-design.md)
- [v0.1 Implementation Plan](docs/plans/2025-11-25-bedsheet-v0.1-implementation.md)
