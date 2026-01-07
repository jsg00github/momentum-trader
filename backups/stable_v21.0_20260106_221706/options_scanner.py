import yfinance as yf
import threading
import time
import pandas as pd
from datetime import datetime, date as date_obj

# Default Universe (Liquidity + High Beta Swing Favorites)
DEFAULT_UNIVERSE = ["SPY", "QQQ", "IWM", "NVDA", "TSLA", "AMD", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "NFLX", "PLTR", "MARA", "COIN", "MSTR", "BITO", "SMH", "XLF"]

# Caching Logic
OPTIONS_CACHE = {
    "data": None,
    "last_update": 0,
    "is_updating": False
}

def get_cached_options_flow():
    global OPTIONS_CACHE
    now = time.time()
    
    # Cache valid for 30 minutes
    if OPTIONS_CACHE["data"] and (now - OPTIONS_CACHE["last_update"]) < 1800:
        return OPTIONS_CACHE["data"]
    
    if not OPTIONS_CACHE["is_updating"]:
        threading.Thread(target=refresh_options_sync).start()
        
    return OPTIONS_CACHE["data"]

def refresh_options_sync():
    global OPTIONS_CACHE
    if OPTIONS_CACHE["is_updating"]: return
    OPTIONS_CACHE["is_updating"] = True
    try:
        data = scan_unusual_options(DEFAULT_UNIVERSE)
        OPTIONS_CACHE["data"] = data
        OPTIONS_CACHE["last_update"] = time.time()
    finally:
        OPTIONS_CACHE["is_updating"] = False

def scan_unusual_options(tickers=None):
    """
    Scans for unusual options activity in the Swing Trading window (20-45 DTE).
    Returns actionable trade setups with Entry, Target, and Stop Loss.
    """
    if not tickers:
        tickers = DEFAULT_UNIVERSE

    results = []
    today = datetime.now().date()
    print(f"[OPTIONS] Scanning {len(tickers)} tickers for SWING activity (20-45 DTE)...")

    for ticker_symbol in tickers:
        try:
            tk = yf.Ticker(ticker_symbol)
            exps = tk.options
            
            if not exps:
                continue

            # Get current price once per ticker
            try:
                current_price = tk.fast_info.last_price
            except:
                # Fallback
                hist = tk.history(period="1d")
                if hist.empty: continue
                current_price = hist['Close'].iloc[-1]

            # Swing Window: 20 to 45 days out
            swing_exps = []
            for date_str in exps:
                exp_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                dte = (exp_date - today).days
                if 15 <= dte <= 60:
                    swing_exps.append((date_str, dte))

            # Only look at the closest exp within the swing window to save time/api calls
            if not swing_exps:
                continue
                
            # Sort by DTE to find the "center" of the 1-month window
            swing_exps.sort(key=lambda x: abs(x[1] - 30))
            target_exp = swing_exps[0] # The one closest to 30 days
            
            date_str, dte = target_exp
            chain = tk.option_chain(date_str)
            if chain is None:
                continue
            
            # Helper to calculate setup
            def create_setup(ticker, o_type, strike, exp, dte, vol, oi, price, last_opt_price, iv):
                # Standard Swing Setup Logic
                if o_type == "CALL":
                    target = strike # The bet is that it reaches the strike
                    # If Out-of-the-money, target is strike. If ITM, target is strike + 5%
                    if strike <= price: target = price * 1.05
                    stop = price * 0.95 # 5% stop
                else: # PUT
                    target = strike
                    if strike >= price: target = price * 0.95
                    stop = price * 1.05 # 5% stop
                
                return {
                    "ticker": ticker,
                    "type": o_type,
                    "strike": strike,
                    "expiration": exp,
                    "dte": dte,
                    "volume": int(vol),
                    "oi": int(oi),
                    "vol_oi_ratio": round(vol / (oi if oi > 0 else 1), 2),
                    "currentPrice": round(price, 2),
                    "entry": round(price, 2),
                    "target": round(target, 2),
                    "stop": round(stop, 2),
                    "lastPrice": last_opt_price,
                    "impliedVolatility": round(iv * 100, 1)
                }

            # Analyze Calls
            for idx, row in chain.calls.iterrows():
                vol = row.get('volume', 0) or 0
                oi = row.get('openInterest', 0) or 0
                # Higher threshold for swing contracts (Vol > OI is very strong signal for 1-month out)
                if vol > 300 and (vol > oi * 1.0 or vol > 1000):
                    results.append(create_setup(
                        ticker_symbol, "CALL", row['strike'], date_str, dte, 
                        vol, oi, current_price, row['lastPrice'], row['impliedVolatility']
                    ))

            # Analyze Puts
            for idx, row in chain.puts.iterrows():
                vol = row.get('volume', 0) or 0
                oi = row.get('openInterest', 0) or 0
                if vol > 300 and (vol > oi * 1.0 or vol > 1000):
                    results.append(create_setup(
                        ticker_symbol, "PUT", row['strike'], date_str, dte, 
                        vol, oi, current_price, row['lastPrice'], row['impliedVolatility']
                    ))
        except Exception as e:
            print(f"Error scanning {ticker_symbol}: {e}")
            continue

    # Sort by Volume/OI Ratio (Conviction)
    results.sort(key=lambda x: x['vol_oi_ratio'], reverse=True)
    
    # --- SENTIMENT RESOLUTION (Decide the Winner) ---
    # We group by ticker and compare the "Aggregated Conviction" (Sum of Vol * Ratio)
    # only the side (Bull vs Bear) with the highest conviction survives.
    
    ticker_sentiment = {}
    for r in results:
        ticker = r['ticker']
        if ticker not in ticker_sentiment:
            ticker_sentiment[ticker] = {'bull_score': 0, 'bear_score': 0, 'bull_signals': [], 'bear_signals': []}
        
        score = r['volume'] * r['vol_oi_ratio']
        if r['type'] == 'CALL':
            ticker_sentiment[ticker]['bull_score'] += score
            ticker_sentiment[ticker]['bull_signals'].append(r)
        else:
            ticker_sentiment[ticker]['bear_score'] += score
            ticker_sentiment[ticker]['bear_signals'].append(r)
            
    final_bullish = []
    final_bearish = []
    
    for ticker, data in ticker_sentiment.items():
        if data['bull_score'] > data['bear_score']:
            # Bullish wins - include its signals
            final_bullish.extend(data['bull_signals'])
        elif data['bear_score'] > data['bull_score']:
            # Bearish wins
            final_bearish.extend(data['bear_signals'])
        else:
            # If perfectly tied (rare), include both or just skip? 
            # Let's include both for now if they are above thresholds
            final_bullish.extend(data['bull_signals'])
            final_bearish.extend(data['bear_signals'])

    # Re-sort final results by conviction
    final_bullish.sort(key=lambda x: x['vol_oi_ratio'], reverse=True)
    final_bearish.sort(key=lambda x: x['vol_oi_ratio'], reverse=True)
    
    return {
        "bullish": final_bullish[:15],
        "bearish": final_bearish[:15],
        "perspective": "SWING (15-60 DTE) - Net Sentiment"
    }
