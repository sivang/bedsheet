# Bedsheet Agents

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Tests](https://img.shields.io/badge/tests-96%20passing-brightgreen.svg)]()

**Cloud-agnostic agent orchestration for Python.** Build single agents or coordinate multi-agent teams with streaming events, parallel execution, and full observability.

```python
from bedsheet import Agent, Supervisor, ActionGroup
from bedsheet.llm import AnthropicClient

# Create a supervisor that coordinates research and analysis agents
supervisor = Supervisor(
    name="ResearchDirector",
    instruction="Coordinate research tasks across your team.",
    model_client=AnthropicClient(),
    collaborators=[researcher, analyst, writer],
    collaboration_mode="supervisor",
)

# Full visibility into every step
async for event in supervisor.invoke(session_id, "Analyze the AI chip market"):
    print(event)  # See delegations, tool calls, agent responses in real-time
```

---

## Why "Bedsheet"?

It's a playful nod to **AWS Bedrock Agents** - we "cover" the same concepts (agents, action groups, orchestration) while being cloud-agnostic. Like a bedsheet that covers your bed regardless of brand, Bedsheet covers your agent orchestration needs regardless of cloud provider.

Plus, we think agent frameworks shouldn't take themselves too seriously.

---

## Why Bedsheet?

### The Problem with Existing Frameworks

| Framework | Issue |
|-----------|-------|
| **LangChain** | Massive abstraction layers, hard to debug, "magic" that hides what's happening |
| **AutoGPT** | Autonomous but unpredictable, limited control over agent behavior |
| **CrewAI** | Role-based but rigid, complex configuration for simple tasks |

### The Bedsheet Approach

**Simple, Observable, Production-Ready**

```python
# No magic. No hidden abstractions. Just Python.
async for event in agent.invoke(session_id, user_input):
    if isinstance(event, ToolCallEvent):
        print(f"Calling: {event.tool_name}")  # See exactly what's happening
    elif isinstance(event, CompletionEvent):
        print(f"Response: {event.response}")
```

**Key Principles:**

1. **Streaming-First** - Events flow as they happen, not batch responses
2. **Full Observability** - See every tool call, every decision, every agent interaction
3. **Parallel by Default** - Multiple tool calls and agent delegations run concurrently
4. **Minimal Abstraction** - You can read our source code in an afternoon
5. **Type-Safe** - Full type hints, protocol-based extensibility

---

## Features

### Single Agent with Tools

```python
from bedsheet import Agent, ActionGroup
from bedsheet.llm import AnthropicClient

# Define tools with simple decorators
tools = ActionGroup(name="WebTools")

@tools.action(name="search", description="Search the web")
async def search(query: str) -> dict:
    # Your implementation
    return {"results": [...]}

@tools.action(name="fetch", description="Fetch a URL")
async def fetch(url: str) -> str:
    # Your implementation
    return "<html>..."

# Create an agent
agent = Agent(
    name="WebResearcher",
    instruction="You research topics on the web.",
    model_client=AnthropicClient(),
)
agent.add_action_group(tools)

# Invoke with streaming
async for event in agent.invoke("session-123", "Research quantum computing"):
    print(event)
```

### Multi-Agent Collaboration

The real power: **supervisors that coordinate teams of agents**.

```python
from bedsheet import Supervisor

# Create specialized agents
ethics_checker = Agent(name="EthicsChecker", instruction="Review requests for concerns.", ...)
researcher = Agent(name="Researcher", instruction="Research topics deeply.", ...)
writer = Agent(name="Writer", instruction="Write clear summaries.", ...)

# Supervisor coordinates them
supervisor = Supervisor(
    name="ContentDirector",
    instruction="""
    1. First, check ethics
    2. If approved, research the topic
    3. Then have the writer create a summary
    """,
    model_client=AnthropicClient(),
    collaborators=[ethics_checker, researcher, writer],
    collaboration_mode="supervisor",  # Orchestrate and synthesize
)
```

### Parallel Delegation

Supervisors can delegate to multiple agents **simultaneously**:

```python
# In the supervisor's instruction:
# "Delegate to researcher AND analyst in parallel..."

# The supervisor will call:
delegate(delegations=[
    {"agent_name": "Researcher", "task": "Find market data"},
    {"agent_name": "Analyst", "task": "Analyze competitors"},
])

# Both run concurrently, results synthesized together
```

### Rich Event Streaming

See everything that happens inside your agents:

```python
async for event in supervisor.invoke(session_id, user_input):
    match event:
        case DelegationEvent(delegations=d):
            print(f"Delegating to: {[x['agent_name'] for x in d]}")

        case CollaboratorStartEvent(agent_name=name):
            print(f"  [{name}] Starting...")

        case CollaboratorEvent(agent_name=name, inner_event=inner):
            if isinstance(inner, ToolCallEvent):
                print(f"  [{name}] Calling: {inner.tool_name}")

        case CollaboratorCompleteEvent(agent_name=name, response=resp):
            print(f"  [{name}] Done: {resp[:50]}...")

        case CompletionEvent(response=resp):
            print(f"\nFinal: {resp}")
```

### Two Collaboration Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| **Supervisor** | Orchestrates agents, synthesizes results | Complex tasks needing coordination |
| **Router** | Picks one agent, hands off entirely | Simple routing to specialists |

```python
# Supervisor mode: coordinates, then synthesizes
supervisor = Supervisor(..., collaboration_mode="supervisor")

# Router mode: just routes to the right agent
router = Supervisor(..., collaboration_mode="router")
```

---

## Real-World Example: Investment Research Assistant

A complete example showing ethics checking, parallel research, and synthesis:

```python
import asyncio
from bedsheet import Agent, Supervisor, ActionGroup
from bedsheet.llm import AnthropicClient

# === Define Tools ===

market_tools = ActionGroup(name="MarketTools")

@market_tools.action(name="get_stock_data", description="Get stock price and metrics")
async def get_stock_data(symbol: str) -> dict:
    await asyncio.sleep(0.5)  # Simulate API call
    return {"symbol": symbol, "price": 875.50, "change": "+3.2%", "pe_ratio": 65.4}

@market_tools.action(name="get_technicals", description="Get technical indicators")
async def get_technicals(symbol: str) -> dict:
    await asyncio.sleep(0.3)
    return {"rsi": 62.5, "macd": "bullish", "trend": "uptrend"}


news_tools = ActionGroup(name="NewsTools")

@news_tools.action(name="search_news", description="Search financial news")
async def search_news(company: str) -> dict:
    await asyncio.sleep(0.4)
    return {"articles": [
        {"headline": "Record AI Chip Revenue", "sentiment": "positive"},
        {"headline": "New GPU Architecture Announced", "sentiment": "positive"},
    ]}


# === Create Agents ===

market_analyst = Agent(
    name="MarketAnalyst",
    instruction="Analyze stocks using price data and technical indicators.",
    model_client=AnthropicClient(),
)
market_analyst.add_action_group(market_tools)

news_researcher = Agent(
    name="NewsResearcher",
    instruction="Research recent news and analyze sentiment.",
    model_client=AnthropicClient(),
)
news_researcher.add_action_group(news_tools)


# === Create Supervisor ===

advisor = Supervisor(
    name="InvestmentAdvisor",
    instruction="""You coordinate investment research.

    For each request:
    1. Delegate to MarketAnalyst AND NewsResearcher IN PARALLEL
    2. Synthesize their findings into a comprehensive analysis

    Use parallel delegation:
    delegate(delegations=[
        {"agent_name": "MarketAnalyst", "task": "Analyze [SYMBOL]"},
        {"agent_name": "NewsResearcher", "task": "Find news about [COMPANY]"}
    ])
    """,
    model_client=AnthropicClient(),
    collaborators=[market_analyst, news_researcher],
    collaboration_mode="supervisor",
)


# === Run It ===

async def main():
    async for event in advisor.invoke("session-1", "Analyze NVIDIA stock"):
        print(event)

asyncio.run(main())
```

**Output shows parallel execution:**
```
DelegationEvent(delegations=[{MarketAnalyst: ...}, {NewsResearcher: ...}])
CollaboratorStartEvent(agent_name='MarketAnalyst')
CollaboratorStartEvent(agent_name='NewsResearcher')  # Both start together!
CollaboratorEvent(agent_name='MarketAnalyst', inner_event=ToolCallEvent(...))
CollaboratorEvent(agent_name='NewsResearcher', inner_event=ToolCallEvent(...))
...
CompletionEvent(response='## NVIDIA Analysis\n\nPrice: $875.50 (+3.2%)...')
```

See [examples/investment_advisor.py](examples/investment_advisor.py) for the full runnable demo.

---

## Comparison with Other Frameworks

| Feature | Bedsheet | AWS Bedrock Agents | LangChain | CrewAI | AutoGPT |
|---------|----------|-------------------|-----------|--------|---------|
| **Learning Curve** | Low | Medium | High | Medium | Medium |
| **Streaming Events** | Built-in | Limited | Add-on | Limited | No |
| **Multi-Agent** | Native | Native | Via LangGraph | Native | Limited |
| **Parallel Execution** | Default | Manual | Manual | Limited | No |
| **Observability** | Full event stream | CloudWatch | Callbacks | Logging | Logging |
| **Cloud Lock-in** | None | AWS only | None | None | None |
| **Lines of Code** | ~1000 | N/A (managed) | ~100,000+ | ~10,000 | ~20,000 |
| **Self-Hosted** | Yes | No | Yes | Yes | Yes |
| **Cost Model** | Your LLM costs | AWS markup + LLM | Your LLM costs | Your LLM costs | Your LLM costs |

### When to Use Bedsheet

**Choose Bedsheet if you want:**
- Full visibility into agent execution
- Simple, readable code you can debug
- Native multi-agent support with parallel execution
- Streaming-first architecture
- Something you can understand in a day

---

## Enterprise Ready

Bedsheet is designed for production use from day one:

### Observability & Debugging
- **Full event streaming** - Every tool call, every agent decision, every result is an event you can log, monitor, and analyze
- **No black boxes** - Unlike managed services, you can step through every line of code
- **Easy integration** - Events can feed into your existing observability stack (Datadog, Prometheus, etc.)

### Reliability
- **96 tests** covering all core functionality
- **Type-safe** - Full type hints catch errors before runtime
- **Error recovery** - Failed tool calls are passed back to the LLM for intelligent retry
- **Max iteration limits** - Built-in protection against runaway agents

### Scalability
- **Async-first** - Built on `asyncio` for high concurrency
- **Parallel execution** - Tools and agent delegations run concurrently by default
- **Pluggable memory** - Swap `InMemory` for `RedisMemory` for distributed state
- **Stateless agents** - Session state lives in memory backend, agents can run anywhere

### Security & Compliance
- **Self-hosted** - Your data never leaves your infrastructure
- **No vendor lock-in** - Switch LLM providers by implementing `LLMClient` protocol
- **Audit trail** - Event stream provides complete execution history
- **Open source** - Full code visibility, no hidden behaviors

### Simple Operations
- **~1000 lines of code** - Small enough to audit, understand, and maintain
- **Zero external dependencies** beyond `anthropic` SDK
- **Standard Python** - No custom DSLs, no YAML configs, just Python

---

## Quick Start

**Try it instantly - no API key required:**

```bash
pip install bedsheet-agents
python -m bedsheet
```

This runs a multi-agent demo showing parallel delegation, event streaming, and supervisor synthesis using simulated responses.

**Output:**
```
======================================================================
  BEDSHEET AGENTS - Multi-Agent Collaboration Demo
======================================================================

User: Analyze NVIDIA stock for me

[0.1s] PARALLEL DELEGATION - dispatching 2 agents:
         -> MarketAnalyst: Analyze NVIDIA (NVDA) stock price and technical...
         -> NewsResearcher: Find and analyze recent news about NVIDIA

[0.2s] || [MarketAnalyst] Starting...
[0.2s] || [NewsResearcher] Starting...
         [MarketAnalyst] -> get_stock_data({'symbol': 'NVDA'})
         [NewsResearcher] -> search_news({'company': 'NVIDIA'})
...
```

---

## Installation

```bash
pip install bedsheet-agents
```

With Redis memory backend:
```bash
pip install bedsheet-agents[redis]
```

Development:
```bash
pip install bedsheet-agents[dev]
```

## Requirements

- Python 3.11+
- Anthropic API key for real usage (set `ANTHROPIC_API_KEY` environment variable)
- No API key needed for the demo: `python -m bedsheet`

---

## Documentation

- [Multi-Agent Guide](docs/multi-agent-guide.md) - Complete walkthrough of supervisor patterns
- [Examples](examples/) - Runnable demos
- [API Reference](docs/) - Coming soon

---

## Architecture

```
bedsheet/
├── agent.py          # Single agent with ReAct loop
├── supervisor.py     # Multi-agent coordination
├── action_group.py   # Tool definitions with @action decorator
├── events.py         # 10 event types for streaming
├── llm/
│   ├── base.py       # LLMClient protocol
│   └── anthropic.py  # Claude integration
└── memory/
    ├── base.py       # Memory protocol
    ├── in_memory.py  # Dict-based (development)
    └── redis.py      # Redis-based (production)
```

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Clone and install dev dependencies
git clone https://github.com/vitakka/bedsheet-agents
cd bedsheet-agents
pip install -e ".[dev]"

# Run tests
pytest -v
```

---

## Roadmap

- [x] **v0.1** - Single agent, tools, streaming
- [x] **v0.2** - Multi-agent, supervisor, parallel delegation
- [ ] **v0.3** - Knowledge bases, RAG integration
- [ ] **v0.4** - Guardrails, content filtering
- [ ] **v0.5** - MCP integration, code interpreter

---

## License

Apache 2.0 - see [LICENSE](LICENSE) for details.

---

**Built with Claude. Designed for humans.**
