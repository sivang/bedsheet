# Bedsheet User Guide

A progressive tutorial from your first agent to complex multi-agent orchestration.

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Your First Agent](#2-your-first-agent)
3. [Adding Tools](#3-adding-tools)
4. [Understanding Events](#4-understanding-events)
5. [Streaming Responses](#5-streaming-responses)
6. [Conversation Memory](#6-conversation-memory)
7. [Multiple Tools](#7-multiple-tools)
8. [Your First Multi-Agent System](#8-your-first-multi-agent-system)
9. [Parallel Delegation](#9-parallel-delegation)
10. [Deep Agent Hierarchies](#10-deep-agent-hierarchies)
11. [Router Mode](#11-router-mode)
12. [Best Practices](#12-best-practices)

---

## 1. Getting Started

### Installation

```bash
uv pip install bedsheet
```

### Set Your API Key

Bedsheet uses Claude by default. Get your API key from [console.anthropic.com](https://console.anthropic.com/):

```bash
export ANTHROPIC_API_KEY=your-key-here
```

### Verify Installation

```bash
uvx bedsheet demo
```

This runs a demo showing multi-agent collaboration. If it works, you're ready!

---

## 2. Your First Agent

Let's create the simplest possible agent - one that just responds to messages without any tools:

```python
import asyncio
from bedsheet import Agent
from bedsheet.llm import AnthropicClient
from bedsheet.events import CompletionEvent

async def main():
    # Create an agent
    agent = Agent(
        name="Assistant",
        instruction="You are a helpful assistant. Be concise.",
        model_client=AnthropicClient(),
    )

    # Invoke the agent and get events
    async for event in agent.invoke(
        session_id="my-session",
        input_text="What is Python?"
    ):
        if isinstance(event, CompletionEvent):
            print(event.response)

asyncio.run(main())
```

**What's happening:**

1. **`Agent`** - The core class that talks to an LLM
2. **`name`** - A name for your agent (used in logs and multi-agent setups)
3. **`instruction`** - The system prompt that defines the agent's behavior
4. **`model_client`** - The LLM to use (Anthropic's Claude by default)
5. **`invoke()`** - Runs the agent and yields events as they happen
6. **`session_id`** - Groups messages into a conversation (more on this later)
7. **`CompletionEvent`** - The final response from the agent

**Output:**
```
Python is a high-level, interpreted programming language known for its readable
syntax and versatility. It's widely used for web development, data science,
automation, and AI/ML applications.
```

---

## 3. Adding Tools

Agents become powerful when they can use tools. Let's give our agent the ability to check the weather:

```python
import asyncio
from bedsheet import Agent, ActionGroup
from bedsheet.llm import AnthropicClient
from bedsheet.events import CompletionEvent, ToolCallEvent, ToolResultEvent

# Step 1: Create an ActionGroup to hold tools
tools = ActionGroup(name="WeatherTools")

# Step 2: Define a tool using the @action decorator
@tools.action(
    name="get_weather",
    description="Get the current weather for a city"
)
async def get_weather(city: str) -> dict:
    """In a real app, this would call a weather API."""
    # Simulated weather data
    weather_data = {
        "New York": {"temp": 72, "condition": "Sunny"},
        "London": {"temp": 58, "condition": "Cloudy"},
        "Tokyo": {"temp": 68, "condition": "Partly cloudy"},
    }
    return weather_data.get(city, {"temp": 70, "condition": "Unknown"})

async def main():
    # Step 3: Create an agent
    agent = Agent(
        name="WeatherBot",
        instruction="You help users check the weather. Use the get_weather tool when asked about weather.",
        model_client=AnthropicClient(),
    )

    # Step 4: Attach the tools to the agent
    agent.add_action_group(tools)

    # Step 5: Invoke
    async for event in agent.invoke("session-1", "What's the weather in Tokyo?"):
        if isinstance(event, ToolCallEvent):
            print(f"[Tool Call] {event.tool_name}({event.tool_input})")
        elif isinstance(event, ToolResultEvent):
            print(f"[Tool Result] {event.result}")
        elif isinstance(event, CompletionEvent):
            print(f"\n{event.response}")

asyncio.run(main())
```

**Output:**
```
[Tool Call] get_weather({'city': 'Tokyo'})
[Tool Result] {'temp': 68, 'condition': 'Partly cloudy'}

The weather in Tokyo is currently 68°F and partly cloudy.
```

**What's happening:**

1. The LLM sees your message and the available tools
2. It decides to call `get_weather` with `city="Tokyo"`
3. Bedsheet executes your function and sends the result back to the LLM
4. The LLM generates a natural language response based on the tool result

---

## 4. Understanding Events

Bedsheet uses an **event-driven architecture**. Instead of returning a single response, `invoke()` yields events as things happen. This gives you full visibility into the agent's behavior.

### All Event Types

```python
from bedsheet.events import (
    # Single agent events
    TextTokenEvent,      # A token from streaming response
    ToolCallEvent,       # LLM wants to call a tool
    ToolResultEvent,     # Tool execution completed
    CompletionEvent,     # Agent finished with final response
    ErrorEvent,          # Something went wrong
    ThinkingEvent,       # Extended thinking content (Claude 3.5+)

    # Multi-agent events
    DelegationEvent,     # Supervisor delegating to agents
    CollaboratorStartEvent,   # A collaborator agent is starting
    CollaboratorEvent,        # Wraps events from collaborators
    CollaboratorCompleteEvent,# A collaborator finished
    RoutingEvent,        # Router picked an agent
)
```

### Event Handling Pattern

```python
async for event in agent.invoke(session_id, user_input):
    match event:
        case ToolCallEvent(tool_name=name, tool_input=args):
            print(f"Calling {name} with {args}")

        case ToolResultEvent(result=result, error=error):
            if error:
                print(f"Tool failed: {error}")
            else:
                print(f"Tool returned: {result}")

        case CompletionEvent(response=text):
            print(f"Final: {text}")

        case ErrorEvent(error=err, recoverable=can_retry):
            print(f"Error: {err}, Recoverable: {can_retry}")
```

---

## 5. Streaming Responses

By default, you get the complete response in `CompletionEvent`. But you can stream token-by-token for a better UX:

```python
async for event in agent.invoke(session_id, user_input, stream=True):
    if isinstance(event, TextTokenEvent):
        print(event.token, end="", flush=True)  # Print each word as it arrives
    elif isinstance(event, CompletionEvent):
        print()  # Newline after streaming completes
```

This is how ChatGPT and Claude show responses word-by-word instead of making you wait for the complete answer.

---

## 6. Conversation Memory

Agents can remember previous messages in a session using **Memory**:

```python
from bedsheet import Agent
from bedsheet.memory import InMemory  # Simple dict-based memory

agent = Agent(
    name="Assistant",
    instruction="You are helpful.",
    model_client=AnthropicClient(),
    memory=InMemory(),  # Enable conversation memory
)

# First message
async for event in agent.invoke("session-1", "My name is Alice"):
    if isinstance(event, CompletionEvent):
        print(event.response)
# Output: "Nice to meet you, Alice!"

# Second message - agent remembers!
async for event in agent.invoke("session-1", "What's my name?"):
    if isinstance(event, CompletionEvent):
        print(event.response)
# Output: "Your name is Alice."

# Different session - no memory
async for event in agent.invoke("session-2", "What's my name?"):
    if isinstance(event, CompletionEvent):
        print(event.response)
# Output: "I don't know your name yet."
```

**Session IDs matter!** Same session = continued conversation. Different session = fresh start.

### Memory Backends

```python
from bedsheet.memory import InMemory, RedisMemory

# Development: Simple in-memory (lost when app restarts)
memory = InMemory()

# Production: Redis (persistent across restarts)
memory = RedisMemory(url="redis://localhost:6379")
```

---

## 7. Multiple Tools

Agents can have many tools. The LLM decides which to use (and can use multiple in sequence):

```python
tools = ActionGroup(name="ResearchTools")

@tools.action(name="search_web", description="Search the web for information")
async def search_web(query: str) -> list:
    # Your implementation
    return [{"title": "Result 1", "snippet": "..."}]

@tools.action(name="get_page", description="Fetch content from a URL")
async def get_page(url: str) -> str:
    # Your implementation
    return "<html>...</html>"

@tools.action(name="summarize", description="Summarize long text")
async def summarize(text: str, max_words: int = 100) -> str:
    # Your implementation
    return "Summary..."

agent = Agent(
    name="Researcher",
    instruction="""You help users research topics.
    1. Search for relevant information
    2. Fetch pages if needed
    3. Summarize findings""",
    model_client=AnthropicClient(),
)
agent.add_action_group(tools)
```

**Tool calls run in parallel!** If the LLM requests multiple tools at once, Bedsheet executes them concurrently:

```python
# LLM might request:
# - search_web("Python tutorials")
# - search_web("Python best practices")
# Both run at the same time, not one after another!
```

---

## 8. Your First Multi-Agent System

Now let's coordinate multiple agents. A **Supervisor** can delegate tasks to specialized agents:

```python
from bedsheet import Agent, Supervisor, ActionGroup
from bedsheet.llm import AnthropicClient
from bedsheet.memory import InMemory
from bedsheet.events import (
    CompletionEvent, DelegationEvent,
    CollaboratorStartEvent, CollaboratorCompleteEvent
)

# === Agent 1: Translator ===
translator = Agent(
    name="Translator",
    instruction="You translate text between languages. Always respond with just the translation.",
    model_client=AnthropicClient(),
)

# === Agent 2: Summarizer ===
summarizer = Agent(
    name="Summarizer",
    instruction="You summarize text concisely. Always respond with just the summary.",
    model_client=AnthropicClient(),
)

# === Supervisor: Coordinator ===
coordinator = Supervisor(
    name="Coordinator",
    instruction="""You coordinate text processing tasks.

    You have two collaborators:
    - Translator: For translation tasks
    - Summarizer: For summarization tasks

    When a user asks for help, delegate to the appropriate agent.
    After receiving their response, provide it to the user.""",
    model_client=AnthropicClient(),
    memory=InMemory(),
    collaborators=[translator, summarizer],
    collaboration_mode="supervisor",
)

async def main():
    async for event in coordinator.invoke("session-1", "Translate 'Hello world' to Spanish"):
        if isinstance(event, DelegationEvent):
            agents = [d["agent_name"] for d in event.delegations]
            print(f"Delegating to: {agents}")

        elif isinstance(event, CollaboratorStartEvent):
            print(f"  [{event.agent_name}] Starting...")

        elif isinstance(event, CollaboratorCompleteEvent):
            print(f"  [{event.agent_name}] Done")

        elif isinstance(event, CompletionEvent):
            print(f"\nFinal: {event.response}")

asyncio.run(main())
```

**Output:**
```
Delegating to: ['Translator']
  [Translator] Starting...
  [Translator] Done

Final: The Spanish translation of "Hello world" is "Hola mundo".
```

**What's happening:**

1. User asks for a translation
2. Coordinator (Supervisor) recognizes this needs the Translator
3. It delegates the task using a built-in `delegate` tool
4. Translator processes the request and returns a response
5. Coordinator synthesizes and presents the final answer

---

## 9. Parallel Delegation

The real power of multi-agent systems: running agents **simultaneously**.

```python
# === Two Research Agents ===
market_analyst = Agent(
    name="MarketAnalyst",
    instruction="You analyze stock market data and trends.",
    model_client=AnthropicClient(),
)
# (add tools for market data)

news_researcher = Agent(
    name="NewsResearcher",
    instruction="You research recent news and analyze sentiment.",
    model_client=AnthropicClient(),
)
# (add tools for news)

# === Supervisor with Parallel Delegation ===
advisor = Supervisor(
    name="InvestmentAdvisor",
    instruction="""You coordinate investment research.

    For stock analysis, delegate to BOTH agents IN PARALLEL:

    delegate(delegations=[
        {"agent_name": "MarketAnalyst", "task": "Analyze [SYMBOL] price and technicals"},
        {"agent_name": "NewsResearcher", "task": "Find news about [COMPANY]"}
    ])

    Then synthesize their findings into a comprehensive report.""",
    model_client=AnthropicClient(),
    memory=InMemory(),
    collaborators=[market_analyst, news_researcher],
    collaboration_mode="supervisor",
)
```

**With parallel delegation:**
```
Time: 0s    [MarketAnalyst] Starting...
Time: 0s    [NewsResearcher] Starting...    <- Both start together!
Time: 2s    [MarketAnalyst] Complete
Time: 2s    [NewsResearcher] Complete
Time: 3s    [Supervisor] Synthesizes response
Total: 3 seconds
```

**Without parallel delegation:**
```
Time: 0s    [MarketAnalyst] Starting...
Time: 2s    [MarketAnalyst] Complete
Time: 2s    [NewsResearcher] Starting...    <- Waits for first to finish
Time: 4s    [NewsResearcher] Complete
Time: 5s    [Supervisor] Synthesizes response
Total: 5 seconds
```

---

## 10. Deep Agent Hierarchies

Supervisors can contain other Supervisors, creating deep hierarchies:

```python
# Level 3: Specialist agents
code_writer = Agent(name="CodeWriter", instruction="Write code.", ...)
code_reviewer = Agent(name="CodeReviewer", instruction="Review code.", ...)
test_writer = Agent(name="TestWriter", instruction="Write tests.", ...)

# Level 2: Team leads (Supervisors containing agents)
dev_lead = Supervisor(
    name="DevLead",
    instruction="Coordinate code writing and review.",
    collaborators=[code_writer, code_reviewer],
    collaboration_mode="supervisor",
    ...
)

qa_lead = Supervisor(
    name="QALead",
    instruction="Coordinate testing efforts.",
    collaborators=[test_writer],
    collaboration_mode="supervisor",
    ...
)

# Level 1: Project manager (Supervisor containing supervisors!)
project_manager = Supervisor(
    name="ProjectManager",
    instruction="""You manage software projects.

    For new features:
    1. Delegate to DevLead for implementation
    2. Delegate to QALead for testing

    Ensure quality before marking complete.""",
    collaborators=[dev_lead, qa_lead],  # Other supervisors!
    collaboration_mode="supervisor",
    ...
)
```

**Hierarchy:**
```
ProjectManager (Supervisor)
├── DevLead (Supervisor)
│   ├── CodeWriter (Agent)
│   └── CodeReviewer (Agent)
└── QALead (Supervisor)
    └── TestWriter (Agent)
```

When you invoke `project_manager`:
1. ProjectManager might delegate to DevLead
2. DevLead might delegate to CodeWriter and CodeReviewer
3. Results bubble up through the hierarchy
4. Each supervisor synthesizes its collaborators' outputs

**Events are nested!** You'll see `CollaboratorEvent` wrapping `CollaboratorEvent` for deep hierarchies:

```python
async for event in project_manager.invoke(session_id, task):
    if isinstance(event, CollaboratorEvent):
        print(f"[{event.agent_name}]")
        inner = event.inner_event

        if isinstance(inner, CollaboratorEvent):
            # This is a nested collaborator (DevLead's agents)
            print(f"  [{inner.agent_name}] {inner.inner_event}")
```

---

## 11. Router Mode

Sometimes you don't need synthesis - you just want to route to the right specialist:

```python
# Create specialists
python_expert = Agent(name="PythonExpert", instruction="Answer Python questions.", ...)
javascript_expert = Agent(name="JavaScriptExpert", instruction="Answer JS questions.", ...)
database_expert = Agent(name="DatabaseExpert", instruction="Answer database questions.", ...)

# Router just picks one and hands off
help_desk = Supervisor(
    name="HelpDesk",
    instruction="""Route programming questions to the right expert:
    - Python questions -> PythonExpert
    - JavaScript questions -> JavaScriptExpert
    - Database questions -> DatabaseExpert

    Pick ONE expert that best matches the question.""",
    collaborators=[python_expert, javascript_expert, database_expert],
    collaboration_mode="router",  # Just route, don't synthesize
    ...
)
```

**Supervisor mode** (default):
- Orchestrates multiple agents
- Synthesizes their responses
- Good for complex tasks needing coordination

**Router mode**:
- Picks one agent
- Passes through that agent's response directly
- Good for simple routing/triage

---

## 12. Best Practices

### Agent Design

1. **Single Responsibility**: Each agent should do one thing well
   ```python
   # Good: Focused agents
   code_writer = Agent(name="CodeWriter", instruction="Write Python code.")
   code_reviewer = Agent(name="CodeReviewer", instruction="Review code for bugs.")

   # Bad: One agent trying to do everything
   do_everything = Agent(name="DoEverything", instruction="Write, review, test, deploy...")
   ```

2. **Clear Instructions**: Be specific about what the agent should do
   ```python
   # Good: Clear, specific instructions
   instruction = """You summarize text.
   - Keep summaries under 100 words
   - Focus on key points
   - Use bullet points for clarity"""

   # Bad: Vague instructions
   instruction = "Help with text stuff"
   ```

3. **Tool Descriptions Matter**: The LLM uses these to decide when to call tools
   ```python
   # Good: Clear description
   @tools.action(name="get_weather", description="Get current weather for a city. Returns temperature and conditions.")

   # Bad: Vague description
   @tools.action(name="get_weather", description="Weather stuff")
   ```

### Multi-Agent Design

4. **Use Parallel Delegation**: When tasks are independent, run them together
   ```python
   # Good: Parallel for independent tasks
   instruction = """Delegate to BOTH analysts simultaneously:
   delegate(delegations=[...])"""

   # Less efficient: Sequential for independent tasks
   instruction = """First delegate to Analyst1, then to Analyst2..."""
   ```

5. **Gate Expensive Operations**: Check prerequisites first
   ```python
   instruction = """
   1. FIRST: Check ethics/permissions
   2. ONLY IF APPROVED: Do the expensive research
   3. Synthesize results"""
   ```

6. **Let Supervisors Synthesize**: Don't just concatenate
   ```python
   # Good: Supervisor creates unified response
   instruction = """Synthesize findings into a comprehensive report with:
   - Executive summary
   - Key data points
   - Recommendations"""

   # Bad: Just concatenating
   instruction = "Return what each agent said"
   ```

### Error Handling

7. **Tools Should Return Errors Gracefully**:
   ```python
   @tools.action(name="get_data", description="Fetch data")
   async def get_data(id: str) -> dict:
       try:
           return await fetch(id)
       except NotFoundError:
           return {"error": f"No data found for id: {id}"}
       except Exception as e:
           return {"error": f"Failed to fetch: {str(e)}"}
   ```

8. **Set Appropriate Limits**:
   ```python
   supervisor = Supervisor(
       ...,
       max_iterations=10,  # Prevent runaway loops
   )
   ```

### Production Readiness

9. **Use Redis Memory for Production**:
   ```python
   from bedsheet.memory import RedisMemory

   memory = RedisMemory(url="redis://your-redis:6379")
   ```

10. **Log Events for Observability**:
    ```python
    async for event in agent.invoke(...):
        logger.info(f"Event: {event.type}", extra={"event": event})
        # ... handle event
    ```

---

## Next Steps

- **[Multi-Agent Guide](multi-agent-guide.md)**: Deep dive into supervisor patterns
- **[Technical Guide](technical-guide.html)**: Understand the Python patterns used
- **Run the demo**: `uvx bedsheet demo` to see everything in action

---

**Questions?** Open an issue at [github.com/sivang/bedsheet](https://github.com/sivang/bedsheet)
