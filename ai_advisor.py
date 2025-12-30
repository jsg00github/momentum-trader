import yfinance as yf
import pandas as pd
import numpy as np
import concurrent.futures
import json
import os
import time
import threading

# Directory setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CACHE_FILE = os.path.join(DATA_DIR, "recs_cache.json")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Universe of liquid stocks to analyze
UNIVERSE = [
    "NVDA", "TSLA", "AAPL", "AMD", "MSFT", "AMZN", "GOOGL", "META", 
    "NFLX", "COIN", "MARA", "PLTR", "SOFI", "SHOP", "SNOW",
    "JPM", "BAC", "XOM", "CVX", "KO", "PEP", "MCD", "DIS"
]

# Global Cache State
ACTIVE_RECS = {"Aggressive": [], "Moderate": [], "Safe": [], "last_scan": 0, "is_scanning": False}

def load_cache():
    global ACTIVE_RECS
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                ACTIVE_RECS.update(data)
        except Exception as e:
            print(f"Error loading recs cache: {e}")

def save_cache():
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(ACTIVE_RECS, f, indent=4)
    except Exception as e:
        print(f"Error saving recs cache: {e}")

def analyze_ticker(ticker):
    try:
        data = yf.download(ticker, period="6mo", interval="1d", progress=False, auto_adjust=False, timeout=10)
        if len(data) < 50: return None

        # Handle MultiIndex
        if isinstance(data.columns, pd.MultiIndex):
            close = data['Close'][ticker]
            high = data['High'][ticker]
            low = data['Low'][ticker]
        else:
            close, high, low = data['Close'], data['High'], data['Low']

        last_price = float(close.iloc[-1])
        ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
        ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
        sma200 = float(close.rolling(window=200).mean().iloc[-1]) if len(close) > 200 else ema50 * 0.9
        
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
        atr_pct = (tr.rolling(window=14).mean().iloc[-1] / last_price) * 100
        
        profile, score, rationale = None, 0, []

        # 1. Aggressive (High Mom, High Vol)
        if last_price > ema21 * 0.98 and atr_pct > 1.5 and rsi > 50:
            profile = "Aggressive"
            score = 80 + (rsi - 50) if rsi < 80 else 95
            rationale = ["Strong Momentum", f"High Volatility ({atr_pct:.1f}%)"]
        
        # 2. Moderate (Steady Growth)
        elif last_price > ema50 * 0.98 and atr_pct < 3.0 and rsi > 40:
            profile = "Moderate"
            score = 70 + (rsi - 40)
            rationale = ["Steady Trend", "Standard Volatility"]

        # 3. Safe (Value/Dip)
        elif rsi < 45 or abs(last_price - sma200)/last_price < 0.08:
            profile = "Safe"
            score = 60 + (45 - rsi)
            rationale = ["Support Zone", "Defensive / Value"]
            
        if profile:
            return {
                "ticker": ticker, "profile": profile, "score": round(score, 1),
                "rationale": rationale,
                "metrics": {"price": round(last_price, 2), "rsi": round(rsi, 1), "atr_pct": round(atr_pct, 2)}
            }
        return None
    except Exception: return None

def update_recommendations_worker():
    global ACTIVE_RECS
    if ACTIVE_RECS["is_scanning"]: return
    ACTIVE_RECS["is_scanning"] = True
    print("\n>>> AI ADVISOR BACKGROUND SCAN STARTED <<<")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(analyze_ticker, UNIVERSE))
    
    all_candidates = [r for r in results if r]
    
    # --- STICKY LOGIC ---
    for cat in ["Aggressive", "Moderate", "Safe"]:
        current_tickers = [item["ticker"] for item in ACTIVE_RECS[cat]]
        new_validated = []
        
        # 1. Keep current members IF they still fit the profile (even if score dropped a bit)
        for ticker in current_tickers:
            match = next((c for c in all_candidates if c["ticker"] == ticker and c["profile"] == cat), None)
            if match:
                new_validated.append(match)
        
        # 2. Fill remaining slots from new candidates (sorted by score)
        other_candidates = [c for c in all_candidates if c["profile"] == cat and c["ticker"] not in [v["ticker"] for v in new_validated]]
        other_candidates.sort(key=lambda x: x['score'], reverse=True)
        
        combined = (new_validated + other_candidates)[:3]
        ACTIVE_RECS[cat] = combined

    ACTIVE_RECS["last_scan"] = time.time()
    ACTIVE_RECS["is_scanning"] = False
    save_cache()
    print(">>> AI ADVISOR BATCH UPDATE COMPLETE <<<")

def get_recommendations():
    global ACTIVE_RECS
    
    # If first time, load from file
    if not ACTIVE_RECS["Aggressive"] and not ACTIVE_RECS["Moderate"] and not ACTIVE_RECS["Safe"]:
        load_cache()
    
    # Trigger background scan if stale (15 mins) or empty
    is_empty = not ACTIVE_RECS["Aggressive"] and not ACTIVE_RECS["Moderate"] and not ACTIVE_RECS["Safe"]
    stale = (time.time() - ACTIVE_RECS["last_scan"]) > 900
    if (stale or is_empty) and not ACTIVE_RECS["is_scanning"]:
        threading.Thread(target=update_recommendations_worker).start()
        
    return {k: v for k, v in ACTIVE_RECS.items() if k in ["Aggressive", "Moderate", "Safe"]}

# Initialize on import
load_cache()
