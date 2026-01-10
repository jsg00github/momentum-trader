"""
Sharpe Ratio Portfolio Builder
Builds monthly portfolios based on Sharpe Ratio > 2 and P/E filters.
Reuses cached data from Weekly RSI Scanner to avoid redundant API calls.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
import cache
import market_data

# Sharpe calculation constants
TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.04  # 4% annual risk-free rate (adjustable)


def calculate_sharpe(df: pd.DataFrame, risk_free_annual: float = RISK_FREE_RATE) -> Optional[float]:
    """
    Calculate annualized Sharpe Ratio from price DataFrame.
    Uses daily returns and annualizes.
    """
    if df is None or df.empty:
        return None
    
    # Normalize if MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    
    if 'Close' not in df.columns:
        return None
    
    close = df['Close']
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    
    close = close.dropna()
    if len(close) < 60:  # Need at least ~3 months of data
        return None
    
    # Calculate daily returns
    daily_returns = close.pct_change().dropna()
    
    if len(daily_returns) < 50:
        return None
    
    # Annualized metrics
    mean_daily_return = daily_returns.mean()
    std_daily_return = daily_returns.std()
    
    if std_daily_return == 0 or pd.isna(std_daily_return):
        return None
    
    # Annualized Sharpe (without risk-free for simplicity, or subtract daily risk-free)
    daily_rf = risk_free_annual / TRADING_DAYS_PER_YEAR
    excess_return = mean_daily_return - daily_rf
    
    sharpe = (excess_return * TRADING_DAYS_PER_YEAR) / (std_daily_return * np.sqrt(TRADING_DAYS_PER_YEAR))
    
    return round(float(sharpe), 3)


# In-memory simple cache for fundamentals to speed up repeated scans
FUNDAMENTALS_CACHE = {}

def get_fundamentals(ticker: str) -> Dict:
    """
    Get fundamental data (P/E, Market Cap, etc.) from yfinance.
    Uses in-memory cache to prevent redundant network calls.
    """
    if ticker in FUNDAMENTALS_CACHE:
        return FUNDAMENTALS_CACHE[ticker]
        
    try:
        t = yf.Ticker(ticker)
        info = t.info
        data = {
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "market_cap": info.get("marketCap", 0),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "dividend_yield": info.get("dividendYield", 0),
            "beta": info.get("beta", 1.0),
            "name": info.get("shortName", ticker)
        }
        FUNDAMENTALS_CACHE[ticker] = data
        return data
    except Exception as e:
        print(f"Error getting fundamentals for {ticker}: {e}")
        return {}


def scan_sharpe_portfolio(
    min_sharpe: float = 1.5,
    max_pe: float = 50.0,
    min_pe: float = 0.0,
    min_market_cap: float = 1_000_000_000,  # $1B
    max_results: int = 50
) -> Dict:
    """
    Scans cached tickers for high Sharpe ratio stocks.
    Reuses data from Weekly RSI Scanner cache!
    """
    print(f"📊 Sharpe Portfolio Scan: min_sharpe={min_sharpe}, PE={min_pe}-{max_pe}")
    
    # Get cached data from Weekly RSI Scanner
    c = cache.get_cache()
    
    # Get cache statistics to see what's available
    stats = c.stats()
    print(f"📦 Cache has {stats['total_entries']} entries, {stats['fresh_24h']} fresh")
    
    if stats['total_entries'] == 0:
        return {
            "error": "No cached data available. Run Weekly RSI Scanner first.",
            "results": [],
            "scanned": 0
        }
    
    # Get all cached tickers with fresh data
    import sqlite3
    from datetime import timedelta
    
    conn = sqlite3.connect(c.db_path)
    cursor = conn.cursor()
    
    # Get tickers cached in last 24 hours
    cutoff = datetime.now() - timedelta(hours=24)
    cursor.execute("""
        SELECT DISTINCT ticker FROM price_cache 
        WHERE date_cached > ?
    """, (cutoff,))
    
    cached_tickers = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    print(f"🔍 Scanning {len(cached_tickers)} cached tickers...")
    
    results = []
    scanned = 0
    
    
    # PHASE 1: Fast Filter (Sharpe Only) - No Network Calls
    candidates = []
    
    for ticker in cached_tickers:
        scanned += 1
        
        # Get cached price data
        df = c.get(ticker, "6mo", "1d", max_age_hours=24)
        if df is None:
            df = c.get(ticker, "1y", "1d", max_age_hours=24)
        
        if df is None or df.empty:
            continue
        
        # Calculate Sharpe
        sharpe = calculate_sharpe(df)
        if sharpe is None or sharpe < min_sharpe:
            continue
            
        # Get current price
        if isinstance(df.columns, pd.MultiIndex):
            close_col = df['Close']
            if isinstance(close_col, pd.DataFrame):
                close_col = close_col.iloc[:, 0]
        else:
            close_col = df['Close']
        
        current_price = float(close_col.dropna().iloc[-1]) if not close_col.empty else 0
        
        candidates.append({
            "ticker": ticker,
            "sharpe": sharpe,
            "price": round(current_price, 2)
        })

    # Sort candidates by Sharpe DESC
    candidates.sort(key=lambda x: x['sharpe'], reverse=True)
    
    print(f"⚡ Found {len(candidates)} candidates with Sharpe > {min_sharpe}. Fetching fundamentals for top {max_results}...")
    
    # PHASE 2: Heavy Filter (Fundamentals) - Network Calls
    # Only process top N candidates to save time
    
    results = []
    
    # If we have too many candidates, we only process the top ones + buffer
    # Buffer allows for some to be filtered out by P/E
    candidates_to_process = candidates[:max_results * 3] 
    
    for cand in candidates_to_process:
        if len(results) >= max_results:
            break
            
        ticker = cand["ticker"]
        
        # Get fundamentals (P/E filter)
        fundamentals = get_fundamentals(ticker)
        pe = fundamentals.get("pe_ratio")
        market_cap = fundamentals.get("market_cap", 0)
        
        # Apply filters
        # Safely convert P/E to float if needed
        pe_filtered = False
        if pe is not None:
            try:
                pe_float = float(pe)
                if pe_float < min_pe or pe_float > max_pe:
                    pe_filtered = True
            except (ValueError, TypeError):
                # If PE is not a valid number, ignore it
                pass 
        
        if pe_filtered:
            continue
        
        if market_cap is not None and market_cap < min_market_cap:
            continue
            
        results.append({
            "ticker": ticker,
            "sharpe": cand["sharpe"],
            "pe_ratio": pe,
            "market_cap": market_cap,
            "sector": fundamentals.get("sector", "Unknown"),
            "name": fundamentals.get("name", ticker),
            "price": cand["price"],
            "beta": fundamentals.get("beta", 1.0)
        })
    
    print(f"✅ Final Results: {len(results)} stocks")
    
    # Add Outlooks
    for res in results:
        res['outlook'] = generate_outlook(res)

    return {
        "results": results,
        "scanned": scanned,
        "filters": {
            "min_sharpe": min_sharpe,
            "pe_range": f"{min_pe}-{max_pe}",
            "min_market_cap": min_market_cap
        },
        "scan_time": datetime.now().isoformat()
    }


def generate_outlook(data: Dict) -> str:
    """Generates a heuristic 3-6 month outlook based on metrics."""
    sharpe = data.get("sharpe", 0)
    pe = data.get("pe_ratio")
    beta = data.get("beta", 1.0)
    
    outlook = []
    
    if sharpe > 2.0:
        outlook.append("Expect strong trend continuation due to exceptional risk-adjusted momentum.")
    elif sharpe > 1.5:
        outlook.append("Steady accumulation expected; stock is efficiently outperforming volatility.")
        
    if beta < 0.8:
        outlook.append("Defensive play likely to hold value during market choppiness.")
    elif beta > 1.3:
        outlook.append("High beta suggests potential for outsized gains if market remains bullish.")
        
    if pe and isinstance(pe, (int, float)):
        if pe < 15:
            outlook.append("Undervalued levels provide a safety margin for medium-term hold.")
        elif pe > 40:
            outlook.append("High growth expectations priced in; momentum dependent on earnings beats.")
            
    return " ".join(outlook) if outlook else "Neutral outlook based on available metrics."


def build_equal_weight_portfolio(candidates: List[Dict], max_positions: int = 10, strategy: str = 'undervalued') -> Dict:
    """
    Builds an equal-weighted portfolio from top candidates.
    Strategies:
    - 'sharpe': Top Sharpe only.
    - 'undervalued': Strict PE < 20, then Top Sharpe.
    """
    if not candidates:
        return {"positions": [], "weight_per_position": 0}
    
    filtered_candidates = candidates.copy()
    
    if strategy == 'undervalued':
        # Strict Value Filter: Must be profitable (PE > 0) and Cheap (PE < 20)
        filtered_candidates = [c for c in filtered_candidates if c.get('pe_ratio') and 0 < c.get('pe_ratio') < 20]
        # Sort by Sharpe Desc
        filtered_candidates.sort(key=lambda x: x.get('sharpe', 0), reverse=True)
    else:
        # Default Sharpe Sort
        filtered_candidates.sort(key=lambda x: x.get('sharpe', 0), reverse=True)
    
    # Take top N
    selected = filtered_candidates[:max_positions]
    
    if not selected and strategy == 'undervalued':
         # Fallback to Sharpe if absolutely no value stocks found
         print("⚠️ Value strategy yielded 0 results. Falling back to Sharpe.")
         selected = candidates[:max_positions]
         strategy = "sharpe (fallback)"
    
    if not selected:
         return {"positions": [], "total_positions": 0, "strategy": strategy}

    weight = round(100.0 / len(selected), 2)
    
    positions = []
    for stock in selected:
        positions.append({
            "ticker": stock["ticker"],
            "name": stock.get("name", stock["ticker"]),
            "sharpe": stock.get("sharpe", 0),
            "weight": weight,
            "price": stock.get("price", 0),
            "sector": stock.get("sector", "Unknown"),
            "pe_ratio": stock.get("pe_ratio"),
            "outlook": stock.get("outlook", "N/A")
        })
    
    return {
        "positions": positions,
        "weight_per_position": weight,
        "total_positions": len(positions),
        "portfolio_date": date.today().isoformat(),
        "strategy": f"Equal Weight ({strategy})"
    }
