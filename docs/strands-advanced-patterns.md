# Strands Advanced Patterns Explained

## Part 1: Orchestration Styles

### ReAct Loop (What Bedsheet Already Has)

**ReAct = Reasoning + Acting**

The standard agent loop where the LLM:
1. **Reads** context (conversation history, tool results)
2. **Reasons** about what to do next
3. **Acts** by calling a tool OR responding
4. **Observes** the result
5. **Repeats** until task is complete

```
User: "What's the weather in Tokyo?"
    │
    ▼
┌─────────────────────────────────┐
│  LLM THINKS: I need weather     │
│  data. I'll use get_weather()   │
│                                 │
│  ACTION: get_weather("Tokyo")   │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  TOOL RESULT: 22°C, sunny       │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  LLM THINKS: I have the data.   │
│  I can now respond.             │
│                                 │
│  RESPONSE: "Tokyo is 22°C..."   │
└─────────────────────────────────┘
```

**Limitation:** Each step waits for tool results before planning the next step.

---

### ReWOO (Reasoning Without Observation)

**ReWOO = Plan First, Execute Later, Synthesize at End**

Instead of interleaving reasoning and observation, ReWOO separates them into three distinct phases:

```
┌─────────────────────────────────────────────────────────┐
│  PHASE 1: PLANNING (No tool execution)                  │
│                                                         │
│  LLM creates a complete plan upfront:                   │
│                                                         │
│  Plan:                                                  │
│  1. Get weather for Tokyo → store as $weather           │
│  2. Get currency rate JPY→USD → store as $rate          │
│  3. Get flight prices → store as $flights               │
│  4. Synthesize travel recommendation using $1, $2, $3   │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  PHASE 2: EXECUTION (Run all tools)                     │
│                                                         │
│  Execute plan steps (can be parallelized):              │
│  • get_weather("Tokyo") → $weather = "22°C sunny"       │
│  • get_currency("JPY", "USD") → $rate = "0.0067"        │
│  • get_flights("Tokyo") → $flights = "$800 round trip"  │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  PHASE 3: SYNTHESIS (Combine results)                   │
│                                                         │
│  LLM receives all results and produces final answer:    │
│  "Tokyo trip: Great weather (22°C), flights $800..."    │
└─────────────────────────────────────────────────────────┘
```

**Advantages:**
- Fewer LLM calls (plan once, execute all, synthesize once)
- Tools can run in parallel during execution phase
- Better for complex multi-step tasks

**Disadvantages:**
- Can't adapt plan based on intermediate results
- If step 2 fails, the whole plan may be invalid

---

### Reflexion (Iterative Self-Improvement)

**Reflexion = Try → Critique → Improve → Repeat**

The agent attempts a task, then reflects on its own output to improve it:

```
┌─────────────────────────────────────────────────────────┐
│  ATTEMPT 1                                              │
│                                                         │
│  Task: "Write a function to validate email addresses"  │
│                                                         │
│  Output:                                                │
│  def validate(email):                                   │
│      return "@" in email                                │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  REFLECTION (Self-Critique)                             │
│                                                         │
│  "My solution is too simple. It would accept           │
│   'a@b' which isn't a valid email. I should check:     │
│   - Domain has a dot                                    │
│   - Local part isn't empty                              │
│   - Use regex for proper validation"                    │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  ATTEMPT 2 (Improved)                                   │
│                                                         │
│  import re                                              │
│  def validate(email):                                   │
│      pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.   │
│                  [a-zA-Z]{2,}$'                         │
│      return bool(re.match(pattern, email))              │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  REFLECTION (Satisfied)                                 │
│                                                         │
│  "This handles common cases well. I could add more     │
│   edge cases but this is good for the requirement."     │
│                                                         │
│  → DONE                                                 │
└─────────────────────────────────────────────────────────┘
```

**Use Cases:**
- Code generation with self-review
- Writing tasks with revision
- Problem-solving with verification

---

### Autonomous Loops

**Autonomous = Keep Going Until Done (No Human in Loop)**

The agent runs indefinitely without requiring human input between steps:

```
┌─────────────────────────────────────────────────────────┐
│  TASK: "Monitor the API and fix any issues"            │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  AUTONOMOUS LOOP                                        │
│                                                         │
│  while not done:                                        │
│      status = check_api_health()                        │
│      if status.has_errors:                              │
│          diagnosis = analyze_logs()                     │
│          fix = generate_fix(diagnosis)                  │
│          apply_fix(fix)                                 │
│          verify = test_api()                            │
│          if verify.passed:                              │
│              log("Fixed: " + diagnosis)                 │
│          else:                                          │
│              escalate_to_human()                        │
│      sleep(60)  # Check again in 1 minute               │
└─────────────────────────────────────────────────────────┘
```

**Features:**
- Extended chain-of-thought reasoning
- Multi-step workflows without human intervention
- Self-correction and retry logic
- Can run for hours or days

**Use Cases:**
- DevOps monitoring and remediation
- Data pipeline management
- Research tasks requiring many iterations

---

## Part 2: Multi-Agent Patterns

### Pattern 1: Agents-as-Tools (What Bedsheet's Supervisor Does)

**Hierarchical Delegation**

One "orchestrator" agent treats other agents as tools it can call:

```
                    ┌─────────────────┐
                    │   ORCHESTRATOR  │
                    │    (Supervisor) │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │  RESEARCHER  │ │   ANALYST    │ │    WRITER    │
    │    Agent     │ │    Agent     │ │    Agent     │
    └──────────────┘ └──────────────┘ └──────────────┘
```

**Flow:**
1. User asks: "Write a report on AI trends"
2. Orchestrator delegates: "Researcher, find recent AI papers"
3. Orchestrator delegates: "Analyst, analyze the findings"
4. Orchestrator delegates: "Writer, create the report"
5. Orchestrator synthesizes and returns final result

**Bedsheet equivalent:** `Supervisor` class with `collaborators`

---

### Pattern 2: Swarms (Peer-to-Peer Collaboration)

**No Central Controller**

Agents work as equals, passing tasks directly to each other:

```
    ┌──────────────┐         ┌──────────────┐
    │   AGENT A    │◄───────►│   AGENT B    │
    │  (Research)  │         │  (Analysis)  │
    └──────┬───────┘         └───────┬──────┘
           │                         │
           │    ┌──────────────┐     │
           └───►│   AGENT C    │◄────┘
                │   (Writing)  │
                └──────────────┘
```

**How it works:**
1. Agent A starts working on research
2. Agent A realizes it needs analysis → hands off to Agent B
3. Agent B completes analysis → hands off to Agent C
4. Agent C writes the report
5. Any agent can hand off to any other agent

**Key difference from Supervisor:**
- No central orchestrator deciding who does what
- Agents autonomously decide when to hand off
- More flexible but less predictable

**Use Cases:**
- Creative collaboration (brainstorming)
- Emergent problem-solving
- Tasks where optimal workflow isn't known upfront

---

### Pattern 3: Agent Graphs (DAG-Based Orchestration)

**Directed Acyclic Graph with Explicit Dependencies**

Define agents as nodes and their dependencies as edges:

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ AGENT A  │ │ AGENT B  │ │ AGENT C  │
        │ (Fetch)  │ │ (Fetch)  │ │ (Fetch)  │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │            │            │
             └────────────┼────────────┘
                          │
                          ▼
                    ┌──────────┐
                    │ AGENT D  │
                    │ (Merge)  │
                    └────┬─────┘
                         │
            ┌────────────┴────────────┐
            │                         │
            ▼                         ▼
      ┌──────────┐              ┌──────────┐
      │ AGENT E  │              │ AGENT F  │
      │(Analyze) │              │ (Format) │
      └────┬─────┘              └────┬─────┘
           │                         │
           └────────────┬────────────┘
                        │
                        ▼
                  ┌──────────┐
                  │   END    │
                  └──────────┘
```

**Graph Types:**

1. **Sequential Pipeline:**
   ```
   A → B → C → D (quality control, each step validates previous)
   ```

2. **Parallel Processing:**
   ```
   A ─┬─► B ─┬─► E
      │      │
      └─► C ─┘
      │
      └─► D ──────► F
   ```

3. **Conditional Branching:**
   ```
   A → [if condition] → B
                    └─► C
   ```

**Use Cases:**
- ETL pipelines
- Document processing workflows
- Multi-stage approval processes

---

### Pattern 4: Agent Workflows (Task DAGs)

**Pre-defined Task Sequences Executed as Single Tools**

Unlike Agent Graphs (which are about agent orchestration), Workflows are about **task orchestration**:

```
┌─────────────────────────────────────────────────────────┐
│  WORKFLOW: "process_customer_order"                     │
│                                                         │
│  ┌─────────────┐     ┌─────────────┐     ┌───────────┐ │
│  │ Validate    │────►│ Check       │────►│ Process   │ │
│  │ Payment     │     │ Inventory   │     │ Shipping  │ │
│  └─────────────┘     └─────────────┘     └───────────┘ │
│         │                   │                   │       │
│         ▼                   ▼                   ▼       │
│  ┌─────────────┐     ┌─────────────┐     ┌───────────┐ │
│  │ Fraud       │     │ Reserve     │     │ Send      │ │
│  │ Check       │     │ Stock       │     │ Email     │ │
│  └─────────────┘     └─────────────┘     └───────────┘ │
└─────────────────────────────────────────────────────────┘
                         │
                         │  Exposed as single tool
                         ▼
┌─────────────────────────────────────────────────────────┐
│  AGENT                                                  │
│                                                         │
│  "Process order #12345"                                 │
│       │                                                 │
│       └──► process_customer_order(order_id="12345")     │
│                      │                                  │
│                      └──► (entire workflow executes)    │
└─────────────────────────────────────────────────────────┘
```

**Key Characteristics:**
- Deterministic execution (same input = same steps)
- Non-conversational (runs to completion)
- Parallel task processing where dependencies allow
- Repeatable business processes

**Use Cases:**
- Order processing
- Onboarding workflows
- Compliance checks
- Report generation pipelines

---

### Pattern 5: Agent-to-Agent Protocol (A2A)

**Standardized Communication Between Agents**

A protocol for agents to discover, communicate, and collaborate:

```
┌─────────────────────────────────────────────────────────┐
│  A2A PROTOCOL                                           │
│                                                         │
│  1. DISCOVERY                                           │
│     Agent A: "Who can help with data analysis?"         │
│     Registry: "Agent B (stats), Agent C (ML)"           │
│                                                         │
│  2. CAPABILITY NEGOTIATION                              │
│     Agent A: "Can you handle time-series data?"         │
│     Agent B: "Yes, I support ARIMA, Prophet, LSTM"      │
│                                                         │
│  3. TASK HANDOFF                                        │
│     Agent A: {                                          │
│       "task": "analyze_trends",                         │
│       "data": [...],                                    │
│       "context": "Looking for seasonality"              │
│     }                                                   │
│                                                         │
│  4. RESULT RETURN                                       │
│     Agent B: {                                          │
│       "result": {...},                                  │
│       "confidence": 0.95,                               │
│       "suggestions": ["Try weekly aggregation"]         │
│     }                                                   │
└─────────────────────────────────────────────────────────┘
```

**Benefits:**
- Agents from different systems can collaborate
- Standard message format for interoperability
- Built-in capability discovery
- Works across network boundaries

---

## Summary Comparison

| Pattern | Control | Flexibility | Predictability | Use Case |
|---------|---------|-------------|----------------|----------|
| **Agents-as-Tools** | Centralized | Low | High | Clear delegation |
| **Swarms** | Decentralized | High | Low | Creative tasks |
| **Agent Graphs** | Declarative | Medium | High | Pipelines |
| **Workflows** | Deterministic | Low | Very High | Business processes |
| **A2A Protocol** | Distributed | High | Medium | Cross-system |

---

## What Bedsheet Currently Supports

| Pattern | Bedsheet | How |
|---------|----------|-----|
| ReAct | ✅ | `Agent.invoke()` loop |
| Agents-as-Tools | ✅ | `Supervisor` class |
| Router | ✅ | `Supervisor(collaboration="router")` |
| Parallel Execution | ✅ | `asyncio.gather()` for tools |

## What Bedsheet Could Add

| Pattern | Complexity | Value |
|---------|------------|-------|
| ReWOO | Medium | Efficiency for multi-step tasks |
| Reflexion | Medium | Better code/content generation |
| Autonomous Loops | Low | Long-running agents |
| Swarms | High | Emergent collaboration |
| Agent Graphs | High | Pipeline orchestration |
| Workflows | Medium | Business process automation |
| A2A Protocol | High | Cross-system interop |
