"""
News Module - Fetch market news from Finnhub API.

Finnhub /company-news endpoint is FREE tier compatible.
Returns headlines, summaries, source, and sentiment for portfolio tickers.
"""
import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import threading

import config

# Rate limiting (shared with finnhub_provider)
_news_cache = {}
_cache_ttl = 300  # 5 minutes

def get_news_for_ticker(ticker: str, days: int = 3) -> List[Dict]:
    """
    Fetch company news from Finnhub for a single ticker.
    
    Returns list of news items:
    - headline: Main title
    - summary: Short description
    - source: Source name (e.g., "Yahoo", "MarketWatch")
    - datetime: Unix timestamp
    - url: Link to full article
    - related: Ticker symbol
    """
    if not config.FINNHUB_API_KEY:
        return []
    
    # Check cache
    cache_key = f"{ticker}_{days}"
    if cache_key in _news_cache:
        cached_time, cached_data = _news_cache[cache_key]
        if time.time() - cached_time < _cache_ttl:
            return cached_data
    
    try:
        today = datetime.now()
        from_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        to_date = today.strftime("%Y-%m-%d")
        
        url = f"{config.FINNHUB_BASE_URL}/company-news"
        params = {
            "symbol": ticker.upper(),
            "from": from_date,
            "to": to_date,
            "token": config.FINNHUB_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            
            # Parse and filter news items
            news_items = []
            for item in data[:5]:  # Limit to 5 items per ticker
                news_items.append({
                    "ticker": ticker.upper(),
                    "headline": item.get("headline", ""),
                    "summary": item.get("summary", "")[:200] + "..." if len(item.get("summary", "")) > 200 else item.get("summary", ""),
                    "source": item.get("source", ""),
                    "datetime": item.get("datetime", 0),
                    "url": item.get("url", ""),
                    "image": item.get("image", ""),
                    "sentiment": analyze_headline_sentiment(item.get("headline", ""))
                })
            
            # Cache result
            _news_cache[cache_key] = (time.time(), news_items)
            return news_items
            
        return []
        
    except Exception as e:
        print(f"[news] Error fetching news for {ticker}: {e}")
        return []


def get_news_for_tickers(tickers: List[str], days: int = 3, max_items: int = 10) -> List[Dict]:
    """
    Fetch news for multiple tickers and combine results.
    Sorted by datetime (newest first), limited to max_items.
    """
    if not tickers:
        return []
    
    all_news = []
    
    # Limit to first 5 tickers to avoid rate limiting
    for ticker in tickers[:5]:
        news = get_news_for_ticker(ticker, days)
        all_news.extend(news)
    
    # Sort by datetime (newest first) and limit
    all_news.sort(key=lambda x: x.get("datetime", 0), reverse=True)
    return all_news[:max_items]


def get_market_headlines(days: int = 1) -> List[Dict]:
    """
    Fetch general market news using major tickers as proxy.
    Returns top headlines from SPY, QQQ, and major market movers.
    """
    market_tickers = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA"]
    return get_news_for_tickers(market_tickers, days=days, max_items=5)


def analyze_headline_sentiment(headline: str) -> str:
    """
    Simple keyword-based sentiment analysis.
    Returns: 'bullish', 'bearish', or 'neutral'
    """
    headline_lower = headline.lower()
    
    bullish_keywords = [
        "surge", "soar", "rally", "gain", "jump", "beat", "record", "high", 
        "upgrade", "buy", "bullish", "growth", "profit", "revenue beat",
        "outperform", "strong", "positive", "boost", "rises", "climbs"
    ]
    
    bearish_keywords = [
        "drop", "fall", "crash", "plunge", "decline", "miss", "loss", "cut",
        "downgrade", "sell", "bearish", "warning", "concern", "risk", "weakness",
        "slump", "tumble", "sinks", "slides", "fear", "recession"
    ]
    
    bullish_count = sum(1 for kw in bullish_keywords if kw in headline_lower)
    bearish_count = sum(1 for kw in bearish_keywords if kw in headline_lower)
    
    if bullish_count > bearish_count:
        return "bullish"
    elif bearish_count > bullish_count:
        return "bearish"
    else:
        return "neutral"


def format_time_ago(timestamp: int) -> str:
    """Convert Unix timestamp to human-readable 'time ago' string."""
    if not timestamp:
        return ""
    
    now = time.time()
    diff = now - timestamp
    
    if diff < 3600:
        return f"{int(diff / 60)}m ago"
    elif diff < 86400:
        return f"{int(diff / 3600)}h ago"
    elif diff < 604800:
        return f"{int(diff / 86400)}d ago"
    else:
        return datetime.fromtimestamp(timestamp).strftime("%b %d")
