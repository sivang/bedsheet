"""
Investment Advisor - Multi-Agent System

A target-agnostic multi-agent system for stock research and investment advice.
This agent definition works with any Bedsheet deployment target:
  - local: Uses AnthropicClient (Claude)
  - gcp: Translates to ADK LlmAgent (Gemini via Vertex AI)
  - aws: Uses Bedrock client

Architecture:
- InvestmentAdvisor (Supervisor): Coordinates the team, synthesizes recommendations
- MarketAnalyst (Agent): Stock data and technical analysis
- NewsResearcher (Agent): News search and sentiment analysis
- RiskAnalyst (Agent): Risk assessment and position sizing

Usage:
  # Generate deployment for your target
  bedsheet generate bedsheet.yaml --target gcp
  bedsheet generate bedsheet.yaml --target local
"""

from bedsheet import Agent, ActionGroup, Supervisor


# =============================================================================
# Market Analyst Tools
# =============================================================================

market_tools = ActionGroup(name="MarketTools")


@market_tools.action(
    name="get_stock_data",
    description="Get current stock price and key metrics"
)
def get_stock_data(symbol: str) -> dict:
    """Fetch stock data (simulated for demo)."""
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
def get_technical_analysis(symbol: str) -> dict:
    """Get technical indicators (simulated)."""
    technicals = {
        "NVDA": {"rsi": 62.5, "macd": "bullish crossover", "trend": "uptrend", "support": 820, "resistance": 920},
        "AAPL": {"rsi": 45.2, "macd": "neutral", "trend": "sideways", "support": 170, "resistance": 185},
        "MSFT": {"rsi": 55.8, "macd": "bullish", "trend": "uptrend", "support": 360, "resistance": 400},
        "GOOGL": {"rsi": 52.3, "macd": "neutral", "trend": "sideways", "support": 135, "resistance": 155},
        "AMZN": {"rsi": 58.1, "macd": "bullish", "trend": "uptrend", "support": 170, "resistance": 190},
    }

    symbol_upper = symbol.upper()
    base = technicals.get(symbol_upper, {"rsi": 50, "macd": "neutral", "trend": "unknown"})
    return {"symbol": symbol_upper, **base}


# =============================================================================
# News Researcher Tools
# =============================================================================

news_tools = ActionGroup(name="NewsTools")


@news_tools.action(
    name="search_news",
    description="Search for recent news about a company"
)
def search_news(query: str) -> dict:
    """Search recent news (simulated)."""
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
        "google": [
            {"headline": "Google's Gemini AI Gains Enterprise Traction", "sentiment": "positive"},
            {"headline": "Alphabet Announces Cloud Revenue Growth", "sentiment": "positive"},
            {"headline": "DOJ Antitrust Trial Continues", "sentiment": "negative"},
        ],
        "amazon": [
            {"headline": "AWS Revenue Growth Accelerates", "sentiment": "positive"},
            {"headline": "Amazon Prime Membership Hits New Highs", "sentiment": "positive"},
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
def analyze_sentiment(articles: list) -> dict:
    """Analyze sentiment from news articles."""
    if not articles:
        return {"sentiment": "neutral", "confidence": 0.0}

    sentiment_scores = {"positive": 1, "neutral": 0, "negative": -1}
    total = sum(sentiment_scores.get(a.get("sentiment", "neutral"), 0) for a in articles)
    avg = total / len(articles) if articles else 0

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


# =============================================================================
# Risk Analysis Tools
# =============================================================================

risk_tools = ActionGroup(name="RiskTools")


@risk_tools.action(
    name="analyze_volatility",
    description="Analyze volatility metrics for a stock"
)
def analyze_volatility(symbol: str) -> dict:
    """Analyze volatility (simulated)."""
    volatility_data = {
        "NVDA": {"beta": 1.65, "volatility_30d": "35.2%", "max_drawdown_1y": "-25.4%", "risk_rating": "HIGH"},
        "AAPL": {"beta": 1.28, "volatility_30d": "22.5%", "max_drawdown_1y": "-15.2%", "risk_rating": "MODERATE"},
        "MSFT": {"beta": 0.92, "volatility_30d": "19.2%", "max_drawdown_1y": "-12.1%", "risk_rating": "LOW-MODERATE"},
        "GOOGL": {"beta": 1.05, "volatility_30d": "25.8%", "max_drawdown_1y": "-18.7%", "risk_rating": "MODERATE"},
        "AMZN": {"beta": 1.22, "volatility_30d": "28.3%", "max_drawdown_1y": "-20.5%", "risk_rating": "MODERATE-HIGH"},
    }

    symbol_upper = symbol.upper()
    base = volatility_data.get(symbol_upper, {"risk_rating": "UNKNOWN"})
    return {"symbol": symbol_upper, **base}


@risk_tools.action(
    name="get_position_recommendation",
    description="Get position sizing recommendation based on risk tolerance"
)
def get_position_recommendation(symbol: str, risk_tolerance: str) -> dict:
    """Get position recommendation."""
    position_sizes = {
        "conservative": {"max_position": "2-3%", "entry_strategy": "Dollar-cost average over 3-6 months"},
        "moderate": {"max_position": "4-6%", "entry_strategy": "Split into 2-3 tranches"},
        "aggressive": {"max_position": "8-10%", "entry_strategy": "Can enter full position on dips"}
    }

    base = position_sizes.get(risk_tolerance.lower(), position_sizes["moderate"])

    return {
        "symbol": symbol.upper(),
        "risk_tolerance": risk_tolerance,
        "recommended_position": base["max_position"],
        "entry_strategy": base["entry_strategy"],
        "stop_loss": "Consider 15-20% stop-loss for risk management",
        "disclaimer": "This is educational content, not personalized financial advice."
    }


# =============================================================================
# Create Agent Instances (target-agnostic - no model_client specified)
# =============================================================================

# Market Analyst Agent
market_analyst = Agent(
    name="MarketAnalyst",
    instruction="""You are a market analyst specializing in stock analysis.
Use get_stock_data and get_technical_analysis to gather comprehensive data.
Provide clear, data-driven analysis with specific numbers and metrics.""",
)
market_analyst.add_action_group(market_tools)

# News Researcher Agent
news_researcher = Agent(
    name="NewsResearcher",
    instruction="""You are a news researcher focused on financial news.
Use search_news to find recent articles, then analyze_sentiment for overall mood.
Report key headlines and the overall sentiment (bullish/bearish/neutral).""",
)
news_researcher.add_action_group(news_tools)

# Risk Analyst Agent
risk_analyst = Agent(
    name="RiskAnalyst",
    instruction="""You are a risk analysis specialist.
Use analyze_volatility to assess stock risk metrics.
Use get_position_recommendation to suggest position sizing.
Always emphasize the importance of risk management.""",
)
risk_analyst.add_action_group(risk_tools)


# =============================================================================
# Investment Advisor Supervisor
# =============================================================================

agent = Supervisor(
    name="InvestmentAdvisor",
    instruction="""You are an investment research advisor coordinating specialized analysts.

Your team includes:
- MarketAnalyst: Gets stock data and technical analysis
- NewsResearcher: Finds news and analyzes sentiment
- RiskAnalyst: Assesses volatility and recommends position sizing

For each stock analysis request:
1. Delegate to ALL THREE agents IN PARALLEL:
   delegate(delegations=[
       {"agent_name": "MarketAnalyst", "task": "Analyze [SYMBOL] stock data and technicals"},
       {"agent_name": "NewsResearcher", "task": "Find and analyze news about [COMPANY]"},
       {"agent_name": "RiskAnalyst", "task": "Assess risk for [SYMBOL] and recommend position sizing"}
   ])
2. Synthesize their findings into a comprehensive analysis covering:
   - Current price and valuation metrics
   - Technical outlook (RSI, MACD, trend)
   - News sentiment
   - Risk assessment
   - Recommended strategy

Always include a disclaimer that this is educational content, not financial advice.
Recommend consulting a licensed financial advisor for personal investment decisions.""",
    collaborators=[market_analyst, news_researcher, risk_analyst],
    collaboration_mode="supervisor",
    max_iterations=10,
)


# =============================================================================
# For local testing
# =============================================================================

if __name__ == "__main__":
    print("Investment Advisor initialized!")
    print(f"Supervisor: {agent.name}")
    # Collaborators is a dict {name: agent}
    print(f"Collaborators: {list(agent.collaborators.keys())}")
    print("\nTools available:")
    for name, collab in agent.collaborators.items():
        print(f"  {name}:")
        for ag in collab._action_groups:
            for action in ag.get_actions():
                print(f"    - {action.name}: {action.description}")
