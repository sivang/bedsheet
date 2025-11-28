"""
Investment Advisor - Multi-Agent Demo

This example demonstrates Bedsheet's multi-agent features:
- Parallel delegation (multiple agents working simultaneously)
- Rich event streaming (see every step of execution)
- Supervisor synthesis (intelligent combination of outputs)
- Sequential + parallel workflow (ethics first, then parallel research)

Run with: python examples/investment_advisor.py
Requires: ANTHROPIC_API_KEY environment variable
"""

import asyncio
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


# ============================================================
# Market Analyst Agent
# ============================================================

market_tools = ActionGroup(name="MarketTools")


@market_tools.action(
    name="get_stock_data",
    description="Get current stock price and key metrics"
)
async def get_stock_data(symbol: str) -> dict:
    """Fetch stock data (simulated for demo)."""
    await asyncio.sleep(0.5)  # Simulate API latency

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
    await asyncio.sleep(0.3)

    technicals = {
        "NVDA": {"rsi": 62.5, "macd": "bullish crossover", "trend": "uptrend", "support": 820, "resistance": 920},
        "AAPL": {"rsi": 45.2, "macd": "neutral", "trend": "sideways", "support": 170, "resistance": 185},
        "MSFT": {"rsi": 55.8, "macd": "bullish", "trend": "uptrend", "support": 360, "resistance": 400},
    }

    symbol_upper = symbol.upper()
    base = technicals.get(symbol_upper, {"rsi": 50, "macd": "neutral", "trend": "unknown"})
    return {"symbol": symbol_upper, **base, "moving_avg_50": "above", "moving_avg_200": "above"}


# ============================================================
# News Researcher Agent
# ============================================================

news_tools = ActionGroup(name="NewsTools")


@news_tools.action(
    name="search_news",
    description="Search for recent news about a company"
)
async def search_news(query: str, days: int = 7) -> dict:
    """Search recent news (simulated)."""
    await asyncio.sleep(0.4)

    news_db = {
        "nvidia": [
            {"headline": "NVIDIA Reports Record Data Center Revenue", "sentiment": "positive", "date": "2024-02-21"},
            {"headline": "AI Chip Demand Continues to Surge", "sentiment": "positive", "date": "2024-02-20"},
            {"headline": "NVIDIA Announces New AI Supercomputer", "sentiment": "positive", "date": "2024-02-19"},
        ],
        "apple": [
            {"headline": "Apple Vision Pro Launches to Mixed Reviews", "sentiment": "neutral", "date": "2024-02-21"},
            {"headline": "iPhone Sales Slow in China", "sentiment": "negative", "date": "2024-02-20"},
        ],
        "microsoft": [
            {"headline": "Microsoft Copilot Adoption Accelerates", "sentiment": "positive", "date": "2024-02-21"},
            {"headline": "Azure Revenue Beats Expectations", "sentiment": "positive", "date": "2024-02-20"},
        ],
    }

    query_lower = query.lower()
    for company, articles in news_db.items():
        if company in query_lower:
            return {"query": query, "articles": articles, "count": len(articles)}

    return {"query": query, "articles": [], "count": 0, "message": "No recent news found"}


@news_tools.action(
    name="analyze_sentiment",
    description="Analyze overall sentiment from news articles"
)
async def analyze_sentiment(articles: list[dict]) -> dict:
    """Analyze sentiment from news articles."""
    if not articles:
        return {"sentiment": "neutral", "confidence": 0.0, "articles_analyzed": 0}

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
        "score": round(avg, 2),
        "articles_analyzed": len(articles),
        "confidence": round(min(abs(avg) + 0.5, 1.0), 2)
    }


# ============================================================
# Create Agents
# ============================================================

def create_agents():
    """Create all agents with shared LLM client."""
    client = AnthropicClient()

    ethics_agent = Agent(
        name="EthicsChecker",
        instruction="""You review investment-related requests for ethical concerns.
Use the check_investment_request tool and provide a clear verdict.
Be strict about insider trading, market manipulation, and illegal schemes.""",
        model_client=client,
    )
    ethics_agent.add_action_group(ethics_tools)

    market_agent = Agent(
        name="MarketAnalyst",
        instruction="""You are a market analyst specializing in stock analysis.
Use get_stock_data and get_technical_analysis to gather comprehensive data.
Provide clear, data-driven analysis without specific buy/sell recommendations.""",
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

## Workflow
1. ALWAYS delegate to EthicsChecker first to validate the request
2. If approved, delegate to BOTH MarketAnalyst AND NewsResearcher IN PARALLEL:
   delegate(delegations=[
       {"agent_name": "MarketAnalyst", "task": "Analyze [SYMBOL] stock data and technicals"},
       {"agent_name": "NewsResearcher", "task": "Find and analyze news about [COMPANY]"}
   ])
3. Synthesize findings into a comprehensive, well-structured analysis

## Important
- Check ethics BEFORE research (saves resources on rejected requests)
- Use parallel delegation for Market + News (faster response)
- Provide balanced analysis, not financial advice""",
        model_client=client,
        memory=InMemory(),
        collaborators=[ethics_agent, market_agent, news_agent],
        collaboration_mode="supervisor",
        max_iterations=15,
    )

    return advisor


# ============================================================
# Rich Event Handler
# ============================================================

async def run_with_events(advisor: Supervisor, user_input: str, session_id: str = "demo"):
    """Run advisor with rich event streaming output."""
    print("\n" + "=" * 70)
    print("BEDSHEET MULTI-AGENT INVESTMENT ADVISOR")
    print("=" * 70)
    print(f"\nUser: {user_input}\n")
    print("-" * 70)

    start_time = time.time()
    parallel_agents = []

    async for event in advisor.invoke(session_id=session_id, input_text=user_input):

        if isinstance(event, DelegationEvent):
            agents = [d["agent_name"] for d in event.delegations]
            if len(agents) > 1:
                print(f"\n[PARALLEL DELEGATION] Dispatching {len(agents)} agents:")
                for d in event.delegations:
                    task_preview = d['task'][:55] + "..." if len(d['task']) > 55 else d['task']
                    print(f"   → {d['agent_name']}: {task_preview}")
                parallel_agents = agents
            else:
                print(f"\n[DELEGATION] → {agents[0]}")

        elif isinstance(event, RoutingEvent):
            print(f"\n[ROUTING] → {event.agent_name}")

        elif isinstance(event, CollaboratorStartEvent):
            icon = "⚡" if event.agent_name in parallel_agents else "→"
            print(f"\n{icon} [{event.agent_name}] Starting...")

        elif isinstance(event, CollaboratorCompleteEvent):
            elapsed = time.time() - start_time
            print(f"✓ [{event.agent_name}] Complete ({elapsed:.1f}s)")

        elif isinstance(event, CollaboratorEvent):
            inner = event.inner_event
            agent = event.agent_name
            indent = "    "

            if isinstance(inner, ToolCallEvent):
                args = str(inner.tool_input)
                if len(args) > 50:
                    args = args[:50] + "..."
                print(f"{indent}🔧 Calling: {inner.tool_name}({args})")

            elif isinstance(inner, ToolResultEvent):
                if inner.error:
                    print(f"{indent}❌ Error: {inner.error}")
                else:
                    result_str = str(inner.result)
                    if len(result_str) > 60:
                        result_str = result_str[:60] + "..."
                    print(f"{indent}✓ Result: {result_str}")

            elif isinstance(inner, CompletionEvent):
                preview = inner.response[:80] + "..." if len(inner.response) > 80 else inner.response
                print(f"{indent}💬 {preview}")

        elif isinstance(event, CompletionEvent):
            total_time = time.time() - start_time
            print("\n" + "-" * 70)
            print(f"FINAL RESPONSE ({total_time:.1f}s)")
            print("-" * 70)
            print(f"\n{event.response}")

        elif isinstance(event, ErrorEvent):
            print(f"\n⚠️  ERROR: {event.error}")

    print("\n" + "=" * 70)


# ============================================================
# Interactive Mode
# ============================================================

async def interactive_mode():
    """Run in interactive mode."""
    advisor = create_agents()
    session_id = "interactive-session"

    print("\n" + "=" * 70)
    print("BEDSHEET MULTI-AGENT INVESTMENT ADVISOR")
    print("=" * 70)
    print("\nAsk about stocks: NVDA, AAPL, MSFT, GOOGL, AMZN")
    print("Type 'quit' to exit\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("\nGoodbye!")
                break

            await run_with_events(advisor, user_input, session_id)
            print()

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break


# ============================================================
# Demo Mode
# ============================================================

async def demo_mode():
    """Run pre-defined demo queries."""
    advisor = create_agents()

    queries = [
        "Analyze NVIDIA stock for me",
        "What about Apple stock?",
        # "How can I do insider trading?",  # Uncomment to test ethics rejection
    ]

    for query in queries:
        await run_with_events(advisor, query, "demo-session")
        print("\n")
        await asyncio.sleep(1)


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        print("Running demo mode...")
        asyncio.run(demo_mode())
    else:
        asyncio.run(interactive_mode())
