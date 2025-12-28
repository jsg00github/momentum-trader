
import yfinance as yf
import pandas as pd
import numpy as np
import concurrent.futures

# Universe of liquid stocks to analyze
UNIVERSE = [
    "NVDA", "TSLA", "AAPL", "AMD", "MSFT", "AMZN", "GOOGL", "META", 
    "NFLX", "COIN", "MARA", "PLTR", "SOFI", "SHOP", "SNOW",
    "JPM", "BAC", "XOM", "CVX", "KO", "PEP", "MCD", "DIS"
]

def analyze_ticker(ticker):
    try:
        data = yf.download(ticker, period="6mo", interval="1d", progress=False, auto_adjust=False)
        if len(data) < 50:
            return None

        # Handle MultiIndex
        if isinstance(data.columns, pd.MultiIndex):
            close = data['Close'][ticker]
            high = data['High'][ticker]
            low = data['Low'][ticker]
            volume = data['Volume'][ticker]
        else:
            close = data['Close']
            high = data['High']
            low = data['Low']
            volume = data['Volume']

        # Metrics
        last_price = float(close.iloc[-1])
        
        # EMA
        ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
        ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
        sma200 = float(close.rolling(window=200).mean().iloc[-1]) if len(close) > 200 else ema50 * 0.9 # Fallback
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        # Volatility (ATR %)
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]
        atr_pct = (atr / last_price) * 100
        
        # Classify
        profile = None
        score = 0
        rationale = []

        # 1. Aggressive (High Mom, High Vol)
        # Criteria: Uptrend (Price > EMA21), High ATR (> 2.5%), Good Volume
        if last_price > ema21 and atr_pct > 2.0:
            if 50 < rsi < 75:
                profile = "Aggressive"
                score = 85 + (rsi - 50)
                rationale.append("High Momentum Breakout")
                rationale.append(f"High Volatility ({atr_pct:.1f}%)")
        
        # 2. Moderate (Steady Growth)
        # Criteria: Price > EMA50, Lower Vol (< 2.0%), RSI Healthy
        elif last_price > ema50 and atr_pct < 2.5:
            if 40 < rsi < 65:
                profile = "Moderate"
                score = 75 + (rsi - 40)
                rationale.append("Steady Trend")
                rationale.append("Moderate Volatility")

        # 3. Safe (Value/Dip)
        # Criteria: Oversold or Near Support, Low Vol
        elif rsi < 40 or abs(last_price - sma200)/last_price < 0.05:
            profile = "Safe"
            score = 60 + (40 - rsi)
            rationale.append("Oversold / Support Buy")
            rationale.append("Defensive Play")
            
        if profile:
            return {
                "ticker": ticker,
                "profile": profile,
                "score": round(score, 1),
                "rationale": rationale,
                "metrics": {
                    "price": round(last_price, 2),
                    "rsi": round(rsi, 1),
                    "atr_pct": round(atr_pct, 2)
                }
            }
        return None

    except Exception as e:
        # print(f"Error {ticker}: {e}")
        return None

def get_recommendations():
    recs = {
        "Aggressive": [],
        "Moderate": [],
        "Safe": []
    }
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = list(executor.map(analyze_ticker, UNIVERSE))
        
    for r in results:
        if r:
            cat = r['profile']
            if cat in recs:
                recs[cat].append(r)
    
    # Sort by Score
    for k in recs:
        recs[k] = sorted(recs[k], key=lambda x: x['score'], reverse=True)[:3] # Top 3 per category
        
    return recs
