"""
Finnhub Data Provider - Backup source for market data.

IMPORTANT FREE TIER LIMITATIONS:
- /stock/candle (historical OHLC) requires PAID subscription
- /quote (real-time price) is available on FREE tier
- /stock/profile2 (company info) is available on FREE tier

This provider is useful for:
1. Health checks (verify connectivity)
2. Real-time price quotes
3. As a paid upgrade path for full historical data
"""
import requests
import pandas as pd
import time
from datetime import datetime, timedelta
import threading

import config

# Rate limiting
_last_call_time = 0
_call_lock = threading.Lock()
_calls_this_minute = 0
_minute_start = 0

def _rate_limit():
    """Enforce Finnhub rate limit of 60 calls per minute."""
    global _last_call_time, _calls_this_minute, _minute_start
    
    with _call_lock:
        current_time = time.time()
        
        # Reset counter if we're in a new minute
        if current_time - _minute_start > 60:
            _calls_this_minute = 0
            _minute_start = current_time
        
        # If we've hit the limit, wait
        if _calls_this_minute >= config.FINNHUB_RATE_LIMIT:
            sleep_time = 60 - (current_time - _minute_start) + 0.1
            if sleep_time > 0:
                print(f"[finnhub] Rate limit reached, waiting {sleep_time:.1f}s...")
                time.sleep(sleep_time)
            _calls_this_minute = 0
            _minute_start = time.time()
        
        _calls_this_minute += 1
        _last_call_time = time.time()

def _period_to_timestamps(period: str):
    """Convert yfinance-style period string to Unix timestamps."""
    now = datetime.now()
    
    period_map = {
        "1d": timedelta(days=1),
        "5d": timedelta(days=5),
        "1mo": timedelta(days=30),
        "3mo": timedelta(days=90),
        "6mo": timedelta(days=180),
        "1y": timedelta(days=365),
        "2y": timedelta(days=730),
        "5y": timedelta(days=1825),
    }
    
    delta = period_map.get(period, timedelta(days=180))  # Default to 6mo
    start = now - delta
    
    return int(start.timestamp()), int(now.timestamp())

def fetch_quote(ticker: str) -> dict:
    """
    Fetch real-time quote from Finnhub (FREE TIER).
    
    Returns dict with keys: c (current), d (change), dp (change %), h (high), l (low), o (open), pc (prev close)
    """
    if not config.FINNHUB_API_KEY:
        return {}
    
    _rate_limit()
    
    url = f"{config.FINNHUB_BASE_URL}/quote"
    params = {"symbol": ticker.upper(), "token": config.FINNHUB_API_KEY}
    
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("c", 0) > 0:  # Valid if current price exists
                return {
                    "price": data["c"],
                    "change": data.get("d", 0),
                    "change_pct": data.get("dp", 0),
                    "high": data.get("h", 0),
                    "low": data.get("l", 0),
                    "open": data.get("o", 0),
                    "prev_close": data.get("pc", 0),
                    "timestamp": data.get("t", 0)
                }
        return {}
    except Exception as e:
        print(f"[finnhub] Quote error for {ticker}: {e}")
        return {}

def fetch_candles(ticker: str, period: str = "6mo", resolution: str = "D") -> pd.DataFrame:
    """
    Fetch OHLCV candle data from Finnhub.
    
    ⚠️ REQUIRES PAID SUBSCRIPTION - Free tier returns 403 Forbidden for US stocks.
    
    This function is kept for users who upgrade to paid Finnhub plans.
    For free tier, use fetch_quote() instead for real-time prices.
    """
    if not config.FINNHUB_API_KEY:
        print("[finnhub] No API key configured")
        return pd.DataFrame()
    
    _rate_limit()
    
    from_ts, to_ts = _period_to_timestamps(period)
    
    url = f"{config.FINNHUB_BASE_URL}/stock/candle"
    params = {
        "symbol": ticker.upper(),
        "resolution": resolution,
        "from": from_ts,
        "to": to_ts,
        "token": config.FINNHUB_API_KEY
    }
    
    try:
        print(f"[finnhub] Fetching candles for {ticker} ({period}, {resolution})")
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 403:
            print(f"[finnhub] 403 Forbidden - /stock/candle requires PAID subscription")
            return pd.DataFrame()
        
        if response.status_code == 429:
            print(f"[finnhub] Rate limited (429), waiting 60s...")
            time.sleep(60)
            return fetch_candles(ticker, period, resolution)  # Retry
        
        if response.status_code != 200:
            print(f"[finnhub] HTTP {response.status_code} for {ticker}")
            return pd.DataFrame()
        
        data = response.json()
        
        if data.get("s") == "no_data" or "c" not in data:
            print(f"[finnhub] No data for {ticker}")
            return pd.DataFrame()
        
        # Convert to yfinance-compatible DataFrame
        df = pd.DataFrame({
            "Open": data["o"],
            "High": data["h"],
            "Low": data["l"],
            "Close": data["c"],
            "Volume": data["v"],
        })
        
        df.index = pd.to_datetime(data["t"], unit="s")
        df.index.name = "Date"
        df["Adj Close"] = df["Close"]
        
        return df
        
    except Exception as e:
        print(f"[finnhub] Error for {ticker}: {e}")
        return pd.DataFrame()

def fetch_batch_quotes(tickers: list) -> dict:
    """
    Fetch real-time quotes for multiple tickers (FREE TIER).
    
    Returns dict mapping ticker -> quote data
    """
    results = {}
    for ticker in tickers:
        quote = fetch_quote(ticker)
        if quote:
            results[ticker] = quote
    return results

def check_connectivity() -> dict:
    """Check if Finnhub API is reachable and key is valid."""
    if not config.FINNHUB_API_KEY:
        return {"status": "disabled", "message": "No API key configured"}
    
    try:
        _rate_limit()
        
        # Use quote endpoint (free tier compatible)
        url = f"{config.FINNHUB_BASE_URL}/quote"
        params = {"symbol": "AAPL", "token": config.FINNHUB_API_KEY}
        
        start = time.time()
        response = requests.get(url, params=params, timeout=5)
        latency = (time.time() - start) * 1000
        
        if response.status_code == 200:
            data = response.json()
            if data.get("c", 0) > 0:
                return {
                    "status": "ok",
                    "message": f"Connected (AAPL: ${data['c']})",
                    "latency_ms": round(latency, 2),
                    "tier": "free (quotes only)"
                }
            else:
                return {"status": "warning", "message": "Connected but no quote data"}
        elif response.status_code == 401:
            return {"status": "error", "message": "Invalid API key"}
        elif response.status_code == 429:
            return {"status": "warning", "message": "Rate limited"}
        else:
            return {"status": "error", "message": f"HTTP {response.status_code}"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}
