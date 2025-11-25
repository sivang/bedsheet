# Bedsheet Agents

Cloud-agnostic agent orchestration inspired by AWS Bedrock Agents. Build agentic workflows with Claude as the LLM, pluggable memory backends, and event streaming.

## Features

- **Single Agent with ReAct Loop** - Claude-powered agent with tool use and streaming events
- **Decorator-Based Actions** - Define actions with `@group.action()` decorator, automatic schema inference
- **Cloud-Agnostic Memory** - InMemory for development, Redis for production, pluggable protocol
- **Streaming Events** - Tool calls, results, completions, and errors streamed as they happen
- **Parallel Tool Execution** - Multiple tools called simultaneously when requested
- **Error Recovery** - Tool errors passed back to LLM for recovery attempts

## Installation

Install core library:

```bash
pip install bedsheet-agents
```

With Redis memory backend (optional):

```bash
pip install bedsheet-agents[redis]
```

## Quick Start

```python
import asyncio
from bedsheet import Agent, ActionGroup
from bedsheet.llm import AnthropicClient
from bedsheet.memory import InMemory

# Create agent
agent = Agent(
    name="WeatherAssistant",
    instruction="You are a helpful weather assistant.",
    model_client=AnthropicClient(),
    memory=InMemory(),
)

# Define action group
weather = ActionGroup(name="Weather")

@weather.action(name="get_weather", description="Get weather for a city")
async def get_weather(city: str) -> dict:
    # Your implementation here
    return {"city": city, "temp": 72, "condition": "sunny"}

agent.add_action_group(weather)

# Invoke agent
async def main():
    async for event in agent.invoke(
        session_id="user-123",
        input_text="What's the weather in SF?"
    ):
        print(event)

asyncio.run(main())
```

## Development

Install with dev dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Run all tests verbosely:

```bash
pytest -v
```

## License

MIT
