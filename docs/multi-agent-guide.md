# Multi-Agent Collaboration Guide

This guide walks through building a multi-agent assistant using Bedsheet's Supervisor pattern. We'll create an **AI Research Assistant** that demonstrates Bedsheet's key features:

- **Parallel Delegation**: Multiple agents working simultaneously
- **Rich Event Streaming**: Full visibility into every step of execution
- **Supervisor Synthesis**: Intelligent combination of multiple agent outputs
- **Error Recovery**: Graceful handling of agent failures

## The Example: Investment Research Assistant

We'll build an assistant that helps with investment research by coordinating three specialized agents:

1. **EthicsChecker** - Validates requests before processing
2. **MarketAnalyst** - Analyzes market data and trends
3. **NewsResearcher** - Gathers recent news and sentiment

The supervisor delegates to Market and News agents **in parallel**, dramatically reducing response time.

## Architecture

```
                         User: "Analyze NVIDIA stock"
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────┐
│                    InvestmentAdvisor                          │
│                      (Supervisor)                             │
│                                                               │
│   1. Check ethics                                             │
│   2. Delegate to Market + News IN PARALLEL                    │
│   3. Synthesize comprehensive analysis                        │
└───────────┬──────────────────┬──────────────────┬────────────┘
            │                  │                  │
            ▼                  │                  │
   ┌─────────────────┐         │                  │
   │  EthicsChecker  │         │                  │
   │  (Sequential)   │         │                  │
   └────────┬────────┘         │                  │
            │                  ▼                  ▼
            │         ┌─────────────────┐ ┌─────────────────┐
            │         │  MarketAnalyst  │ │  NewsResearcher │
            │         │   (Parallel)    │ │   (Parallel)    │
            │         └────────┬────────┘ └────────┬────────┘
            │                  │                   │
            ▼                  ▼                   ▼
┌───────────────────────────────────────────────────────────────┐
│              Synthesized Investment Analysis                   │
└───────────────────────────────────────────────────────────────┘
```

## Complete Example

> **Dependencies:** This example uses REAL data. Install with: `pip install bedsheet[demo]`
> (adds `yfinance` for Yahoo Finance stock data and `ddgs` for DuckDuckGo news search)

### Step 1: Define the Collaborator Agents

```python
import asyncio
from bedsheet import Agent, ActionGroup, Supervisor
from bedsheet.llm import AnthropicClient
from bedsheet.memory import InMemory
from bedsheet.events import (
    ToolCallEvent, ToolResultEvent, CompletionEvent, ErrorEvent,
    DelegationEvent, CollaboratorStartEvent, CollaboratorEvent,
    CollaboratorCompleteEvent, RoutingEvent
)


# ============================================================
# Ethics Checker Agent
# ============================================================

ethics_tools = ActionGroup(name="EthicsTools")


@ethics_tools.action(
    name="check_investment_request",
    description="Check if an investment request is appropriate"
)
async def check_investment_request(request: str) -> dict:
    """Check for inappropriate investment advice requests."""
    red_flags = ["insider", "manipulation", "pump and dump", "illegal"]
    request_lower = request.lower()

    for flag in red_flags:
        if flag in request_lower:
            return {
                "approved": False,
                "reason": f"Request may involve {flag}",
                "recommendation": "We cannot provide advice on potentially illegal activities."
            }

    return {
        "approved": True,
        "reason": "Request is appropriate for analysis",
        "recommendation": None
    }


ethics_agent = Agent(
    name="EthicsChecker",
    instruction="""You review investment-related requests for ethical concerns.
Use the check_investment_request tool and provide a clear verdict.
Be strict about insider trading, market manipulation, and illegal schemes.""",
    model_client=AnthropicClient(),
)
ethics_agent.add_action_group(ethics_tools)


# ============================================================
# Market Analyst Agent
# ============================================================

market_tools = ActionGroup(name="MarketTools")


@market_tools.action(
    name="get_stock_data",
    description="Get REAL current stock price and key metrics from Yahoo Finance"
)
async def get_stock_data(symbol: str) -> dict:
    """Fetch REAL stock data from Yahoo Finance."""
    import yfinance as yf

    ticker = yf.Ticker(symbol.upper())
    info = ticker.info
    fast = ticker.fast_info

    current_price = fast.last_price
    prev_close = fast.previous_close
    change = ((current_price - prev_close) / prev_close) * 100

    return {
        "symbol": symbol.upper(),
        "price": round(current_price, 2),
        "change": f"{change:+.2f}%",
        "pe_ratio": round(info.get("trailingPE", 0), 2) if info.get("trailingPE") else "N/A",
        "market_cap": f"${fast.market_cap/1e12:.2f}T" if fast.market_cap >= 1e12 else f"${fast.market_cap/1e9:.2f}B",
        "data_source": "Yahoo Finance (REAL DATA)",
    }


@market_tools.action(
    name="get_technical_analysis",
    description="Get REAL technical indicators calculated from historical price data"
)
async def get_technical_analysis(symbol: str) -> dict:
    """Calculate REAL technical indicators from Yahoo Finance historical data."""
    import yfinance as yf

    ticker = yf.Ticker(symbol.upper())
    hist = ticker.history(period="6mo")
    close = hist["Close"]

    # RSI (14-day)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi = 100 - (100 / (1 + gain / loss))

    # Moving averages and trend
    sma_20 = close.rolling(window=20).mean().iloc[-1]
    sma_50 = close.rolling(window=50).mean().iloc[-1]
    current_price = close.iloc[-1]

    if current_price > sma_20 > sma_50:
        trend = "strong uptrend"
    elif current_price > sma_20:
        trend = "uptrend"
    elif current_price < sma_20 < sma_50:
        trend = "strong downtrend"
    else:
        trend = "downtrend"

    return {
        "symbol": symbol.upper(),
        "rsi_14": round(rsi.iloc[-1], 2),
        "trend": trend,
        "sma_20": round(sma_20, 2),
        "sma_50": round(sma_50, 2),
        "support_30d": round(hist.tail(30)["Low"].min(), 2),
        "resistance_30d": round(hist.tail(30)["High"].max(), 2),
        "data_source": "Calculated from Yahoo Finance historical data (REAL DATA)",
    }


market_agent = Agent(
    name="MarketAnalyst",
    instruction="""You are a market analyst specializing in stock analysis.
Use get_stock_data to fetch REAL current stock data from Yahoo Finance.
Use get_technical_analysis to get REAL calculated technical indicators.
Provide clear, data-driven analysis with specific numbers.""",
    model_client=AnthropicClient(),
)
market_agent.add_action_group(market_tools)


# ============================================================
# News Researcher Agent
# ============================================================

news_tools = ActionGroup(name="NewsTools")


@news_tools.action(
    name="search_news",
    description="Search for REAL recent news about a company using DuckDuckGo"
)
async def search_news(query: str) -> dict:
    """Search REAL recent news using DuckDuckGo."""
    from ddgs import DDGS

    with DDGS() as ddgs:
        results = list(ddgs.news(query, max_results=5))

        articles = []
        for r in results:
            articles.append({
                "headline": r.get("title", ""),
                "source": r.get("source", ""),
                "date": r.get("date", ""),
                "body": r.get("body", "")[:150] + "..." if r.get("body") else "",
            })

        return {
            "query": query,
            "articles": articles,
            "count": len(articles),
            "data_source": "DuckDuckGo News (REAL DATA)",
        }


@news_tools.action(
    name="analyze_sentiment",
    description="Analyze overall sentiment from news articles"
)
async def analyze_sentiment(articles: list[dict]) -> dict:
    """Analyze sentiment from news articles."""
    if not articles:
        return {"sentiment": "neutral", "confidence": 0.0}

    sentiment_scores = {"positive": 1, "neutral": 0, "negative": -1}
    total = sum(sentiment_scores.get(a.get("sentiment", "neutral"), 0) for a in articles)
    avg = total / len(articles)

    if avg > 0.3:
        sentiment = "bullish"
    elif avg < -0.3:
        sentiment = "bearish"
    else:
        sentiment = "neutral"

    return {
        "sentiment": sentiment,
        "score": avg,
        "articles_analyzed": len(articles),
        "confidence": min(abs(avg) + 0.5, 1.0)
    }


news_agent = Agent(
    name="NewsResearcher",
    instruction="""You are a news researcher focused on financial news.
Use search_news to find REAL recent news articles via DuckDuckGo.
Use analyze_sentiment to analyze the overall sentiment.
Report key headlines with their sources.""",
    model_client=AnthropicClient(),
)
news_agent.add_action_group(news_tools)
```

### Step 2: Create the Supervisor

The supervisor coordinates all three agents:

```python
# ============================================================
# Investment Advisor Supervisor
# ============================================================

advisor = Supervisor(
    name="InvestmentAdvisor",
    instruction="""You are an investment research advisor that coordinates
specialized analysts to provide comprehensive stock analysis.

## Your Workflow

1. **Ethics Check First**: ALWAYS delegate to EthicsChecker first
   - If ethics check fails, stop and explain to the user
   - If it passes, proceed to research

2. **Parallel Research**: Delegate to BOTH analysts simultaneously:
   - MarketAnalyst: For price data and technical analysis
   - NewsResearcher: For recent news and sentiment

   Use parallel delegation like this:
   delegate(delegations=[
       {"agent_name": "MarketAnalyst", "task": "Analyze [SYMBOL] stock"},
       {"agent_name": "NewsResearcher", "task": "Find news about [COMPANY]"}
   ])

3. **Synthesize**: Combine findings into a comprehensive analysis:
   - Current price and key metrics
   - Technical outlook
   - News sentiment
   - Overall assessment (without specific buy/sell advice)

## Important
- Always check ethics BEFORE doing research
- Use parallel delegation for Market and News to save time
- Provide balanced analysis, not financial advice""",
    model_client=AnthropicClient(),
    memory=InMemory(),
    collaborators=[ethics_agent, market_agent, news_agent],
    collaboration_mode="supervisor",  # We want synthesis, not just routing
    max_iterations=15,
)
```

### Step 3: Rich Event Handling

This is where Bedsheet shines - full visibility into every step:

```python
async def run_with_rich_events():
    """Demonstrate rich event streaming."""
    session_id = "demo-session"
    user_input = "Can you analyze NVIDIA stock for me?"

    print("\n" + "=" * 70)
    print("BEDSHEET MULTI-AGENT DEMO")
    print("=" * 70)
    print(f"\nUser: {user_input}\n")
    print("-" * 70)

    # Track timing for parallel execution demo
    import time
    start_time = time.time()
    parallel_agents = []

    async for event in advisor.invoke(session_id=session_id, input_text=user_input):

        # --------------------------------------------------------
        # Delegation Events - Shows coordination decisions
        # --------------------------------------------------------
        if isinstance(event, DelegationEvent):
            agents = [d["agent_name"] for d in event.delegations]
            if len(agents) > 1:
                print(f"\n[PARALLEL DELEGATION] Dispatching {len(agents)} agents simultaneously:")
                for d in event.delegations:
                    print(f"   → {d['agent_name']}: {d['task'][:60]}...")
                parallel_agents = agents
            else:
                print(f"\n[DELEGATION] → {agents[0]}")

        # --------------------------------------------------------
        # Collaborator Lifecycle Events
        # --------------------------------------------------------
        elif isinstance(event, CollaboratorStartEvent):
            indicator = "⚡" if event.agent_name in parallel_agents else "→"
            print(f"\n{indicator} [{event.agent_name}] Starting...")

        elif isinstance(event, CollaboratorCompleteEvent):
            elapsed = time.time() - start_time
            print(f"✓ [{event.agent_name}] Complete ({elapsed:.1f}s)")

        # --------------------------------------------------------
        # Inner Events - See inside each collaborator
        # --------------------------------------------------------
        elif isinstance(event, CollaboratorEvent):
            inner = event.inner_event
            agent = event.agent_name
            indent = "    "

            if isinstance(inner, ToolCallEvent):
                print(f"{indent}🔧 [{agent}] Calling: {inner.tool_name}({inner.tool_input})")

            elif isinstance(inner, ToolResultEvent):
                if inner.error:
                    print(f"{indent}❌ [{agent}] Error: {inner.error}")
                else:
                    # Show truncated result
                    result_str = str(inner.result)
                    if len(result_str) > 80:
                        result_str = result_str[:80] + "..."
                    print(f"{indent}✓ [{agent}] Result: {result_str}")

            elif isinstance(inner, CompletionEvent):
                # Collaborator's response (before supervisor synthesis)
                preview = inner.response[:100] + "..." if len(inner.response) > 100 else inner.response
                print(f"{indent}💬 [{agent}] Response: {preview}")

        # --------------------------------------------------------
        # Final Completion
        # --------------------------------------------------------
        elif isinstance(event, CompletionEvent):
            total_time = time.time() - start_time
            print("\n" + "-" * 70)
            print(f"FINAL RESPONSE ({total_time:.1f}s total)")
            print("-" * 70)
            print(f"\n{event.response}")

        # --------------------------------------------------------
        # Error Handling
        # --------------------------------------------------------
        elif isinstance(event, ErrorEvent):
            print(f"\n⚠️  ERROR: {event.error}")
            if event.recoverable:
                print("   (Attempting recovery...)")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(run_with_rich_events())
```

## Example Output

Running the above produces output like:

```
======================================================================
BEDSHEET MULTI-AGENT DEMO
======================================================================

User: Can you analyze NVIDIA stock for me?

----------------------------------------------------------------------

[DELEGATION] → EthicsChecker

→ [EthicsChecker] Starting...
    🔧 [EthicsChecker] Calling: check_investment_request({'request': 'analyze NVIDIA stock'})
    ✓ [EthicsChecker] Result: {'approved': True, 'reason': 'Request is appropriate...'}
    💬 [EthicsChecker] Response: The request has been approved...
✓ [EthicsChecker] Complete (1.2s)

[PARALLEL DELEGATION] Dispatching 2 agents simultaneously:
   → MarketAnalyst: Analyze NVIDIA (NVDA) stock price and technical indicators
   → NewsResearcher: Find recent news about NVIDIA and analyze sentiment

⚡ [MarketAnalyst] Starting...
⚡ [NewsResearcher] Starting...
    🔧 [MarketAnalyst] Calling: get_stock_data({'symbol': 'NVDA'})
    🔧 [NewsResearcher] Calling: search_news({'query': 'nvidia', 'days': 7})
    ✓ [NewsResearcher] Result: {'query': 'nvidia', 'articles': [...], 'count': 3}
    ✓ [MarketAnalyst] Result: {'symbol': 'NVDA', 'price': 875.50, 'change': '+3.2%'...}
    🔧 [MarketAnalyst] Calling: get_technical_analysis({'symbol': 'NVDA'})
    🔧 [NewsResearcher] Calling: analyze_sentiment({'articles': [...]})
    ✓ [MarketAnalyst] Result: {'rsi': 62.5, 'macd': 'bullish crossover'...}
    ✓ [NewsResearcher] Result: {'sentiment': 'bullish', 'score': 1.0, 'confidence': 1.0}
    💬 [MarketAnalyst] Response: NVDA is currently trading at $875.50...
    💬 [NewsResearcher] Response: News sentiment for NVIDIA is strongly bullish...
✓ [MarketAnalyst] Complete (2.1s)
✓ [NewsResearcher] Complete (2.0s)

----------------------------------------------------------------------
FINAL RESPONSE (3.4s total)
----------------------------------------------------------------------

## NVIDIA (NVDA) Investment Analysis

### Current Market Data
- **Price**: $875.50 (+3.2% today)
- **P/E Ratio**: 65.4
- **Market Cap**: $2.1 Trillion

### Technical Analysis
The technical indicators paint a bullish picture:
- RSI at 62.5 (neutral, room to run)
- MACD showing bullish crossover
- Trading above both 50-day and 200-day moving averages
- Current uptrend with support at $820 and resistance at $920

### News & Sentiment
Recent news is overwhelmingly positive:
- Record data center revenue reported
- Continued surge in AI chip demand
- New AI supercomputer announcement

**Overall Sentiment**: Strongly Bullish (confidence: 100%)

### Summary
NVIDIA shows strong momentum from both technical and sentiment perspectives.
The stock is riding the AI wave with record revenue and positive news flow.
Technical indicators suggest the uptrend remains intact.

*Note: This is analysis only, not financial advice.*

======================================================================
```

## Key Features Demonstrated

### 1. Parallel Delegation
Notice how MarketAnalyst and NewsResearcher run **simultaneously**:
```
⚡ [MarketAnalyst] Starting...
⚡ [NewsResearcher] Starting...
```

Both agents make tool calls at the same time, reducing total response time.

### 2. Rich Event Streaming
Every step is visible:
- **DelegationEvent**: See when and why agents are dispatched
- **CollaboratorStartEvent**: Know when each agent begins
- **CollaboratorEvent**: See every tool call and result inside agents
- **CollaboratorCompleteEvent**: Know when each agent finishes
- **CompletionEvent**: The synthesized final response

### 3. Supervisor Synthesis
The supervisor doesn't just concatenate agent outputs - it intelligently synthesizes them into a structured, comprehensive response.

### 4. Sequential + Parallel Mix
Ethics check runs first (sequential), then Market and News run together (parallel). This ensures validation before expensive operations.

## Error Handling

Bedsheet gracefully handles agent failures:

```python
@market_tools.action(name="get_stock_data")
async def get_stock_data(symbol: str) -> dict:
    if symbol.upper() == "INVALID":
        raise ValueError("Invalid stock symbol")
    # ...
```

When an error occurs:
1. The collaborator's error becomes an ErrorEvent
2. The supervisor receives the error as a tool result
3. The supervisor can decide how to proceed (retry, use different agent, or explain to user)

## Best Practices

1. **Always check prerequisites first** (ethics, auth, etc.) before expensive operations
2. **Use parallel delegation** for independent tasks to reduce latency
3. **Handle events appropriately** for your UI (CLI, web, etc.)
4. **Keep collaborator instructions focused** - each agent should have a clear specialty
5. **Let the supervisor synthesize** - don't just concatenate agent outputs

## Structured Outputs for Multi-Agent Systems

When building multi-agent systems, **structured outputs** become especially powerful. Instead of parsing free-form text from collaborators, you can guarantee each agent returns data in a predictable format.

### Use Case: Portfolio Analysis Dashboard

Imagine a dashboard that displays analysis from multiple agents. Each agent returns structured JSON that your UI can render directly:

```python
from bedsheet.llm import AnthropicClient, OutputSchema

# Define schemas for each agent's output
market_schema = OutputSchema.from_dict({
    "type": "object",
    "properties": {
        "symbol": {"type": "string"},
        "price": {"type": "number"},
        "trend": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "key_levels": {
            "type": "object",
            "properties": {
                "support": {"type": "number"},
                "resistance": {"type": "number"}
            }
        }
    },
    "required": ["symbol", "price", "trend", "confidence"]
})

news_schema = OutputSchema.from_dict({
    "type": "object",
    "properties": {
        "sentiment": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
        "headline_count": {"type": "integer"},
        "top_headlines": {
            "type": "array",
            "items": {"type": "string"}
        },
        "risk_factors": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["sentiment", "headline_count"]
})
```

### Why This Matters for Multi-Agent

1. **Reliable Synthesis**: The supervisor can programmatically combine structured data from multiple agents
2. **UI-Ready Output**: Frontend can render agent results without parsing markdown
3. **Type Safety**: Your code knows exactly what shape the data will be
4. **Error Prevention**: No more "agent returned unexpected format" bugs

```python
# Supervisor can now work with predictable data
market_data = market_response.parsed_output  # Guaranteed structure
news_data = news_response.parsed_output      # Guaranteed structure

# Combine programmatically
combined_score = (
    market_data["confidence"] * 0.6 +
    (1.0 if news_data["sentiment"] == "bullish" else 0.5) * 0.4
)
```

### Pro Tip: Schema Per Agent Role

Define a schema that matches each agent's specialty:
- **MarketAnalyst**: Price, technicals, trend direction
- **NewsResearcher**: Sentiment, headlines, risk factors
- **RiskAnalyst**: Risk score, volatility metrics, warnings

This turns your multi-agent system from a "chat with experts" into a **structured data pipeline** that happens to use LLMs.

## Next Steps

- Add more specialized agents (RiskAnalyst, CompetitorTracker, etc.)
- Implement real tool integrations (market data APIs, news APIs)
- Add memory persistence with RedisMemory for conversation continuity
- Build a web UI that streams events in real-time
- Use structured outputs for dashboard-ready agent responses

---

**Copyright © 2025-2026 Sivan Grünberg, [Vitakka Consulting](https://vitakka.co/)**

Licensed under the Elastic License 2.0.
