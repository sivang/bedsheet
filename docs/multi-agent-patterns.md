# Multi-Agent Patterns with Bedsheet

This guide shows how to implement common multi-agent orchestration patterns using Bedsheet's existing constructs. No additional features required - just creative use of `Supervisor`, `Agent`, `@action`, and `asyncio`.

## Pattern Overview

| Pattern | What It Does | Bedsheet Implementation |
|---------|--------------|------------------------|
| **Agents-as-Tools** | Central orchestrator delegates to specialists | `Supervisor` with `collaborators` |
| **Swarms** | Peer agents hand off to each other | Agents with cross-agent `@action` tools |
| **Agent Graphs** | DAG-based pipeline with dependencies | `asyncio.gather()` + sequential phases |
| **Workflows** | Pre-defined task sequence as single tool | `@action` wrapping agent pipeline |
| **A2A Protocol** | Dynamic agent discovery and routing | Registry + Router `Supervisor` |

---

## Pattern 1: Agents-as-Tools (Hierarchical Delegation)

**Use when:** You have a clear orchestrator that decides which specialists to consult.

This is Bedsheet's native `Supervisor` pattern:

```python
from bedsheet import Agent, Supervisor, ActionGroup
from bedsheet.llm import AnthropicClient

client = AnthropicClient()

# Create specialist agents
researcher = Agent(
    name="Researcher",
    instruction="Find and summarize information on topics",
    model_client=client,
)

analyst = Agent(
    name="Analyst",
    instruction="Analyze data and provide insights",
    model_client=client,
)

writer = Agent(
    name="Writer",
    instruction="Write clear, engaging content",
    model_client=client,
)

# Create orchestrating supervisor
orchestrator = Supervisor(
    name="ContentTeam",
    instruction="""You coordinate a content team.
    - Use Researcher for gathering information
    - Use Analyst for data interpretation
    - Use Writer for final content creation
    Delegate tasks appropriately and synthesize results.""",
    model_client=client,
    collaborators=[researcher, analyst, writer],
    collaboration="supervisor",  # Parallel delegation
)

# Run
async for event in orchestrator.invoke("session-1", "Write an article about AI trends"):
    print(event)
```

---

## Pattern 2: Swarms (Peer-to-Peer Collaboration)

**Use when:** Agents should autonomously decide when to hand off to peers, with no central controller.

```python
from bedsheet import Agent, ActionGroup
from bedsheet.events import CompletionEvent

client = AnthropicClient()

# Create agents that will form a swarm
researcher = Agent(
    name="Researcher",
    instruction="Research topics. Hand off to Analyst when you have data.",
    model_client=client,
)

analyst = Agent(
    name="Analyst",
    instruction="Analyze data. Hand off to Writer when insights are ready.",
    model_client=client,
)

writer = Agent(
    name="Writer",
    instruction="Write final content based on analysis.",
    model_client=client,
)

# Give each agent the ability to hand off to others
async def create_handoff_action(from_agent: Agent, to_agent: Agent):
    """Create a handoff tool from one agent to another."""

    @from_agent.default_action_group.action(
        name=f"handoff_to_{to_agent.name.lower()}",
        description=f"Hand off work to {to_agent.name} with context"
    )
    async def handoff(context: str, task: str) -> str:
        """Hand off to the next agent with context."""
        message = f"Context from {from_agent.name}:\n{context}\n\nTask: {task}"
        result = ""
        async for event in to_agent.invoke(f"swarm-session", message):
            if isinstance(event, CompletionEvent):
                result = event.text
        return result

# Wire up the swarm connections
await create_handoff_action(researcher, analyst)
await create_handoff_action(analyst, writer)
await create_handoff_action(writer, researcher)  # Can loop back if needed

# Start the swarm with the researcher
async for event in researcher.invoke(
    "swarm-session",
    "Research AI trends, analyze the findings, and write a summary"
):
    print(event)
```

**Key insight:** Each agent has `@action` tools to invoke other agents. The LLM decides when to hand off based on its instruction.

---

## Pattern 3: Agent Graphs (DAG-Based Pipelines)

**Use when:** You have explicit dependencies between processing stages.

```python
import asyncio
from bedsheet import Agent
from bedsheet.events import CompletionEvent

client = AnthropicClient()

# Define pipeline stages as agents
fetcher_a = Agent(name="FetcherA", instruction="Fetch data from source A", model_client=client)
fetcher_b = Agent(name="FetcherB", instruction="Fetch data from source B", model_client=client)
fetcher_c = Agent(name="FetcherC", instruction="Fetch data from source C", model_client=client)
merger = Agent(name="Merger", instruction="Merge multiple data sources", model_client=client)
analyzer = Agent(name="Analyzer", instruction="Analyze merged data", model_client=client)
formatter = Agent(name="Formatter", instruction="Format results for output", model_client=client)

async def get_result(agent: Agent, session_id: str, message: str) -> str:
    """Helper to get final text from an agent."""
    async for event in agent.invoke(session_id, message):
        if isinstance(event, CompletionEvent):
            return event.text
    return ""

async def run_pipeline(query: str) -> str:
    """
    Pipeline graph:

        FetcherA ─┐
        FetcherB ─┼─► Merger ─┬─► Analyzer ─► (output)
        FetcherC ─┘           │
                              └─► Formatter ─► (output)
    """
    session = "pipeline-session"

    # Phase 1: Parallel fetching (no dependencies)
    fetch_results = await asyncio.gather(
        get_result(fetcher_a, session, f"Fetch source A data for: {query}"),
        get_result(fetcher_b, session, f"Fetch source B data for: {query}"),
        get_result(fetcher_c, session, f"Fetch source C data for: {query}"),
    )

    # Phase 2: Merge (depends on all fetchers)
    merged = await get_result(
        merger, session,
        f"Merge these data sources:\n" + "\n---\n".join(fetch_results)
    )

    # Phase 3: Parallel processing (both depend on merger)
    analysis, formatted = await asyncio.gather(
        get_result(analyzer, session, f"Analyze: {merged}"),
        get_result(formatter, session, f"Format for display: {merged}"),
    )

    return f"Analysis:\n{analysis}\n\nFormatted:\n{formatted}"

# Run the pipeline
result = await run_pipeline("quarterly sales data")
print(result)
```

**Key insight:** Use `asyncio.gather()` for parallel stages, sequential `await` for dependencies.

---

## Pattern 4: Workflows (Task DAGs as Tools)

**Use when:** You have repeatable multi-step processes that should be exposed as a single operation.

```python
from bedsheet import Agent, ActionGroup
from bedsheet.events import CompletionEvent

client = AnthropicClient()

# Create workflow step agents
validator = Agent(name="Validator", instruction="Validate order data", model_client=client)
inventory_checker = Agent(name="InventoryChecker", instruction="Check stock levels", model_client=client)
payment_processor = Agent(name="PaymentProcessor", instruction="Process payments", model_client=client)
shipper = Agent(name="Shipper", instruction="Arrange shipping", model_client=client)
notifier = Agent(name="Notifier", instruction="Send customer notifications", model_client=client)

# Main agent that uses the workflow
order_agent = Agent(
    name="OrderManager",
    instruction="Process customer orders using the process_order workflow",
    model_client=client,
)

order_group = ActionGroup(name="Orders", description="Order processing tools")

@order_group.action(
    name="process_order",
    description="Complete order processing workflow: validate → check inventory → process payment → ship → notify"
)
async def process_order(order_id: str, customer_email: str, items: str) -> dict:
    """Execute the full order processing workflow."""
    session = f"order-{order_id}"

    async def run_step(agent: Agent, message: str) -> str:
        async for event in agent.invoke(session, message):
            if isinstance(event, CompletionEvent):
                return event.text
        return ""

    # Step 1: Validate
    validation = await run_step(
        validator,
        f"Validate order {order_id}: items={items}, email={customer_email}"
    )
    if "invalid" in validation.lower():
        return {"status": "failed", "step": "validation", "message": validation}

    # Step 2: Check inventory
    inventory = await run_step(
        inventory_checker,
        f"Check stock for order {order_id}: {items}"
    )
    if "out of stock" in inventory.lower():
        return {"status": "failed", "step": "inventory", "message": inventory}

    # Step 3: Process payment
    payment = await run_step(
        payment_processor,
        f"Process payment for order {order_id}"
    )

    # Step 4: Arrange shipping
    shipping = await run_step(
        shipper,
        f"Ship order {order_id} to customer"
    )

    # Step 5: Notify customer
    notification = await run_step(
        notifier,
        f"Send confirmation to {customer_email} for order {order_id}"
    )

    return {
        "status": "completed",
        "order_id": order_id,
        "steps": {
            "validation": validation,
            "inventory": inventory,
            "payment": payment,
            "shipping": shipping,
            "notification": notification,
        }
    }

order_agent.add_action_group(order_group)

# Now the agent can use the workflow as a single tool
async for event in order_agent.invoke(
    "session-1",
    "Process order #12345 for customer@example.com with items: Widget x2, Gadget x1"
):
    print(event)
```

**Key insight:** Wrap the entire multi-agent pipeline in a single `@action`, exposing it as one tool to the outer agent.

---

## Pattern 5: A2A Protocol (Dynamic Agent Discovery)

**Use when:** Agents need to discover and route to other agents based on capabilities at runtime.

```python
from bedsheet import Agent, Supervisor, ActionGroup
from bedsheet.events import CompletionEvent
from dataclasses import dataclass

client = AnthropicClient()

@dataclass
class AgentCapability:
    agent: Agent
    capabilities: list[str]
    description: str

class AgentRegistry:
    """Registry for agent discovery."""

    def __init__(self):
        self.agents: dict[str, AgentCapability] = {}

    def register(self, agent: Agent, capabilities: list[str], description: str):
        self.agents[agent.name] = AgentCapability(agent, capabilities, description)

    def find_by_capability(self, capability: str) -> Agent | None:
        for entry in self.agents.values():
            if capability in entry.capabilities:
                return entry.agent
        return None

    def list_capabilities(self) -> str:
        lines = []
        for name, entry in self.agents.items():
            lines.append(f"- {name}: {', '.join(entry.capabilities)} - {entry.description}")
        return "\n".join(lines)

# Create the registry
registry = AgentRegistry()

# Register agents with capabilities
math_agent = Agent(name="MathExpert", instruction="Solve math problems", model_client=client)
registry.register(math_agent, ["math", "calculation", "statistics"], "Mathematical computations")

code_agent = Agent(name="CodeExpert", instruction="Write and debug code", model_client=client)
registry.register(code_agent, ["coding", "debugging", "python", "javascript"], "Software development")

data_agent = Agent(name="DataExpert", instruction="Analyze and visualize data", model_client=client)
registry.register(data_agent, ["data-analysis", "visualization", "sql"], "Data science")

# Create a router that uses the registry
router = Agent(
    name="Router",
    instruction=f"""You are a task router. Route requests to the appropriate expert.

Available experts:
{registry.list_capabilities()}

Use the route_to_expert tool to delegate tasks.""",
    model_client=client,
)

router_group = ActionGroup(name="Routing", description="Route to experts")

@router_group.action(
    name="route_to_expert",
    description="Route a task to an expert based on required capability"
)
async def route_to_expert(capability: str, task: str) -> str:
    """Find an agent with the capability and delegate the task."""
    agent = registry.find_by_capability(capability)
    if not agent:
        return f"No agent found with capability: {capability}"

    result = ""
    async for event in agent.invoke(f"routed-{capability}", task):
        if isinstance(event, CompletionEvent):
            result = event.text
    return f"[{agent.name}]: {result}"

@router_group.action(
    name="list_available_experts",
    description="List all available experts and their capabilities"
)
async def list_available_experts() -> str:
    return registry.list_capabilities()

router.add_action_group(router_group)

# The router dynamically discovers and delegates
async for event in router.invoke(
    "session-1",
    "Calculate the standard deviation of [1,2,3,4,5] and then write Python code to verify it"
):
    print(event)
```

**Key insight:** Use a registry pattern with capability tags. The router agent discovers agents at runtime.

---

## Combining Patterns

These patterns can be combined. For example:

- **Supervisor + Workflows:** A supervisor delegates to agents, some of which execute internal workflows
- **Swarm + A2A:** Swarm agents use a registry to discover peers dynamically
- **Graph + Workflows:** A pipeline where some nodes are entire workflows

```python
# Example: Supervisor with workflow-wrapped specialists
supervisor = Supervisor(
    name="TeamLead",
    instruction="Coordinate the team",
    model_client=client,
    collaborators=[
        order_agent,      # Has process_order workflow tool
        data_agent,       # Has analyze_data workflow tool
        report_agent,     # Has generate_report workflow tool
    ],
)
```

---

## Best Practices

1. **Start simple:** Use `Supervisor` first. Add complexity only when needed.

2. **Clear handoff context:** When agents hand off, include full context so the next agent doesn't need to ask questions.

3. **Session management:** Use consistent `session_id` patterns:
   - `f"{workflow}-{step}"` for pipelines
   - `f"{parent}-{child}"` for hierarchies
   - Unique IDs for independent work

4. **Error handling:** Wrap agent invocations in try/except and return meaningful error messages.

5. **Logging:** Emit custom events or use print statements to trace multi-agent flows during development.

---

## See Also

- [Multi-Agent Guide](multi-agent-guide.md) - Supervisor and Router patterns in depth
- [Technical Guide](technical-guide.html) - Core Bedsheet patterns
- [User Guide](user-guide.html) - Getting started with agents
