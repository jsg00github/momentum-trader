
import concurrent.futures
import time
import random
import yfinance as yf
import pandas as pd
from typing import List, Optional
import os
import sys

# Local imports
import screener
import scoring
import cache

# Global progress tracking
SCAN_STATUS = {
    "total": 0, 
    "current": 0, 
    "is_running": False
}

def get_scan_status():
    return SCAN_STATUS

def process_ticker(ticker, use_cache=True, strategy="rally_3m"):
    """
    Process a single ticker. 
    Moved from main.py to allow usage in background tasks.
    """
    c = cache.get_cache() if use_cache else None
    
    # Reduced retries for speed. If a ticker fails once during a bulk scan, we just skip it.
    max_retries = 1 
    for attempt in range(max_retries):
        try:
            # Try to get from cache first
            df = None
            if c:
                df = c.get(ticker, screener.PERIOD, screener.INTERVAL)
            
            # If not in cache, download
            if df is None:
                period = screener.PERIOD
                if strategy == "weekly_rsi":
                    period = "1y" 

                df = yf.download(ticker, period=period, interval=screener.INTERVAL, 
                               progress=False, auto_adjust=False, threads=False)
                
                if c and df is not None and not df.empty:
                    c.set(ticker, screener.PERIOD, screener.INTERVAL, df)
            
            if df is None or df.empty:
                return None
            
            # Handle MultiIndex
            if isinstance(df.columns, pd.MultiIndex):
                try:
                     # Check if ticker is in level 1
                     if ticker in df.columns.get_level_values(1):
                         df = df.xs(ticker, axis=1, level=1)
                     else:
                         return None
                except:
                     return None

            if strategy == "weekly_rsi":
                result = screener.scan_rsi_crossover(df)
            else:
                result = screener.compute_3m_pattern(df)
            
            if result:
                result["ticker"] = ticker
                return result
                
            return None
            
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Error processing {ticker}: {e}")
            else:
                time.sleep((2 ** attempt) + random.random())
                
    return None

def run_market_scan(limit=1000, strategy="rally_3m"):
    """
    Runs a full market scan using the SEC ticker universe.
    """
    tickers = screener.get_sec_tickers()
    if not tickers:
        return {"error": "No tickers found"}
        
    subset = tickers[:limit]
    print(f"Scanning {len(subset)} tickers with strategy {strategy}...")
    
    # Init Progress
    SCAN_STATUS["total"] = len(subset)
    SCAN_STATUS["current"] = 0
    SCAN_STATUS["is_running"] = True

    # Calculate SPY RS
    spy_ret_3m = 0
    try:
        spy_df = yf.download("SPY", period="6mo", interval="1d", progress=False, auto_adjust=False)
        if isinstance(spy_df.columns, pd.MultiIndex):
            if "SPY" in spy_df.columns.get_level_values(1):
                spy_df = spy_df.xs("SPY", axis=1, level=1)
        
        if not spy_df.empty:
            closes = spy_df["Close"].values
            if len(closes) > 63:
                spy_ret_3m = ((closes[-1] / closes[-1-63]) - 1.0) * 100
    except Exception:
        pass

    # Batch Processing
    # We process tickers in chunks to maintain stability and avoid memory leaks
    batch_size = 50
    results = []
    
    total_batches = (len(subset) + batch_size - 1) // batch_size
    print(f"Processing {len(subset)} tickers in {total_batches} batches...")
    
    for i in range(0, len(subset), batch_size):
        batch = subset[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        
        # Prepare batch string for display
        batch_tickers_sample = ", ".join(batch[:4]) + "..." if len(batch) > 4 else ", ".join(batch)
        print(f"Starting Batch {batch_num}/{total_batches} ({len(batch)} tickers): {batch_tickers_sample}")
        
        # Update Status with details
        SCAN_STATUS["last_ticker"] = f"Batch {batch_num}/{total_batches}: {batch_tickers_sample}"

        # Reverting to ThreadPoolExecutor because yf.download(bulk) was hanging on Windows/Network.
        # This method is slower but proven robust.
        # NON-BLOCKING EXECUTOR PATTERN
        # We manually manage the executor to ensure we can force shutdown(wait=False)
        # if threads hang. The 'with' context manager would block indefinitely.
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)
        future_to_ticker = {}
        try:
            future_to_ticker = {executor.submit(process_ticker, ticker, True, strategy): ticker for ticker in batch}
            
            # 45 second timeout for the entire batch
            for future in concurrent.futures.as_completed(future_to_ticker, timeout=45):
                SCAN_STATUS["current"] += 1
                ticker = future_to_ticker[future]
                try:
                    res = future.result()
                    if res:
                        score = scoring.calculate_score(res)
                        res["score"] = score
                        res["grade"] = scoring.score_to_grade(score)
                        res["rs_spy"] = round(res["ret_3m_pct"] - spy_ret_3m, 2)
                        results.append(res)
                except Exception as exc:
                    print(f"Ticker {ticker} exception: {exc}")
                    
        except concurrent.futures.TimeoutError:
            print(f"Batch {batch_num} timed out! Kicking zombie threads...")
            # This is the critical fix: cancel pending futures and do NOT wait for zombies
            for f in future_to_ticker:
                f.cancel()
            
        finally:
            # wait=False ensures we don't hang if a thread is blocked in C-level socket
            executor.shutdown(wait=False)
        
        # Small pause between batches
        time.sleep(0.5)
        # Force garbage collection
        import gc
        gc.collect()
            
    # Sort by Score
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    SCAN_STATUS["is_running"] = False
    
    return {
        "results": results, 
        "scanned": len(subset),
        "spy_ret_3m": round(spy_ret_3m, 2)
    }
