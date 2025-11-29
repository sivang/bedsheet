"""
Bedsheet Agents Demo - Run with: python -m bedsheet

A multi-agent investment advisor demonstrating:
- Parallel delegation to multiple agents
- Rich event streaming (see every step)
- Supervisor synthesis of results

Requires: ANTHROPIC_API_KEY environment variable
Uses: Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)
"""

import asyncio
import os
import sys
import time
from bedsheet import Agent, ActionGroup, Supervisor
from bedsheet.llm import AnthropicClient
from bedsheet.memory import InMemory
from bedsheet.events import (
    ToolCallEvent, ToolResultEvent, CompletionEvent, ErrorEvent,
    DelegationEvent, CollaboratorStartEvent, CollaboratorEvent,
    CollaboratorCompleteEvent, RoutingEvent
)


# ============================================================
# Market Analyst Tools
# ============================================================

market_tools = ActionGroup(name="MarketTools")


@market_tools.action(
    name="get_stock_data",
    description="Get current stock price and key metrics"
)
async def get_stock_data(symbol: str) -> dict:
    """Fetch stock data (simulated for demo)."""
    await asyncio.sleep(0.3)

    stocks = {
        "NVDA": {"price": 875.50, "change": "+3.2%", "pe_ratio": 65.4, "market_cap": "2.1T"},
        "AAPL": {"price": 178.25, "change": "-0.5%", "pe_ratio": 28.1, "market_cap": "2.8T"},
        "MSFT": {"price": 378.90, "change": "+1.1%", "pe_ratio": 35.2, "market_cap": "2.9T"},
        "GOOGL": {"price": 141.80, "change": "+0.8%", "pe_ratio": 24.5, "market_cap": "1.8T"},
        "AMZN": {"price": 178.50, "change": "+1.5%", "pe_ratio": 62.3, "market_cap": "1.9T"},
    }

    symbol_upper = symbol.upper()
    if symbol_upper in stocks:
        return {"symbol": symbol_upper, **stocks[symbol_upper]}
    return {"error": f"Unknown symbol: {symbol}", "suggestion": "Try NVDA, AAPL, MSFT, GOOGL, or AMZN"}


@market_tools.action(
    name="get_technical_analysis",
    description="Get technical analysis indicators for a stock"
)
async def get_technical_analysis(symbol: str) -> dict:
    """Get technical indicators (simulated)."""
    await asyncio.sleep(0.2)

    technicals = {
        "NVDA": {"rsi": 62.5, "macd": "bullish crossover", "trend": "uptrend", "support": 820, "resistance": 920},
        "AAPL": {"rsi": 45.2, "macd": "neutral", "trend": "sideways", "support": 170, "resistance": 185},
        "MSFT": {"rsi": 55.8, "macd": "bullish", "trend": "uptrend", "support": 360, "resistance": 400},
    }

    symbol_upper = symbol.upper()
    base = technicals.get(symbol_upper, {"rsi": 50, "macd": "neutral", "trend": "unknown"})
    return {"symbol": symbol_upper, **base}


# ============================================================
# News Researcher Tools
# ============================================================

news_tools = ActionGroup(name="NewsTools")


@news_tools.action(
    name="search_news",
    description="Search for recent news about a company"
)
async def search_news(query: str) -> dict:
    """Search recent news (simulated)."""
    await asyncio.sleep(0.25)

    news_db = {
        "nvidia": [
            {"headline": "NVIDIA Reports Record Data Center Revenue", "sentiment": "positive"},
            {"headline": "AI Chip Demand Continues to Surge", "sentiment": "positive"},
            {"headline": "NVIDIA Announces New AI Supercomputer", "sentiment": "positive"},
        ],
        "apple": [
            {"headline": "Apple Vision Pro Launches to Mixed Reviews", "sentiment": "neutral"},
            {"headline": "iPhone Sales Slow in China", "sentiment": "negative"},
        ],
        "microsoft": [
            {"headline": "Microsoft Copilot Adoption Accelerates", "sentiment": "positive"},
            {"headline": "Azure Revenue Beats Expectations", "sentiment": "positive"},
        ],
    }

    query_lower = query.lower()
    for company, articles in news_db.items():
        if company in query_lower:
            return {"query": query, "articles": articles, "count": len(articles)}

    return {"query": query, "articles": [], "count": 0}


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
        "confidence": round(min(abs(avg) + 0.5, 1.0), 2),
        "articles_analyzed": len(articles)
    }


# ============================================================
# Create Agents
# ============================================================

def create_agents():
    """Create all agents with shared LLM client."""
    client = AnthropicClient()

    market_agent = Agent(
        name="MarketAnalyst",
        instruction="""You are a market analyst specializing in stock analysis.
Use get_stock_data and get_technical_analysis to gather comprehensive data.
Provide clear, data-driven analysis.""",
        model_client=client,
    )
    market_agent.add_action_group(market_tools)

    news_agent = Agent(
        name="NewsResearcher",
        instruction="""You are a news researcher focused on financial news.
Use search_news to find recent articles, then analyze_sentiment for overall mood.
Report key headlines and sentiment analysis.""",
        model_client=client,
    )
    news_agent.add_action_group(news_tools)

    advisor = Supervisor(
        name="InvestmentAdvisor",
        instruction="""You are an investment research advisor coordinating specialized analysts.

For each stock analysis request:
1. Delegate to BOTH MarketAnalyst AND NewsResearcher IN PARALLEL:
   delegate(delegations=[
       {"agent_name": "MarketAnalyst", "task": "Analyze [SYMBOL] stock data and technicals"},
       {"agent_name": "NewsResearcher", "task": "Find and analyze news about [COMPANY]"}
   ])
2. Synthesize their findings into a comprehensive analysis

Always use parallel delegation for faster response.""",
        model_client=client,
        memory=InMemory(),
        collaborators=[market_agent, news_agent],
        collaboration_mode="supervisor",
        max_iterations=10,
    )

    return advisor


# ============================================================
# Event Display
# ============================================================

async def run_demo():
    """Run the demo with rich event output."""

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print()
        print("=" * 60)
        print("  ANTHROPIC_API_KEY not set")
        print("=" * 60)
        print()
        print("  This demo uses Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)")
        print("  and requires an Anthropic API key.")
        print()
        print("  Set your API key:")
        print("    export ANTHROPIC_API_KEY=your-key-here")
        print()
        print("  Get an API key at: https://console.anthropic.com/")
        print("=" * 60)
        print()
        sys.exit(1)

    print()
    print("=" * 60)
    print("  BEDSHEET AGENTS - Investment Advisor Demo")
    print("=" * 60)
    print()
    print("  This demo shows:")
    print("  - Parallel delegation to multiple agents")
    print("  - Rich event streaming (see every step)")
    print("  - Supervisor synthesis of results")
    print()
    print("  Model: Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)")
    print("  Note: This uses your Anthropic API credits")
    print()
    print("-" * 60)
    print()

    user_input = "Analyze NVIDIA stock for me"
    print(f"User: {user_input}")
    print()
    print("-" * 60)

    advisor = create_agents()
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
            print("-" * 60)
            print(f"FINAL RESPONSE ({elapsed:.1f}s)")
            print("-" * 60)
            print()
            print(event.response)

        elif isinstance(event, ErrorEvent):
            print(f"\nERROR: {event.error}")

    print()
    print("=" * 60)
    print("  Demo complete!")
    print()
    print("  Docs: https://github.com/vitakka/bedsheet-agents")
    print("=" * 60)
    print()


def main():
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
