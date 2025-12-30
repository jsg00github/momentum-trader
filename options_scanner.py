import yfinance as yf
import threading
import time
import pandas as pd

# Default Universe (Liquid Tech/High Momentum)
DEFAULT_UNIVERSE = ["NVDA", "TSLA", "AMD", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "NFLX", "PLTR", "MARA", "COIN", "MSTR"]

# Caching Logic
OPTIONS_CACHE = {
    "data": None,
    "last_update": 0,
    "is_updating": False
}

def get_cached_options_flow():
    global OPTIONS_CACHE
    now = time.time()
    
    # Cache valid for 30 minutes (900s was 1800s)
    if OPTIONS_CACHE["data"] and (now - OPTIONS_CACHE["last_update"]) < 1800:
        return OPTIONS_CACHE["data"]
    
    if not OPTIONS_CACHE["is_updating"]:
        threading.Thread(target=refresh_options_sync).start()
        
    return OPTIONS_CACHE["data"]

import threading
import time

def refresh_options_sync():
    global OPTIONS_CACHE
    OPTIONS_CACHE["is_updating"] = True
    try:
        # Use a subset for speed in production
        data = scan_unusual_options(DEFAULT_UNIVERSE)
        OPTIONS_CACHE["data"] = data
        OPTIONS_CACHE["last_update"] = time.time()
    finally:
        OPTIONS_CACHE["is_updating"] = False

def scan_unusual_options(tickers=None):
    """
    Scans for unusual options activity (Volume > OI * threshold).
    Returns a list of unusual contracts.
    """
    if not tickers:
        tickers = DEFAULT_UNIVERSE

    results = []
    print(f"[OPTIONS] Scanning {len(tickers)} tickers for unusual activity...")

    for ticker_symbol in tickers:
        try:
            tk = yf.Ticker(ticker_symbol)
            exps = tk.options
            
            if not exps:
                continue

            # Look at nearest expiration only for speed
            for date in exps[:1]:
                chain = tk.option_chain(date)
                
                # Analyze Calls
                for idx, row in chain.calls.iterrows():
                    vol = row.get('volume', 0) or 0
                    oi = row.get('openInterest', 0) or 0
                    
                    if vol > 800 and vol > (oi * 2.0): # Stricter criteria
                        results.append({
                            "ticker": ticker_symbol,
                            "type": "CALL",
                            "strike": row['strike'],
                            "expiration": date,
                            "volume": int(vol),
                            "oi": int(oi),
                            "vol_oi_ratio": round(vol / (oi if oi > 0 else 1), 2),
                            "lastPrice": row['lastPrice'],
                            "impliedVolatility": round(row['impliedVolatility'] * 100, 1)
                        })

                # Analyze Puts
                for idx, row in chain.puts.iterrows():
                    vol = row.get('volume', 0) or 0
                    oi = row.get('openInterest', 0) or 0
                    
                    if vol > 800 and vol > (oi * 2.0):
                        results.append({
                            "ticker": ticker_symbol,
                            "type": "PUT",
                            "strike": row['strike'],
                            "expiration": date,
                            "volume": int(vol),
                            "oi": int(oi),
                            "vol_oi_ratio": round(vol / (oi if oi > 0 else 1), 2),
                            "lastPrice": row['lastPrice'],
                            "impliedVolatility": round(row['impliedVolatility'] * 100, 1)
                        })
        except: continue

    # Sort by Volume/OI Ratio
    results.sort(key=lambda x: x['vol_oi_ratio'], reverse=True)
    
    bullish = [r for r in results if r['type'] == 'CALL']
    bearish = [r for r in results if r['type'] == 'PUT']
    
    # Aggregate Flow by Ticker
    recommendations = []
    sentiment_map = {}
    for trade in results:
        t = trade['ticker']
        if t not in sentiment_map:
            sentiment_map[t] = {'call_vol': 0, 'put_vol': 0}
        if trade['type'] == 'CALL': sentiment_map[t]['call_vol'] += trade['volume']
        else: sentiment_map[t]['put_vol'] += trade['volume']

    for ticker, stats in sentiment_map.items():
        c_vol, p_vol = stats['call_vol'], stats['put_vol']
        advice = {'ticker': ticker}
        if c_vol > (p_vol * 1.5): advice['sentiment'] = "BULLISH"
        elif p_vol > (c_vol * 1.5): advice['sentiment'] = "BEARISH"
        else: advice['sentiment'] = "NEUTRAL"
        recommendations.append(advice)

    return {
        "bullish": bullish[:10], # Top 10
        "bearish": bearish[:10],
        "top_recommendations": recommendations[:5]
    }
