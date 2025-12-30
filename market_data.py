import yfinance as yf
import pandas as pd
import numpy as np
import time
import threading
from datetime import datetime

# Global Caches
BREADTH_CACHE = {
    "data": None,
    "last_update": 0,
    "is_updating": False
}

MARKET_STATUS_CACHE = {
    "data": None,
    "last_update": 0,
    "is_updating": False
}

SECTORS = {
    "Technology": "XLK",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Cons. Discret.": "XLY",
    "Cons. Staples": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Comms": "XLC",
    "Utilities": "XLU"
}

SECTOR_HOLDINGS = {
    "XLK": ["MSFT", "AAPL", "NVDA", "AVGO", "ORCL", "ADBE", "CRM", "AMD"],
    "XLF": ["JPM", "V", "MA", "BAC", "WFC", "MS", "GS", "AXP"],
    "XLV": ["LLY", "UNH", "JNJ", "MRK", "ABBV", "TMO", "AMGN", "PFE"],
    "XLY": ["AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "BKNG"],
    "XLP": ["PG", "COST", "PEP", "KO", "WMT", "PM", "MDLZ", "CL"],
    "XLE": ["XOM", "CVX", "COP", "EOG", "SLB", "MPC", "PSX", "OXY"],
    "XLI": ["GE", "CAT", "UBER", "UNP", "HON", "BA", "UPS", "DE"],
    "XLB": ["LIN", "SHW", "FCX", "APD", "ECL", "NEM", "DOW", "DD"],
    "XLRE": ["PLD", "AMT", "EQIX", "PSA", "CCI", "O", "DLR", "VIC"],
    "XLC": ["META", "GOOGL", "NFLX", "TMUS", "DIS", "CMCSA", "VZ", "T"],
    "XLU": ["NEE", "SO", "DUK", "SRE", "AEP", "D", "PEG", "ED"]
}

INDICES = ["SPY", "QQQ", "IWM", "^VIX"]

def calculate_breadth_metrics(sectors_perf):
    """Calculates breadth metrics from sector performance data"""
    if not sectors_perf:
        return {"ad_ratio": 50, "hl_ratio": 50, "sentiment": 50, "advancing": 0, "declining": 0, "new_highs": 0, "new_lows": 0, "total": 0}
        
    advancing = sum(1 for s in sectors_perf if s.get('1m', 0) > 0)
    total = len(sectors_perf)
    declining = total - advancing
    
    # Simple proxy for high/low based on 1m performance vs 3m
    new_highs = sum(1 for s in sectors_perf if s.get('1m', 0) > 3)
    new_lows = sum(1 for s in sectors_perf if s.get('1m', 0) < -3)
    
    ad_ratio = (advancing / total * 100) if total > 0 else 50
    hl_ratio = (new_highs / (new_highs + new_lows) * 100) if (new_highs + new_lows) > 0 else 50
    sentiment = (ad_ratio + hl_ratio) / 2
    
    return {
        "ad_ratio": round(ad_ratio, 1),
        "hl_ratio": round(hl_ratio, 1),
        "sentiment": round(sentiment, 1),
        "advancing": advancing, "declining": declining,
        "new_highs": new_highs, "new_lows": new_lows, "total": total,
        "loading": not sectors_perf
    }

def calculate_3m_perf(series):
    if len(series) < 50: return 0.0
    lookback = min(len(series)-1, 63)
    start = float(series.iloc[-lookback])
    end = float(series.iloc[-1])
    if start == 0: return 0.0
    return ((end - start) / start) * 100

def analyze_sector_constituents_preloaded(sector_ticker, all_closes):
    tickers = SECTOR_HOLDINGS.get(sector_ticker, [])
    if not tickers: return None
    try:
        results = []
        for t in tickers:
            if t in all_closes.columns:
                series = all_closes[t].dropna()
                if len(series) < 20: continue # At least 1 month
                perf = calculate_3m_perf(series)
                ema50 = float(series.ewm(span=50, adjust=False).mean().iloc[-1])
                curr_price = float(series.iloc[-1])
                results.append({"ticker": t, "perf": perf, "trend_ok": curr_price > ema50})
        
        if not results: return None
        results.sort(key=lambda x: x['perf'], reverse=True)
        leader = results[0]
        # Robust laggard logic
        weinstein = [r for r in results if r['trend_ok'] and r['perf'] > 0]
        laggard = sorted(weinstein, key=lambda x: x['perf'])[0] if weinstein else results[-1]
        return {"leader": leader, "laggard": laggard}
    except Exception as e:
        print(f"Error analyzing {sector_ticker}: {e}")
        return None

def get_market_session():
    """Returns the current market session in New York Time (ET)"""
    # Assuming the server is in a fixed offset or we handle UTC
    # NY is typically UTC-5 (or UTC-4 during DST)
    # Simple approach for now: Use UTC and adjust (Assuming Standard Time for simplicity)
    utc_now = datetime.utcnow()
    ny_hour = (utc_now.hour - 5) % 24
    ny_minute = utc_now.minute
    day_of_week = utc_now.weekday() # 0=Mon, 6=Sun
    
    if day_of_week >= 5: return "WEEKEND"
    
    # Times in HHMM format
    t = ny_hour * 100 + ny_minute
    
    if 400 <= t < 930: return "PRE_MARKET"
    if 930 <= t < 1030: return "MARKET_OPEN"
    if 1030 <= t < 1530: return "REGULAR_HOURS"
    if 1530 <= t < 1600: return "MARKET_CLOSE"
    if 1600 <= t < 2000: return "POST_MARKET"
    return "CLOSED"

def generate_expert_summary(indices, sectors):
    spy = indices.get("SPY", {})
    qqq = indices.get("QQQ", {})
    vix = indices.get("VIX", {})
    session = get_market_session()
    
    bullish_count = sum(1 for i in [spy, qqq] if i.get("color") == "Green")
    bearish_count = sum(1 for i in [spy, qqq] if i.get("color") == "Red")
    
    mood = "Neutral"
    if bullish_count == 2: mood = "Bullish"
    elif bearish_count == 2: mood = "Bearish"
    elif spy.get("color") == "Green": mood = "Cautiously Bullish"
    
    risk_level = vix.get("level", "Normal")
    risk_text = "Risk is low."
    if risk_level == "Elevated": risk_text = "Volatility is rising."
    elif risk_level == "High": risk_text = "Extreme fear detected."
    
    leaders = sorted(sectors, key=lambda x: x['1m'], reverse=True)[:2]
    lagnames = [s['name'] for s in sorted(sectors, key=lambda x: x['1m'])[:2]]
    lnames = [s['name'] for s in leaders]
    
    # Session-specific Narrative
    if session == "PRE_MARKET":
        setup = f"The pre-market is showing a **{mood}** bias."
        internals = f"Watch for gaps in **{', '.join(lnames)}**. {risk_text}"
        play = "Monitor the 9:30 AM open for 'Gap and Go' setups."
    elif session == "MARKET_OPEN":
        setup = f"The opening range is forming with **{mood}** momentum."
        internals = f"High volatility detected. **{', '.join(lnames)}** are showing early strength."
        play = "Let the 15-min range settle before entering new positions."
    elif session == "MARKET_CLOSE":
        setup = f"Approaching the close in a **{mood}** state."
        internals = f"Institutional (MOC) flow is favoring **{', '.join(lnames)}**."
        play = "Look for 'Perfect 10' daily closes for potential overnight swings."
    elif session == "POST_MARKET":
        setup = f"The regular session ended **{mood}**."
        internals = f"Post-market action is centering on earnings and late volume. {risk_text}"
        play = "Review today's rotation to prepare tomorrow's watchlist."
    else: # Regular Hours / Default
        setup = f"Market is currently trading in a **{mood}** regime."
        internals = f"Internal health favored by **{', '.join(lnames)}**, with **{', '.join(lagnames)}** laggards."
        play = "Focus on relative strength (RS) names consolidatng near EMA21."

    return {
        "setup": setup, 
        "internals": internals, 
        "play": play, 
        "mood": mood,
        "session": session.replace("_", " ")
    }

def generate_morning_briefing(indices, sectors):
    spy = indices.get("SPY", {})
    vix = indices.get("VIX", {})
    mood = "Neutral"
    if spy.get("color") == "Green": mood = "Bullish"
    elif spy.get("color") == "Red": mood = "Bearish"
    price, ema21 = spy.get("price", 0), spy.get("ema21", 0)
    risk = vix.get("level", "Normal")
    message = f"🌅 <b>MORNING BRIEFING</b>\n\nOverall Mood: {mood}\nSPY: ${price} (EMA21: ${ema21})\nRisk: {risk}\n\nStay disciplined!"
    return message

def get_economic_calendar():
    """ Returns upcoming high-impact economic events. Mocked for now. """
    return [
        {"event": "ADP Non-Farm Employment Change", "date": "Jan 02", "time": "08:15 AM", "impact": "High"},
        {"event": "Initial Jobless Claims", "date": "Jan 02", "time": "08:30 AM", "impact": "Medium"},
        {"event": "FOMC Minutes", "date": "Jan 02", "time": "02:00 PM", "impact": "High"},
        {"event": "Non-Farm Payrolls (NFP)", "date": "Jan 03", "time": "08:30 AM", "impact": "High"}
    ]

def get_market_status():
    global MARKET_STATUS_CACHE
    now = time.time()
    
    # 1. Return cache if fresh (5 minutes)
    if MARKET_STATUS_CACHE["data"] and (now - MARKET_STATUS_CACHE["last_update"]) < 300:
        return MARKET_STATUS_CACHE["data"]
        
    # 2. Trigger non-blocking update if not already running
    if not MARKET_STATUS_CACHE["is_updating"]:
        threading.Thread(target=update_market_status_worker).start()
    
    # 3. If we have ANY cache data (even if 1 hour old), return it
    if MARKET_STATUS_CACHE["data"]:
        return MARKET_STATUS_CACHE["data"]
    
    # 4. Final fallback: Return a descriptive "Loading" skeleton if absolutely no data
    STATUS_SKELETON = {
        "SPY": {"price": 0, "ext_price": 0, "ext_change_pct": 0, "color": "Yellow", "desc": "Initializing...", "ema21": 0, "ema50": 0},
        "QQQ": {"price": 0, "ext_price": 0, "ext_change_pct": 0, "color": "Yellow", "desc": "Initializing...", "ema21": 0, "ema50": 0},
        "IWM": {"price": 0, "ext_price": 0, "ext_change_pct": 0, "color": "Yellow", "desc": "Initializing...", "ema21": 0, "ema50": 0},
        "VIX": {"price": 0, "level": "Normal"}
    }
    return {
        "indices": STATUS_SKELETON, 
        "sectors": [
            {"name": "Sector", "ticker": "...", "1m": 0, "2m": 0, "3m": 0}
        ], 
        "breadth": calculate_breadth_metrics([]), 
        "calendar": get_economic_calendar(),
        "expert_summary": {"session": "LOADING", "mood": "Wait", "setup": "Scanning markets...", "internals": "Patience is a virtue.", "play": "Keep refreshing."}
    }

def update_market_status_worker():
    global MARKET_STATUS_CACHE
    if MARKET_STATUS_CACHE["is_updating"]: return
    MARKET_STATUS_CACHE["is_updating"] = True
    print("\n>>> MARKET STATUS BACKGROUND UPDATE STARTED <<<")
    
    status = {
        "SPY": {"desc": "Offline"}, "QQQ": {"desc": "Offline"}, "IWM": {"desc": "Offline"}, "VIX": {"level": "Normal"}
    }
    sectors_perf = []
    
    try:
        # 1. Fetch Principal Indices (SPY, QQQ, IWM, ^VIX)
        # Reduced period to 1mo for speed (sufficient for 21/50 EMA)
        data = yf.download(" ".join(INDICES), period="1mo", interval="1d", progress=False, auto_adjust=True, timeout=10)
        
        if not data.empty:
            closes = data['Close'] if isinstance(data.columns, pd.MultiIndex) else data
            
            for ticker in ["SPY", "QQQ", "IWM"]:
                try:
                    ser = None
                    if ticker in closes.columns:
                        ser = closes[ticker].dropna()
                    elif 'Close' in closes.columns and len(closes.columns) < 10:
                        ser = closes['Close'].dropna()
                    
                    if ser is None or len(ser) < 5:
                        r_data = yf.download(ticker, period="1mo", interval="1d", progress=False, auto_adjust=True, timeout=5)
                        if not r_data.empty:
                            ser = r_data['Close'].dropna() if 'Close' in r_data.columns else r_data.iloc[:, 0].dropna()

                    if ser is not None and not ser.empty:
                        lp, e21, e50 = float(ser.iloc[-1]), float(ser.ewm(span=21, adjust=False).mean().iloc[-1]), float(ser.ewm(span=50, adjust=False).mean().iloc[-1])
                        color, desc = "Yellow", "Mixed"
                        if lp > e21 and e21 > e50: color, desc = "Green", "Uptrend"
                        elif lp < e50: color, desc = "Red", "Downtrend"
                        
                        ep, echg = lp, 0.0
                        try:
                            fi = yf.Ticker(ticker).fast_info
                            ep = getattr(fi, "last_price", lp)
                            pc = getattr(fi, "previous_close", lp)
                            if pc > 0: echg = ((ep - pc) / pc) * 100
                        except: pass
                        
                        status[ticker] = {
                            "price": round(lp, 2), "ext_price": round(float(ep), 2), "ext_change_pct": round(float(echg), 2),
                            "ema21": round(e21, 2), "ema50": round(e50, 2), "color": color, "desc": desc,
                            "sparkline": [round(float(p), 2) for p in ser.iloc[-20:].tolist()]
                        }
                except Exception as ex: print(f"Error processing {ticker}: {ex}")

            # 2. VIX Check
            try:
                v_fi = yf.Ticker("^VIX").fast_info
                vp = getattr(v_fi, "last_price", 0)
                status["VIX"] = {"price": round(float(vp), 2), "level": "Low" if vp < 15 else ("High" if vp > 20 else "Elevated")}
            except: pass
    except Exception as e:
        print(f"Error in primary indices: {e}")

    # 3. Sector & Constituents Batch Fetch
    all_sec_tickers = list(SECTORS.values())
    all_constituents = [t for sub in SECTOR_HOLDINGS.values() for t in sub]
    scan_tickers = list(set(all_sec_tickers + all_constituents))
    
    try:
        # One giant 6mo download for everything
        print(f">>> FETCHING {len(scan_tickers)} TICKERS IN ONE BATCH... <<<")
        batch_data = yf.download(" ".join(scan_tickers), period="6mo", interval="1d", progress=False, auto_adjust=True, timeout=30)
        
        if not batch_data.empty:
            b_closes = batch_data['Close'] if isinstance(batch_data.columns, pd.MultiIndex) else batch_data
            
            for name, tick in SECTORS.items():
                if tick in b_closes.columns:
                    ser = b_closes[tick].dropna()
                    if len(ser) < 21: continue
                    
                    curr = float(ser.iloc[-1])
                    
                    # 1 Month (~21 trading days)
                    idx1m = max(0, len(ser)-21)
                    p1m = float(ser.iloc[idx1m])
                    chg1m = ((curr-p1m)/p1m)*100 if p1m != 0 else 0
                    
                    # 2 Months (~42 trading days)
                    idx2m = max(0, len(ser)-42)
                    p2m = float(ser.iloc[idx2m])
                    chg2m = ((curr-p2m)/p2m)*100 if p2m != 0 else 0
                    
                    # 3 Months (~63 trading days)
                    idx3m = max(0, len(ser)-63)
                    p3m = float(ser.iloc[idx3m])
                    chg3m = ((curr-p3m)/p3m)*100 if p3m != 0 else 0
                    
                    # Deep Dive using preloaded data
                    deep_dive = analyze_sector_constituents_preloaded(tick, b_closes)
                    
                    sectors_perf.append({
                        "name": name, 
                        "ticker": tick, 
                        "1m": round(chg1m, 2), 
                        "2m": round(chg2m, 2), 
                        "3m": round(chg3m, 2), 
                        "deep_dive": deep_dive
                    })
    except Exception as e:
        print(f"Error in sector batch download: {e}")

    # 4. Final Result Assembly
    result = {
        "indices": status,
        "sectors": sectors_perf,
        "breadth": calculate_breadth_metrics(sectors_perf),
        "calendar": get_economic_calendar(),
        "expert_summary": generate_expert_summary(status, sectors_perf)
    }
        
    MARKET_STATUS_CACHE["data"] = result
    MARKET_STATUS_CACHE["last_update"] = time.time()
    MARKET_STATUS_CACHE["is_updating"] = False
    print(">>> MARKET STATUS BACKGROUND UPDATE COMPLETE <<<")

def get_batch_latest_prices(tickers):
    if not tickers: return {}
    try:
        data = yf.download(" ".join(list(set(tickers))), period="5d", interval="1d", progress=False, auto_adjust=True, timeout=10)
        closes = data['Close'] if isinstance(data.columns, pd.MultiIndex) else data
        prices = {}
        for t in tickers:
            if t in closes.columns:
                ser = closes[t].dropna()
                if not ser.empty: prices[t] = float(ser.iloc[-1])
        return prices
    except: return {}
