"""
Bedsheet Agents Demo - Run with: python -m bedsheet

A zero-config demo showcasing multi-agent collaboration.
No API key required - uses simulated responses.
"""

import asyncio
import time
from bedsheet import Agent, Supervisor, ActionGroup
from bedsheet.testing import MockLLMClient, MockResponse
from bedsheet.llm.base import ToolCall
from bedsheet.events import (
    ToolCallEvent, ToolResultEvent, CompletionEvent,
    DelegationEvent, CollaboratorStartEvent, CollaboratorEvent,
    CollaboratorCompleteEvent, RoutingEvent
)


# ============================================================
# Simulated Tools
# ============================================================

market_tools = ActionGroup(name="MarketTools")

@market_tools.action(name="get_stock_data", description="Get stock price and metrics")
async def get_stock_data(symbol: str) -> dict:
    await asyncio.sleep(0.3)  # Simulate latency
    return {
        "symbol": symbol.upper(),
        "price": 875.50,
        "change": "+3.2%",
        "pe_ratio": 65.4,
        "market_cap": "2.1T"
    }

@market_tools.action(name="get_technicals", description="Get technical indicators")
async def get_technicals(symbol: str) -> dict:
    await asyncio.sleep(0.2)
    return {
        "rsi": 62.5,
        "macd": "bullish crossover",
        "trend": "uptrend",
        "support": 820,
        "resistance": 920
    }


news_tools = ActionGroup(name="NewsTools")

@news_tools.action(name="search_news", description="Search financial news")
async def search_news(company: str) -> dict:
    await asyncio.sleep(0.25)
    return {
        "articles": [
            {"headline": "NVIDIA Reports Record Data Center Revenue", "sentiment": "positive"},
            {"headline": "AI Chip Demand Continues to Surge", "sentiment": "positive"},
            {"headline": "New Blackwell Architecture Announced", "sentiment": "positive"},
        ],
        "count": 3
    }

@news_tools.action(name="analyze_sentiment", description="Analyze news sentiment")
async def analyze_sentiment(headlines: list) -> dict:
    await asyncio.sleep(0.15)
    return {
        "sentiment": "strongly bullish",
        "confidence": 0.92,
        "articles_analyzed": len(headlines)
    }


# ============================================================
# Create Agents with Mock LLM
# ============================================================

def create_demo_agents():
    """Create agents with pre-programmed mock responses."""

    # Market Analyst responses
    market_mock = MockLLMClient(responses=[
        MockResponse(tool_calls=[
            ToolCall(id="m1", name="get_stock_data", input={"symbol": "NVDA"}),
            ToolCall(id="m2", name="get_technicals", input={"symbol": "NVDA"}),
        ]),
        MockResponse(text="NVDA is trading at $875.50 (+3.2%). Technical indicators show RSI at 62.5 with a bullish MACD crossover. The stock is in an uptrend with support at $820 and resistance at $920."),
    ])

    market_analyst = Agent(
        name="MarketAnalyst",
        instruction="Analyze stocks using price data and technical indicators.",
        model_client=market_mock,
    )
    market_analyst.add_action_group(market_tools)

    # News Researcher responses
    news_mock = MockLLMClient(responses=[
        MockResponse(tool_calls=[
            ToolCall(id="n1", name="search_news", input={"company": "NVIDIA"}),
        ]),
        MockResponse(tool_calls=[
            ToolCall(id="n2", name="analyze_sentiment", input={"headlines": ["Record Revenue", "AI Demand", "Blackwell"]}),
        ]),
        MockResponse(text="News sentiment for NVIDIA is strongly bullish (92% confidence). Recent headlines highlight record data center revenue and continued AI chip demand."),
    ])

    news_researcher = Agent(
        name="NewsResearcher",
        instruction="Research recent news and analyze sentiment.",
        model_client=news_mock,
    )
    news_researcher.add_action_group(news_tools)

    # Supervisor responses
    supervisor_mock = MockLLMClient(responses=[
        # First: parallel delegation
        MockResponse(tool_calls=[
            ToolCall(id="d1", name="delegate", input={
                "delegations": [
                    {"agent_name": "MarketAnalyst", "task": "Analyze NVIDIA (NVDA) stock price and technical indicators"},
                    {"agent_name": "NewsResearcher", "task": "Find and analyze recent news about NVIDIA"}
                ]
            }),
        ]),
        # Then: synthesize
        MockResponse(text="""## NVIDIA (NVDA) Investment Analysis

### Market Data
- **Current Price**: $875.50 (+3.2%)
- **P/E Ratio**: 65.4
- **Market Cap**: $2.1 Trillion

### Technical Analysis
The technical picture is bullish:
- RSI at 62.5 - healthy momentum, not overbought
- MACD showing bullish crossover
- Trading in clear uptrend
- Support: $820 | Resistance: $920

### News & Sentiment
Recent news is overwhelmingly positive:
- Record data center revenue
- Continued surge in AI chip demand
- New Blackwell architecture generating excitement

**Overall Sentiment**: Strongly Bullish (92% confidence)

### Summary
NVIDIA shows strong momentum across both technical and fundamental factors. The AI-driven demand cycle remains intact with positive news flow and solid technical support.

*This is analysis only, not financial advice.*"""),
    ])

    advisor = Supervisor(
        name="InvestmentAdvisor",
        instruction="Coordinate investment research using parallel delegation.",
        model_client=supervisor_mock,
        collaborators=[market_analyst, news_researcher],
        collaboration_mode="supervisor",
    )

    return advisor


# ============================================================
# Rich Event Display
# ============================================================

async def run_demo():
    """Run the demo with rich event output."""

    print()
    print("=" * 70)
    print("  BEDSHEET AGENTS - Multi-Agent Collaboration Demo")
    print("=" * 70)
    print()
    print("  This demo shows:")
    print("  - Parallel delegation to multiple agents")
    print("  - Rich event streaming (see every step)")
    print("  - Tool execution with simulated latency")
    print("  - Supervisor synthesis of results")
    print()
    print("  No API key needed - using simulated responses")
    print()
    print("-" * 70)
    print()

    user_input = "Analyze NVIDIA stock for me"
    print(f"User: {user_input}")
    print()
    print("-" * 70)

    advisor = create_demo_agents()
    start_time = time.time()
    parallel_agents = []

    async for event in advisor.invoke(session_id="demo", input_text=user_input):

        if isinstance(event, DelegationEvent):
            agents = [d["agent_name"] for d in event.delegations]
            elapsed = time.time() - start_time
            if len(agents) > 1:
                print(f"\n[{elapsed:.1f}s] PARALLEL DELEGATION - dispatching {len(agents)} agents:")
                for d in event.delegations:
                    task = d['task'][:50] + "..." if len(d['task']) > 50 else d['task']
                    print(f"         -> {d['agent_name']}: {task}")
                parallel_agents = agents
            else:
                print(f"\n[{elapsed:.1f}s] DELEGATION -> {agents[0]}")

        elif isinstance(event, CollaboratorStartEvent):
            elapsed = time.time() - start_time
            icon = "||" if event.agent_name in parallel_agents else "->"
            print(f"\n[{elapsed:.1f}s] {icon} [{event.agent_name}] Starting...")

        elif isinstance(event, CollaboratorCompleteEvent):
            elapsed = time.time() - start_time
            print(f"[{elapsed:.1f}s] OK [{event.agent_name}] Complete")

        elif isinstance(event, CollaboratorEvent):
            inner = event.inner_event
            agent = event.agent_name
            elapsed = time.time() - start_time

            if isinstance(inner, ToolCallEvent):
                args = str(inner.tool_input)
                if len(args) > 40:
                    args = args[:40] + "..."
                print(f"         [{agent}] -> {inner.tool_name}({args})")

            elif isinstance(inner, ToolResultEvent) and not inner.error:
                result = str(inner.result)
                if len(result) > 50:
                    result = result[:50] + "..."
                print(f"         [{agent}] <- {result}")

        elif isinstance(event, CompletionEvent):
            elapsed = time.time() - start_time
            print()
            print("-" * 70)
            print(f"FINAL RESPONSE ({elapsed:.1f}s)")
            print("-" * 70)
            print()
            print(event.response)

    print()
    print("=" * 70)
    print("  Demo complete! To use with real LLM:")
    print()
    print("    export ANTHROPIC_API_KEY=your-key")
    print("    python examples/investment_advisor.py")
    print()
    print("  Docs: https://github.com/vitakka/bedsheet-agents")
    print("=" * 70)
    print()


def main():
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
