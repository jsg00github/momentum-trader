
import concurrent.futures
import time
import random
import yfinance as yf
import pandas as pd
from typing import List, Optional
import os
import sys
import numpy as np
from datetime import datetime

# Local imports
import screener
import scoring
import cache
import market_data

# Global progress tracking
SCAN_STATUS = {
    "total": 0, 
    "current": 0, 
    "is_running": False,
    "last_run": None,
    "results": [],
    "last_ticker": ""
}

def get_scan_status():
    return SCAN_STATUS

def clean_type(val):
    """
    Recursively convert numpy types and non-JSON compliant floats (NaN, Inf) 
    to standard Python types or None. Also handles basic cleaning of objects.
    """
    if val is None:
        return None
        
    if isinstance(val, dict):
        return {str(k): clean_type(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple)):
        return [clean_type(v) for v in val]
    elif isinstance(val, (np.float64, np.float32, np.float16)):
        fval = float(val)
        return fval if np.isfinite(fval) else None
    elif isinstance(val, (np.int64, np.int32, np.int16, np.int8)):
        return int(val)
    elif isinstance(val, float):
        return val if np.isfinite(val) else None
    elif isinstance(val, (int, str, bool)):
        return val
    elif isinstance(val, np.ndarray):
        return clean_type(val.tolist())
    # Failsafe for anything else: convert to string to avoid serialization errors
    return str(val)

def process_ticker(ticker, data_df=None, use_cache=True, strategy="rally_3m"):
    """
    Process a single ticker. 
    If data_df is provided (pre-loaded), it skipping downloading.
    """
    try:
        df = data_df
        
        # If no pre-loaded data, try cache or download
        if df is None:
            c = cache.get_cache() if use_cache else None
            if c:
                df = c.get(ticker, screener.PERIOD, screener.INTERVAL)
            
            if df is None:
                period = screener.PERIOD
                if strategy == "weekly_rsi":
                    period = "1y" 
                df = market_data.safe_yf_download(ticker, period=period, auto_adjust=False)
                if c and df is not None and not df.empty:
                    c.set(ticker, screener.PERIOD, screener.INTERVAL, df)
        
        if df is None or df.empty:
            return None
        
        # Robust MultiIndex / Single Ticker Extract logic
        # If it came from a batch download, it's likely MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            try:
                # Find the ticker in the columns levels
                if ticker in df.columns.get_level_values(1):
                    df = df.xs(ticker, axis=1, level=1)
                elif ticker in df.columns.get_level_values(0):
                    df = df.xs(ticker, axis=1, level=0)
            except Exception as e:
                # Fallback: find columns that start with or contain ticker if flattening failed
                df.columns = [str(c[0]) if isinstance(c, tuple) else str(c) for c in df.columns]

        # Final cleanup: ensure we have standard Open/High/Low/Close columns
        if not all(col in df.columns for col in ['Open', 'High', 'Low', 'Close']):
            # This might happen if indexing returned a series or weird format
            pass

        if strategy == "weekly_rsi":
            result = screener.scan_rsi_crossover(df)
        else:
            result = screener.compute_3m_pattern(df)
        
        if result:
            result["ticker"] = ticker
            result["sector"] = market_data.get_ticker_sector(ticker)
            return result
            
        return None
            
    except Exception as e:
        print(f"Error processing {ticker} in process_ticker: {e}")
        return None

def run_market_scan(limit=1000, strategy="weekly_rsi"):
    """
    Runs a full market scan using the SEC ticker universe.
    Optimized with cache-first approach to avoid Yahoo rate limiting.
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
        spy_df = market_data.safe_yf_download("SPY", period="6mo", auto_adjust=False)
        if not spy_df.empty:
            if isinstance(spy_df.columns, pd.MultiIndex):
                if "SPY" in spy_df.columns.get_level_values(1):
                    spy_df = spy_df.xs("SPY", axis=1, level=1)
                else:
                    spy_df.columns = [c[0] for c in spy_df.columns]
            
            if "Close" in spy_df.columns:
                closes = spy_df["Close"].values
                if len(closes) > 63:
                    val = (closes[-1] / closes[-1-63]) - 1.0
                    spy_ret_3m = float(val) * 100.0
    except Exception as e:
        print(f"Error calculating SPY RS: {e}")

    # PHASE 1: Check cache for all tickers first
    c = cache.get_cache()
    period = "6mo" if strategy == "weekly_rsi" else screener.PERIOD
    cached_data, to_download = c.batch_check(subset, period, "1d", max_age_hours=12)
    
    print(f"📦 Cache: {len(cached_data)} tickers cached, {len(to_download)} need download")
    SCAN_STATUS["last_ticker"] = f"Cache: {len(cached_data)} cached, downloading {len(to_download)}..."

    results = []
    
    # PHASE 2: Process cached tickers immediately (fast!)
    if cached_data:
        print(f"⚡ Processing {len(cached_data)} cached tickers...")
        for ticker, df in cached_data.items():
            SCAN_STATUS["current"] += 1
            SCAN_STATUS["last_ticker"] = f"[CACHE] {ticker}"
            try:
                res = process_ticker(ticker, df, True, strategy)
                if res:
                    score = scoring.calculate_score(res)
                    res["score"] = score
                    res["grade"] = scoring.score_to_grade(score)
                    res["rs_spy"] = round(float(res.get("ret_3m_pct", 0)) - float(spy_ret_3m), 2)
                    results.append(res)
            except Exception as e:
                print(f"Error processing cached {ticker}: {e}")
    
    # PHASE 3: Download missing tickers in small batches with delays
    if to_download:
        batch_size = 25  # Smaller batches to avoid 429
        total_batches = (len(to_download) + batch_size - 1) // batch_size
        
        for i in range(0, len(to_download), batch_size):
            batch = to_download[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            print(f"📡 Downloading Batch {batch_num}/{total_batches} ({len(batch)} tickers)...")
            SCAN_STATUS["last_ticker"] = f"Batch {batch_num}/{total_batches}: {', '.join(batch[:3])}..."

            try:
                batch_df = market_data.safe_yf_download(batch, period=period, auto_adjust=False, threads=True)
                
                if batch_df is not None and not batch_df.empty:
                    for ticker in batch:
                        SCAN_STATUS["current"] += 1
                        SCAN_STATUS["last_ticker"] = f"[LIVE] {ticker}"
                        
                        ticker_df = None
                        try:
                            if isinstance(batch_df.columns, pd.MultiIndex):
                                if ticker in batch_df.columns.get_level_values(1):
                                    ticker_df = batch_df.xs(ticker, axis=1, level=1)
                            elif ticker in batch_df.columns:
                                ticker_df = batch_df
                        except Exception:
                            pass

                        if ticker_df is not None:
                            res = process_ticker(ticker, ticker_df, True, strategy)
                            if res:
                                score = scoring.calculate_score(res)
                                res["score"] = score
                                res["grade"] = scoring.score_to_grade(score)
                                res["rs_spy"] = round(float(res.get("ret_3m_pct", 0)) - float(spy_ret_3m), 2)
                                results.append(res)
                else:
                    # If batch download failed, increment counters anyway
                    SCAN_STATUS["current"] += len(batch)
                    print(f"⚠️ Batch {batch_num} returned empty, skipping...")
                    
            except Exception as e:
                SCAN_STATUS["current"] += len(batch)
                print(f"❌ Batch {batch_num} failed: {e}")
            
            # Rate limiting delay between batches
            if batch_num < total_batches:
                time.sleep(1.5)  # 1.5 second delay between batches
                
            # Garbage collection
            import gc
            gc.collect()
            
    # Sort by Stars (DESC) and then by Score (DESC)
    results.sort(key=lambda x: (x.get("stars", 0), x.get("score", 0)), reverse=True)
    
    SCAN_STATUS["is_running"] = False
    SCAN_STATUS["results"] = clean_type(results)
    SCAN_STATUS["last_run"] = datetime.now().isoformat()
    SCAN_STATUS["spy_ret_3m"] = clean_type(round(spy_ret_3m, 2))
    
    print(f"✅ Scan complete! Found {len(results)} results from {len(subset)} tickers")
    
    return {
        "results": SCAN_STATUS["results"], 
        "scanned": len(subset),
        "spy_ret_3m": SCAN_STATUS["spy_ret_3m"],
        "from_cache": len(cached_data),
        "from_download": len(to_download)
    }
