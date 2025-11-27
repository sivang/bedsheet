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

### v0.2: Multi-Agent Collaboration (In Design)

| Feature | Status | Priority |
|---------|--------|----------|
| Supervisor Agent | 📐 Designed | High |
| Supervisor Mode | 📐 Designed | High |
| Router Mode | 📐 Designed | High |
| Collaborator Agents | 📐 Designed | High |
| Delegate Tool | 📐 Designed | High |
| Parallel Delegation | 📐 Designed | Medium |
| DelegationEvent, CollaboratorEvent, etc. | 📐 Designed | Medium |

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

## v0.2 Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Supervisor class | Extends `Agent` | Reuse existing functionality, consistent API |
| Collaboration modes | Both supervisor + router | Match AWS Bedrock, flexibility |
| Delegation mechanism | Single `delegate` tool | Matches AWS `AgentCommunication::sendMessage` |
| Parallel delegation | Supported | Delegate to multiple agents at once |
| Memory sharing | Isolated per delegation | Simple, supervisor controls context |
| Error handling | Pass to supervisor LLM | Consistent with v0.1 tool errors |
| Event streaming | CollaboratorEvent wrapper | Full visibility into collaborator work |

### New Events for v0.2

- `RoutingEvent` - Router mode picks an agent
- `DelegationEvent` - Supervisor delegates task(s)
- `CollaboratorStartEvent` - Collaborator begins work
- `CollaboratorEvent` - Wraps any event from collaborator
- `CollaboratorCompleteEvent` - Collaborator finishes

---

## Architecture

### v0.1 (Current)

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

### v0.2 (Planned)

```
bedsheet/
├── agent.py              # Agent class (unchanged)
├── supervisor.py         # NEW: Supervisor class
├── action_group.py       # ActionGroup (unchanged)
├── events.py             # + new multi-agent events
├── exceptions.py         # (unchanged)
├── testing.py            # + MockSupervisor helpers
├── llm/
│   └── ...
└── memory/
    └── ...
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

---

## Links

- [v0.1 Design Doc](docs/plans/2025-11-25-bedsheet-v0.1-design.md)
- [v0.1 Implementation Plan](docs/plans/2025-11-25-bedsheet-v0.1-implementation.md)
- [v0.2 Multi-Agent Design Doc](docs/plans/2025-11-27-bedsheet-v0.2-multi-agent-design.md)
