"""
Bedsheet Agents Demo - Run with: python -m bedsheet

A multi-agent investment advisor demonstrating:
- REAL stock data from Yahoo Finance
- REAL news from DuckDuckGo search
- Parallel delegation to multiple agents
- Rich event streaming (see every step)
- Supervisor synthesis of results

Requires: ANTHROPIC_API_KEY environment variable
Uses: Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)
Dependencies: yfinance, ddgs (pip install bedsheet[demo])
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
    CollaboratorCompleteEvent, TextTokenEvent
)


# ============================================================
# Market Analyst Tools - REAL DATA via yfinance
# ============================================================

market_tools = ActionGroup(name="MarketTools")


@market_tools.action(
    name="get_stock_data",
    description="Get REAL current stock price and key metrics from Yahoo Finance"
)
async def get_stock_data(symbol: str) -> dict:
    """Fetch REAL stock data from Yahoo Finance."""
    import yfinance as yf

    try:
        ticker = yf.Ticker(symbol.upper())
        info = ticker.info

        try:
            fast = ticker.fast_info
            current_price = fast.last_price
            prev_close = fast.previous_close
            market_cap = fast.market_cap
        except Exception:
            current_price = info.get("currentPrice") or info.get("regularMarketPrice")
            prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
            market_cap = info.get("marketCap")

        if current_price and prev_close:
            change = ((current_price - prev_close) / prev_close) * 100
            change_str = f"{change:+.2f}%"
        else:
            change_str = "N/A"

        if market_cap:
            if market_cap >= 1e12:
                market_cap_str = f"${market_cap/1e12:.2f}T"
            elif market_cap >= 1e9:
                market_cap_str = f"${market_cap/1e9:.2f}B"
            else:
                market_cap_str = f"${market_cap/1e6:.2f}M"
        else:
            market_cap_str = "N/A"

        return {
            "symbol": symbol.upper(),
            "company_name": info.get("shortName", info.get("longName", symbol.upper())),
            "price": round(current_price, 2) if current_price else "N/A",
            "change": change_str,
            "pe_ratio": round(info.get("trailingPE", 0), 2) if info.get("trailingPE") else "N/A",
            "forward_pe": round(info.get("forwardPE", 0), 2) if info.get("forwardPE") else "N/A",
            "market_cap": market_cap_str,
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
            "data_source": "Yahoo Finance (REAL DATA)",
        }
    except Exception as e:
        return {"error": f"Failed to fetch data for {symbol}: {str(e)}", "symbol": symbol.upper()}


@market_tools.action(
    name="get_technical_analysis",
    description="Get REAL technical analysis indicators calculated from historical price data"
)
async def get_technical_analysis(symbol: str) -> dict:
    """Calculate REAL technical indicators from Yahoo Finance historical data."""
    import yfinance as yf

    try:
        ticker = yf.Ticker(symbol.upper())
        hist = ticker.history(period="6mo")

        if hist.empty:
            return {"error": f"No historical data for {symbol}", "symbol": symbol.upper()}

        close = hist["Close"]

        # RSI (14-day)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = round(rsi.iloc[-1], 2)

        # MACD
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_histogram = macd_line - signal_line

        if macd_histogram.iloc[-1] > 0 and macd_histogram.iloc[-2] <= 0:
            macd_signal = "bullish crossover"
        elif macd_histogram.iloc[-1] < 0 and macd_histogram.iloc[-2] >= 0:
            macd_signal = "bearish crossover"
        elif macd_histogram.iloc[-1] > 0:
            macd_signal = "bullish"
        elif macd_histogram.iloc[-1] < 0:
            macd_signal = "bearish"
        else:
            macd_signal = "neutral"

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
        elif current_price < sma_20:
            trend = "downtrend"
        else:
            trend = "sideways"

        recent_30d = hist.tail(30)

        return {
            "symbol": symbol.upper(),
            "rsi_14": current_rsi,
            "rsi_signal": "overbought" if current_rsi > 70 else "oversold" if current_rsi < 30 else "neutral",
            "macd": macd_signal,
            "trend": trend,
            "sma_20": round(sma_20, 2),
            "sma_50": round(sma_50, 2),
            "current_price": round(current_price, 2),
            "support_30d": round(recent_30d["Low"].min(), 2),
            "resistance_30d": round(recent_30d["High"].max(), 2),
            "data_source": "Calculated from Yahoo Finance historical data (REAL DATA)",
        }
    except Exception as e:
        return {"error": f"Failed to calculate technicals for {symbol}: {str(e)}", "symbol": symbol.upper()}


# ============================================================
# News Researcher Tools - REAL DATA via DuckDuckGo
# ============================================================

news_tools = ActionGroup(name="NewsTools")


@news_tools.action(
    name="search_news",
    description="Search for REAL recent news about a company using DuckDuckGo"
)
async def search_news(query: str) -> dict:
    """Search REAL recent news using DuckDuckGo."""
    from ddgs import DDGS

    try:
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
    except Exception as e:
        return {"error": f"Failed to search news: {str(e)}", "query": query, "articles": [], "count": 0}


@news_tools.action(
    name="analyze_sentiment",
    description="Analyze overall sentiment from news headlines using keyword analysis"
)
async def analyze_sentiment(articles: list) -> dict:
    """Analyze sentiment from news articles using keyword-based analysis."""
    if not articles:
        return {"sentiment": "neutral", "confidence": 0.0, "articles_analyzed": 0}

    positive_words = {
        "surge", "soar", "jump", "gain", "rise", "beat", "exceed", "strong",
        "growth", "profit", "record", "high", "boost", "rally", "upgrade",
        "outperform", "bullish", "positive", "success", "innovation", "breakthrough"
    }
    negative_words = {
        "fall", "drop", "decline", "loss", "miss", "weak", "concern", "risk",
        "down", "cut", "layoff", "lawsuit", "investigation", "fine", "penalty",
        "downgrade", "bearish", "negative", "fail", "crash", "plunge", "warning"
    }

    total_score = 0
    for article in articles:
        headline = article.get("headline", "").lower()
        body = article.get("body", "").lower() if isinstance(article.get("body"), str) else ""
        text = headline + " " + body

        pos_count = sum(1 for word in positive_words if word in text)
        neg_count = sum(1 for word in negative_words if word in text)

        if pos_count > neg_count:
            total_score += 1
        elif neg_count > pos_count:
            total_score -= 1

    avg = total_score / len(articles)

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
Use get_stock_data to fetch REAL current stock data from Yahoo Finance.
Use get_technical_analysis to get REAL calculated technical indicators.
Provide clear, data-driven analysis with specific numbers.""",
        model_client=client,
    )
    market_agent.add_action_group(market_tools)

    news_agent = Agent(
        name="NewsResearcher",
        instruction="""You are a news researcher focused on financial news.
Use search_news to find REAL recent news articles via DuckDuckGo.
Use analyze_sentiment to analyze the overall sentiment.
Report key headlines with their sources.""",
        model_client=client,
    )
    news_agent.add_action_group(news_tools)

    advisor = Supervisor(
        name="InvestmentAdvisor",
        instruction="""You are an investment research advisor coordinating specialized analysts.

Your team uses REAL DATA - no mocks, no simulations:
- MarketAnalyst: REAL stock data from Yahoo Finance + calculated technical indicators
- NewsResearcher: REAL current news from DuckDuckGo + sentiment analysis

For each stock analysis request:
1. Delegate to BOTH MarketAnalyst AND NewsResearcher IN PARALLEL:
   delegate(delegations=[
       {"agent_name": "MarketAnalyst", "task": "Analyze [SYMBOL] stock data and technicals"},
       {"agent_name": "NewsResearcher", "task": "Find and analyze news about [COMPANY]"}
   ])
2. Synthesize their findings into a comprehensive analysis

Always use parallel delegation for faster response.
Mention that all data is REAL and current.
Include a disclaimer that this is educational content, not financial advice.""",
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

def emit(text: str, end: str = "\n"):
    """Print and immediately flush to show real-time progress."""
    print(text, end=end, flush=True)


async def run_demo():
    """Run the demo with real-time event streaming."""

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        emit("")
        emit("=" * 60)
        emit("  ANTHROPIC_API_KEY not set")
        emit("=" * 60)
        emit("")
        emit("  This demo uses Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)")
        emit("  and requires an Anthropic API key.")
        emit("")
        emit("  Set your API key:")
        emit("    export ANTHROPIC_API_KEY=your-key-here")
        emit("")
        emit("  Get an API key at: https://console.anthropic.com/")
        emit("=" * 60)
        emit("")
        sys.exit(1)

    # Check for demo dependencies
    try:
        import yfinance  # noqa: F401
        from ddgs import DDGS  # noqa: F401
    except ImportError:
        emit("")
        emit("=" * 60)
        emit("  Missing demo dependencies")
        emit("=" * 60)
        emit("")
        emit("  This demo uses REAL DATA from Yahoo Finance and DuckDuckGo.")
        emit("  Install the demo dependencies:")
        emit("")
        emit("    pip install bedsheet[demo]")
        emit("    # or: pip install yfinance ddgs")
        emit("")
        emit("=" * 60)
        emit("")
        sys.exit(1)

    emit("")
    emit("=" * 60)
    emit("  BEDSHEET AGENTS - Investment Advisor Demo")
    emit("  *** REAL DATA EDITION ***")
    emit("=" * 60)
    emit("")
    emit("  This demo uses REAL DATA:")
    emit("  - Stock data: Yahoo Finance (live prices)")
    emit("  - News: DuckDuckGo (current articles)")
    emit("  - Technical analysis: Calculated from real history")
    emit("")
    emit("  Model: Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)")
    emit("  Note: This uses your Anthropic API credits")
    emit("")
    emit("-" * 60)
    emit("")

    user_input = "Analyze NVIDIA stock for me"
    emit(f"User: {user_input}")
    emit("")
    emit("-" * 60)
    emit("")
    emit("Waiting for Claude...", end="")

    advisor = create_agents()
    start_time = time.time()
    parallel_agents = []
    first_event = True

    async for event in advisor.invoke(session_id="demo", input_text=user_input, stream=True):

        # Clear "Waiting for Claude..." on first event
        if first_event:
            emit("\r" + " " * 30 + "\r", end="")
            first_event = False

        if isinstance(event, DelegationEvent):
            agents = [d["agent_name"] for d in event.delegations]
            elapsed = time.time() - start_time
            if len(agents) > 1:
                emit(f"[{elapsed:.1f}s] PARALLEL DELEGATION - dispatching {len(agents)} agents:")
                for d in event.delegations:
                    task = d['task'][:50] + "..." if len(d['task']) > 50 else d['task']
                    emit(f"        -> {d['agent_name']}: {task}")
                parallel_agents = agents
            else:
                emit(f"[{elapsed:.1f}s] DELEGATION -> {agents[0]}")

        elif isinstance(event, CollaboratorStartEvent):
            elapsed = time.time() - start_time
            icon = "||" if event.agent_name in parallel_agents else "->"
            emit(f"\n[{elapsed:.1f}s] {icon} [{event.agent_name}] Starting...")

        elif isinstance(event, CollaboratorCompleteEvent):
            elapsed = time.time() - start_time
            emit(f"[{elapsed:.1f}s] OK [{event.agent_name}] Complete")

        elif isinstance(event, CollaboratorEvent):
            inner = event.inner_event
            agent = event.agent_name

            if isinstance(inner, TextTokenEvent):
                emit(inner.token, end="")

            elif isinstance(inner, ToolCallEvent):
                args = str(inner.tool_input)
                if len(args) > 40:
                    args = args[:40] + "..."
                emit(f"        [{agent}] -> {inner.tool_name}({args})")

            elif isinstance(inner, ToolResultEvent) and not inner.error:
                result = str(inner.result)
                if len(result) > 50:
                    result = result[:50] + "..."
                emit(f"        [{agent}] <- {result}")

        elif isinstance(event, TextTokenEvent):
            emit(event.token, end="")

        elif isinstance(event, CompletionEvent):
            elapsed = time.time() - start_time
            emit("")
            emit("-" * 60)
            emit(f"FINAL RESPONSE ({elapsed:.1f}s)")
            emit("-" * 60)
            emit("")
            emit(event.response)

        elif isinstance(event, ErrorEvent):
            emit(f"\nERROR: {event.error}")

    emit("")
    emit("=" * 60)
    emit("  Demo complete! All data was REAL - no mocks!")
    emit("")
    emit("  Docs: https://github.com/sivang/bedsheet")
    emit("=" * 60)
    emit("")


def main():
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
