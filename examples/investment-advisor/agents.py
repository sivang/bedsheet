"""
Investment Advisor - Multi-Agent System with REAL DATA

A target-agnostic multi-agent system for stock research and investment advice.
This agent definition works with any Bedsheet deployment target:
  - local: Uses AnthropicClient (Claude)
  - gcp: Translates to ADK LlmAgent (Gemini via Vertex AI)
  - aws: Uses Bedrock client

Architecture:
- InvestmentAdvisor (Supervisor): Coordinates the team, synthesizes recommendations
- MarketAnalyst (Agent): REAL stock data from Yahoo Finance + calculated technicals
- NewsResearcher (Agent): REAL news from DuckDuckGo search
- RiskAnalyst (Agent): REAL volatility calculated from historical data

Usage:
  # Generate deployment for your target
  bedsheet generate bedsheet.yaml --target gcp
  bedsheet generate bedsheet.yaml --target local
"""

from bedsheet import Agent, ActionGroup, Supervisor


# =============================================================================
# Market Analyst Tools - REAL DATA via yfinance
# =============================================================================

market_tools = ActionGroup(name="MarketTools")


@market_tools.action(
    name="get_stock_data",
    description="Get REAL current stock price and key metrics from Yahoo Finance"
)
def get_stock_data(symbol: str) -> dict:
    """Fetch REAL stock data from Yahoo Finance."""
    import yfinance as yf

    try:
        ticker = yf.Ticker(symbol.upper())
        info = ticker.info

        # Get current price from fast_info or info
        try:
            fast = ticker.fast_info
            current_price = fast.last_price
            prev_close = fast.previous_close
            market_cap = fast.market_cap
        except Exception:
            current_price = info.get("currentPrice") or info.get("regularMarketPrice")
            prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
            market_cap = info.get("marketCap")

        # Calculate change
        if current_price and prev_close:
            change = ((current_price - prev_close) / prev_close) * 100
            change_str = f"{change:+.2f}%"
        else:
            change_str = "N/A"

        # Format market cap
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
            "volume": info.get("volume"),
            "avg_volume": info.get("averageVolume"),
            "dividend_yield": f"{info.get('dividendYield', 0) * 100:.2f}%" if info.get("dividendYield") else "N/A",
            "data_source": "Yahoo Finance (REAL DATA)",
        }
    except Exception as e:
        return {"error": f"Failed to fetch data for {symbol}: {str(e)}", "symbol": symbol.upper()}


@market_tools.action(
    name="get_technical_analysis",
    description="Get REAL technical analysis indicators calculated from historical price data"
)
def get_technical_analysis(symbol: str) -> dict:
    """Calculate REAL technical indicators from Yahoo Finance historical data."""
    import yfinance as yf

    try:
        ticker = yf.Ticker(symbol.upper())
        # Get 6 months of daily data for calculations
        hist = ticker.history(period="6mo")

        if hist.empty:
            return {"error": f"No historical data for {symbol}", "symbol": symbol.upper()}

        close = hist["Close"]

        # Calculate RSI (14-day)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = round(rsi.iloc[-1], 2)

        # Calculate MACD
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_histogram = macd_line - signal_line

        # Determine MACD signal
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

        # Calculate moving averages
        sma_20 = close.rolling(window=20).mean().iloc[-1]
        sma_50 = close.rolling(window=50).mean().iloc[-1]
        current_price = close.iloc[-1]

        # Determine trend
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

        # Calculate support/resistance (simple: recent lows/highs)
        recent_30d = hist.tail(30)
        support = round(recent_30d["Low"].min(), 2)
        resistance = round(recent_30d["High"].max(), 2)

        return {
            "symbol": symbol.upper(),
            "rsi_14": current_rsi,
            "rsi_signal": "overbought" if current_rsi > 70 else "oversold" if current_rsi < 30 else "neutral",
            "macd": macd_signal,
            "macd_histogram": round(macd_histogram.iloc[-1], 4),
            "trend": trend,
            "sma_20": round(sma_20, 2),
            "sma_50": round(sma_50, 2),
            "current_price": round(current_price, 2),
            "support_30d": support,
            "resistance_30d": resistance,
            "data_source": "Calculated from Yahoo Finance historical data (REAL DATA)",
        }
    except Exception as e:
        return {"error": f"Failed to calculate technicals for {symbol}: {str(e)}", "symbol": symbol.upper()}


# =============================================================================
# News Researcher Tools - REAL DATA via DuckDuckGo
# =============================================================================

news_tools = ActionGroup(name="NewsTools")


@news_tools.action(
    name="search_news",
    description="Search for REAL recent news about a company using DuckDuckGo"
)
def search_news(query: str) -> dict:
    """Search REAL recent news using DuckDuckGo."""
    from ddgs import DDGS

    try:
        with DDGS() as ddgs:
            # Search for news
            results = list(ddgs.news(query, max_results=5))

            articles = []
            for r in results:
                articles.append({
                    "headline": r.get("title", ""),
                    "source": r.get("source", ""),
                    "date": r.get("date", ""),
                    "url": r.get("url", ""),
                    "body": r.get("body", "")[:200] + "..." if r.get("body") else "",
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
def analyze_sentiment(articles: list) -> dict:
    """Analyze sentiment from news articles using keyword-based analysis."""
    if not articles:
        return {"sentiment": "neutral", "confidence": 0.0, "articles_analyzed": 0}

    # Positive and negative keyword lists for financial news
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
    analyzed_headlines = []

    for article in articles:
        headline = article.get("headline", "").lower()
        body = article.get("body", "").lower() if isinstance(article.get("body"), str) else ""
        text = headline + " " + body

        pos_count = sum(1 for word in positive_words if word in text)
        neg_count = sum(1 for word in negative_words if word in text)

        if pos_count > neg_count:
            sentiment = "positive"
            score = 1
        elif neg_count > pos_count:
            sentiment = "negative"
            score = -1
        else:
            sentiment = "neutral"
            score = 0

        total_score += score
        analyzed_headlines.append({"headline": article.get("headline", ""), "sentiment": sentiment})

    avg = total_score / len(articles) if articles else 0

    if avg > 0.3:
        overall_sentiment = "bullish"
    elif avg < -0.3:
        overall_sentiment = "bearish"
    else:
        overall_sentiment = "neutral"

    return {
        "sentiment": overall_sentiment,
        "confidence": round(min(abs(avg) + 0.5, 1.0), 2),
        "articles_analyzed": len(articles),
        "breakdown": analyzed_headlines,
        "analysis_method": "Keyword-based sentiment analysis (REAL ANALYSIS)",
    }


# =============================================================================
# Risk Analysis Tools - REAL DATA calculated from historical prices
# =============================================================================

risk_tools = ActionGroup(name="RiskTools")


@risk_tools.action(
    name="analyze_volatility",
    description="Analyze REAL volatility metrics calculated from historical price data"
)
def analyze_volatility(symbol: str) -> dict:
    """Calculate REAL volatility metrics from Yahoo Finance data."""
    import yfinance as yf

    try:
        ticker = yf.Ticker(symbol.upper())
        # Get 1 year of data
        hist = ticker.history(period="1y")
        # Get SPY for beta calculation
        spy = yf.Ticker("SPY")
        spy_hist = spy.history(period="1y")

        if hist.empty:
            return {"error": f"No historical data for {symbol}", "symbol": symbol.upper()}

        close = hist["Close"]
        returns = close.pct_change().dropna()

        # Calculate 30-day volatility (annualized)
        volatility_30d = returns.tail(30).std() * (252 ** 0.5) * 100

        # Calculate beta against S&P 500
        if not spy_hist.empty:
            spy_returns = spy_hist["Close"].pct_change().dropna()
            # Align the data
            common_dates = returns.index.intersection(spy_returns.index)
            stock_ret = returns.loc[common_dates]
            spy_ret = spy_returns.loc[common_dates]

            covariance = stock_ret.cov(spy_ret)
            spy_variance = spy_ret.var()
            beta = covariance / spy_variance if spy_variance != 0 else 1.0
        else:
            beta = 1.0

        # Calculate max drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min() * 100

        # Determine risk rating
        if beta > 1.5 or volatility_30d > 40:
            risk_rating = "HIGH"
        elif beta > 1.2 or volatility_30d > 30:
            risk_rating = "MODERATE-HIGH"
        elif beta > 0.8 or volatility_30d > 20:
            risk_rating = "MODERATE"
        elif beta > 0.5:
            risk_rating = "LOW-MODERATE"
        else:
            risk_rating = "LOW"

        # Calculate Sharpe ratio (assuming 5% risk-free rate)
        avg_return = returns.mean() * 252
        sharpe = (avg_return - 0.05) / (returns.std() * (252 ** 0.5)) if returns.std() > 0 else 0

        return {
            "symbol": symbol.upper(),
            "beta": round(beta, 2),
            "volatility_30d": f"{volatility_30d:.1f}%",
            "volatility_annualized": f"{returns.std() * (252 ** 0.5) * 100:.1f}%",
            "max_drawdown_1y": f"{max_drawdown:.1f}%",
            "sharpe_ratio": round(sharpe, 2),
            "risk_rating": risk_rating,
            "trading_days_analyzed": len(returns),
            "data_source": "Calculated from Yahoo Finance 1-year data (REAL DATA)",
        }
    except Exception as e:
        return {"error": f"Failed to analyze volatility for {symbol}: {str(e)}", "symbol": symbol.upper()}


@risk_tools.action(
    name="get_position_recommendation",
    description="Get position sizing recommendation based on risk tolerance and real volatility data"
)
def get_position_recommendation(symbol: str, risk_tolerance: str) -> dict:
    """Get position recommendation based on volatility and risk tolerance."""
    # First get real volatility data
    volatility_data = analyze_volatility(symbol)

    risk_rating = volatility_data.get("risk_rating", "MODERATE")

    # Adjust position size based on both risk tolerance and stock volatility
    base_positions = {
        "conservative": {"max_position": "2-3%", "entry_strategy": "Dollar-cost average over 3-6 months"},
        "moderate": {"max_position": "4-6%", "entry_strategy": "Split into 2-3 tranches"},
        "aggressive": {"max_position": "8-10%", "entry_strategy": "Can enter full position on dips"},
    }

    base = base_positions.get(risk_tolerance.lower(), base_positions["moderate"])

    # Reduce position for high volatility stocks
    warning = None
    if risk_rating in ["HIGH", "MODERATE-HIGH"]:
        warning = f"CAUTION: {symbol} has {risk_rating} volatility. Consider reducing position size by 30-50%."

    return {
        "symbol": symbol.upper(),
        "risk_tolerance": risk_tolerance,
        "stock_risk_rating": risk_rating,
        "recommended_position": base["max_position"],
        "entry_strategy": base["entry_strategy"],
        "volatility_warning": warning,
        "stop_loss": "Consider 15-20% stop-loss for risk management",
        "beta": volatility_data.get("beta", "N/A"),
        "disclaimer": "This is educational content, not personalized financial advice.",
        "data_source": "Position sizing with REAL volatility data",
    }


# =============================================================================
# Create Agent Instances (target-agnostic - no model_client specified)
# =============================================================================

# Market Analyst Agent
market_analyst = Agent(
    name="MarketAnalyst",
    instruction="""You are a market analyst specializing in stock analysis.
Use get_stock_data to fetch REAL current stock data from Yahoo Finance.
Use get_technical_analysis to get REAL calculated technical indicators (RSI, MACD, trends).
Provide clear, data-driven analysis with specific numbers and metrics.
Always mention that data is real-time from Yahoo Finance.""",
)
market_analyst.add_action_group(market_tools)

# News Researcher Agent
news_researcher = Agent(
    name="NewsResearcher",
    instruction="""You are a news researcher focused on financial news.
Use search_news to find REAL recent news articles via DuckDuckGo.
Use analyze_sentiment to analyze the overall sentiment of the headlines.
Report key headlines with their sources and the overall sentiment (bullish/bearish/neutral).
Always mention that news is real and current from DuckDuckGo search.""",
)
news_researcher.add_action_group(news_tools)

# Risk Analyst Agent
risk_analyst = Agent(
    name="RiskAnalyst",
    instruction="""You are a risk analysis specialist.
Use analyze_volatility to calculate REAL volatility metrics from historical price data.
Use get_position_recommendation to suggest position sizing based on real risk metrics.
Always emphasize the importance of risk management and that calculations use real market data.""",
)
risk_analyst.add_action_group(risk_tools)


# =============================================================================
# Investment Advisor Supervisor
# =============================================================================

agent = Supervisor(
    name="InvestmentAdvisor",
    instruction="""You are an investment research advisor coordinating specialized analysts.

Your team uses REAL DATA:
- MarketAnalyst: Gets REAL stock data from Yahoo Finance + calculated technical indicators
- NewsResearcher: Finds REAL news via DuckDuckGo search + sentiment analysis
- RiskAnalyst: Calculates REAL volatility metrics from historical price data

For each stock analysis request:
1. Delegate to ALL THREE agents IN PARALLEL:
   delegate(delegations=[
       {"agent_name": "MarketAnalyst", "task": "Analyze [SYMBOL] stock data and technicals"},
       {"agent_name": "NewsResearcher", "task": "Find and analyze news about [COMPANY]"},
       {"agent_name": "RiskAnalyst", "task": "Assess risk for [SYMBOL] and recommend position sizing"}
   ])
2. Synthesize their findings into a comprehensive analysis covering:
   - Current price and valuation metrics (REAL from Yahoo Finance)
   - Technical outlook (RSI, MACD, trend) (CALCULATED from real data)
   - News sentiment (REAL news from DuckDuckGo)
   - Risk assessment (CALCULATED from historical volatility)
   - Recommended strategy

Always mention that all data is REAL and current. Include sources.
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
    print("=" * 60)
    print("Investment Advisor - REAL DATA Edition")
    print("=" * 60)
    print(f"\nSupervisor: {agent.name}")
    print(f"Collaborators: {list(agent.collaborators.keys())}")
    print("\nData Sources:")
    print("  - Stock Data: Yahoo Finance (yfinance)")
    print("  - Technical Analysis: Calculated from Yahoo Finance historical data")
    print("  - News: DuckDuckGo Search")
    print("  - Volatility: Calculated from 1-year historical data")
    print("\nTools available:")
    for name, collab in agent.collaborators.items():
        print(f"  {name}:")
        for ag in collab._action_groups:
            for action in ag.get_actions():
                print(f"    - {action.name}: {action.description}")
