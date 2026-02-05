import yfinance as yf
import pandas as pd
import numpy as np
import time
import threading
from datetime import datetime
import requests
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# Finnhub fallback support
import config
import finnhub_provider

# Helper to avoid "Invalid Crumb" issues
# Use a custom session with a User-Agent to reduce 429 errors
_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})

# Thread-safe lock for yfinance downloads if needed
_download_lock = threading.Lock()

# Timeout for Yahoo Finance downloads (seconds)
YF_DOWNLOAD_TIMEOUT = 15


def safe_yf_download(tickers, **kwargs):
    """
    Wrapper for yf.download with retries and a fresh session.
    Enforces threads=False for stability in a concurrent (FastAPI) environment.
    Falls back to Finnhub if Yahoo Finance fails and Finnhub is enabled.
    """
    if isinstance(tickers, list):
        # Remove duplicates and empty strings
        tickers = sorted(list(set([t.strip().upper() for t in tickers if t.strip()])))
        tickers_str = " ".join(tickers)
    else:
        tickers = [tickers.strip().upper()]
        tickers_str = tickers[0]
        
    retries = kwargs.pop('retries', 2)
    # yf.download(threads=True) is notoriously buggy in concurrent environments
    # We enforce threads=False unless explicitly requested for large batch updates
    # where the caller handles the risk (e.g. market_data background worker)
    use_threads = kwargs.pop('threads', False)
    
    # Extract period for Finnhub fallback
    period = kwargs.get('period', '6mo')
    
    print(f"[safe_yf_download] Fetching: {tickers_str} (threads={use_threads})")
    
    # === TRY YAHOO FINANCE FIRST ===
    for i in range(retries + 1):
        try:
            # Use ThreadPoolExecutor with timeout to prevent indefinite hangs
            # NOTE: Removed global lock - yfinance handles its own threading
            # The lock was causing UI requests to wait for background tasks
            def _do_download():
                return yf.download(tickers_str, threads=use_threads, **kwargs)
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_do_download)
                try:
                    df = future.result(timeout=YF_DOWNLOAD_TIMEOUT)
                except FuturesTimeoutError:
                    print(f"[Yahoo] Download timeout after {YF_DOWNLOAD_TIMEOUT}s for {tickers_str}")
                    df = pd.DataFrame()
                
            if df is not None and not df.empty:
                # Diagnostics: verify we got what we asked for
                if isinstance(df.columns, pd.MultiIndex):
                    # Check if requested tickers are in the column levels
                    levels = df.columns.levels[1] if len(df.columns.levels) > 1 else df.columns.levels[0]
                    found = [t for t in tickers if t in levels]
                    if not found and len(tickers) == 1:
                        # Sometimes yf returns a single-level index even if MultiIndex was expected
                        pass
                
                # SUCCESS: Save to cache for future fallback
                if len(tickers) == 1:
                    try:
                        import cache
                        c = cache.get_cache()
                        c.set(tickers[0], period, kwargs.get('interval', '1d'), df)
                    except Exception:
                        pass
                
                return df
            
        except Exception as e:
            if i == retries:
                print(f"[Yahoo] Failed to download {tickers_str} after {retries} retries: {e}")
            else:
                time.sleep(1)
    
    # === FALLBACK TO FINNHUB (quotes only on free tier) ===
    if config.FINNHUB_ENABLED:
        print(f"[safe_yf_download] Yahoo failed, trying Finnhub for {tickers_str}...")
        try:
            # For single ticker
            if len(tickers) == 1:
                df = finnhub_provider.fetch_candles(tickers[0], period=period)
                if not df.empty:
                    print(f"[Finnhub] Successfully fetched {tickers[0]}")
                    return df
            else:
                # For multiple tickers, fetch each and combine into MultiIndex DataFrame
                all_dfs = {}
                for ticker in tickers[:10]:  # Limit to 10 to respect rate limits
                    ticker_df = finnhub_provider.fetch_candles(ticker, period=period)
                    if not ticker_df.empty:
                        all_dfs[ticker] = ticker_df
                
                if all_dfs:
                    # Combine into MultiIndex DataFrame similar to yfinance
                    combined = pd.concat(all_dfs, axis=1)
                    # Restructure to match yfinance MultiIndex format
                    combined.columns = pd.MultiIndex.from_tuples(
                        [(col, ticker) for ticker, df in all_dfs.items() for col in df.columns],
                        names=['Price', 'Ticker']
                    )
                    print(f"[Finnhub] Successfully fetched {len(all_dfs)} tickers")
                    return combined
        except Exception as e:
            print(f"[Finnhub] Fallback failed: {e}")
    
    # === FINAL FALLBACK: LOCAL CACHE (stale data) ===
    if len(tickers) == 1:
        try:
            import cache
            c = cache.get_cache()
            result = c.get_stale(tickers[0], period, kwargs.get('interval', '1d'))
            if result:
                df, cached_time = result
                age_hours = (datetime.now() - cached_time).total_seconds() / 3600
                print(f"[Cache] Using stale data for {tickers[0]} (cached {age_hours:.1f}h ago)")
                return df
        except Exception as e:
            print(f"[Cache] Fallback failed: {e}")
            
    return pd.DataFrame()

def chunk_list(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

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

# Inverse mapping for sector lookup
_TICKER_TO_SECTOR = {}
for sector, tickers in SECTOR_HOLDINGS.items():
    for t in tickers:
        _TICKER_TO_SECTOR[t] = sector

def get_ticker_sector(ticker):
    """Returns the sector name for a given ticker, or 'Other' if unknown."""
    # Check manual mapping first
    if ticker in _TICKER_TO_SECTOR:
        etf = _TICKER_TO_SECTOR[ticker]
        # Reverse lookup sector name
        for name, sym in SECTORS.items():
            if sym == etf: return name
            
    # Fallback to ETF lookup if ticker is a sector ETF itself
    for name, sym in SECTORS.items():
        if sym == ticker: return name
        
    return "Other"

def get_benchmark_performance(dates):
    """
    Returns cumulative performance for SPY and QQQ for the given list of dates.
    Returns: { 'SPY': [val, ...], 'QQQ': [val, ...] } matching order of input dates.
    """
    if not dates: return {"SPY": [], "QQQ": []}
    
    start_date = min(dates)
    end_date = max(dates)
    
    try:
        # Buffer dates to ensure we have data for the exact start
        data = safe_yf_download(["SPY", "QQQ"], start=start_date, progress=False)
        if data.empty: return {"SPY": [0]*len(dates), "QQQ": [0]*len(dates)}
        
        benchmarks = {}
        for sym in ["SPY", "QQQ"]:
            try:
                if isinstance(data.columns, pd.MultiIndex):
                    df = data.xs(sym, axis=1, level=1)
                else:
                    df = data if len(data.columns) > 0 else pd.DataFrame()
                
                if df.empty or 'Close' not in df.columns:
                    benchmarks[sym] = [0]*len(dates)
                    continue
                
                close = df['Close']
                start_val = float(close.iloc[0])
                
                perf_list = []
                for d in dates:
                    # Find closest date in df index <= d
                    ts = pd.Timestamp(d)
                    available_dates = df.index[df.index <= ts]
                    if not available_dates.empty:
                        curr_val = float(close.loc[available_dates[-1]])
                        perf = ((curr_val - start_val) / start_val) * 100
                        perf_list.append(round(perf, 2))
                    else:
                        perf_list.append(0.0)
                benchmarks[sym] = perf_list
            except:
                benchmarks[sym] = [0]*len(dates)
        return benchmarks
    except Exception as e:
        print(f"Error fetching benchmark data: {e}")
        return {"SPY": [0]*len(dates), "QQQ": [0]*len(dates)}

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
            series = None
            try:
                if isinstance(all_closes.columns, pd.MultiIndex):
                    if t in all_closes.columns.get_level_values(1):
                        series = all_closes.xs(t, axis=1, level=1)
                    elif t in all_closes.columns.get_level_values(0):
                        series = all_closes.xs(t, axis=1, level=0)
                elif t in all_closes.columns:
                    series = all_closes[t]
                
                # Singularize if it's still a DataFrame
                if isinstance(series, pd.DataFrame):
                    series = series.iloc[:, 0]
                
                if series is not None:
                    series = series.dropna()
                    if len(series) < 20: continue # At least 1 month
                    perf = calculate_3m_perf(series)
                    ema50 = float(series.ewm(span=50, adjust=False).mean().iloc[-1])
                    curr_price = float(series.iloc[-1])
                    results.append({"ticker": t, "perf": perf, "trend_ok": curr_price > ema50})
            except Exception as e:
                # print(f"  Debug: Sector constituent {t} fail: {e}")
                continue
        
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
    lagnames = [f"{s['name']} (**{SECTORS.get(s['name'], s['ticker'])}**)" for s in sorted(sectors, key=lambda x: x['1m'])[:2]]
    lnames = [f"{s['name']} (**{SECTORS.get(s['name'], s['ticker'])}**)" for s in leaders]
    
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
        data = safe_yf_download(INDICES, period="1mo", interval="1d", progress=False, auto_adjust=True, timeout=10)
        
        if not data.empty:
            closes = data['Close'] if isinstance(data.columns, pd.MultiIndex) else data
            
            for ticker in ["SPY", "QQQ", "IWM"]:
                try:
                    ser = None
                    # Robust MultiIndex Extract
                    if isinstance(closes.columns, pd.MultiIndex):
                        if ticker in closes.columns.get_level_values(1):
                            ser = closes.xs(ticker, axis=1, level=1)
                        elif ticker in closes.columns.get_level_values(0):
                            ser = closes.xs(ticker, axis=1, level=0)
                    elif ticker in closes.columns:
                        ser = closes[ticker]
                    
                    # Force Series
                    if isinstance(ser, pd.DataFrame):
                        ser = ser.iloc[:, 0]
                        
                    if ser is None or len(ser) < 5:
                        r_data = safe_yf_download(ticker, period="1mo", interval="1d", progress=False, auto_adjust=True, timeout=5)
                        if not r_data.empty:
                            ser = r_data['Close'] if 'Close' in r_data.columns else r_data.iloc[:, 0]
                            if isinstance(ser, pd.DataFrame): ser = ser.iloc[:, 0]

                    if ser is not None and not ser.empty:
                        ser = ser.dropna()
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
        # CHUNKED FETCHING to avoid large failures
        print(f">>> FETCHING {len(scan_tickers)} TICKERS IN CHUNKS... <<<")
        all_data_frames = []
        for chunk in chunk_list(scan_tickers, 25):
            print(f"  Fetching chunk: {chunk[:3]}... ({len(chunk)} tickers)")
            chunk_df = safe_yf_download(chunk, period="6mo", interval="1d", progress=False, auto_adjust=True, timeout=30)
            if not chunk_df.empty:
                all_data_frames.append(chunk_df)
                
        if all_data_frames:
            # Join all chunks
            batch_data = pd.concat(all_data_frames, axis=1)
            b_closes = batch_data['Close'] if isinstance(batch_data.columns, pd.MultiIndex) else batch_data
            
            for name, tick in SECTORS.items():
                ser = None
                try:
                    if isinstance(b_closes.columns, pd.MultiIndex):
                        if tick in b_closes.columns.get_level_values(1):
                            ser = b_closes.xs(tick, axis=1, level=1)
                        elif tick in b_closes.columns.get_level_values(0):
                            ser = b_closes.xs(tick, axis=1, level=0)
                    elif tick in b_closes.columns:
                        ser = b_closes[tick]
                except: continue

                if ser is not None:
                    # Force Series
                    if isinstance(ser, pd.DataFrame): ser = ser.iloc[:, 0]
                    ser = ser.dropna()
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
    try:
        result = {
            "indices": status,
            "sectors": sectors_perf,
            "breadth": calculate_breadth_metrics(sectors_perf),
            "calendar": get_economic_calendar(),
            "expert_summary": generate_expert_summary(status, sectors_perf)
        }
            
        MARKET_STATUS_CACHE["data"] = result
        MARKET_STATUS_CACHE["last_update"] = time.time()
        print(">>> MARKET STATUS BACKGROUND UPDATE COMPLETE <<<")
    except Exception as e:
        print(f"Error assembling market status result: {e}")
    finally:
        MARKET_STATUS_CACHE["is_updating"] = False

def get_batch_latest_prices(tickers):
    if not tickers: return {}
    try:
        data = safe_yf_download(list(set(tickers)), period="5d", interval="1d", progress=False, auto_adjust=True, timeout=10)
        closes = data['Close'] if isinstance(data.columns, pd.MultiIndex) else data
        prices = {}
        for t in tickers:
            ser = None
            if isinstance(closes.columns, pd.MultiIndex):
                if t in closes.columns.get_level_values(1):
                    ser = closes.xs(t, axis=1, level=1)
                elif t in closes.columns.get_level_values(0):
                    ser = closes.xs(t, axis=1, level=0)
            elif t in closes.columns:
                ser = closes[t]
            
            if ser is not None:
                if isinstance(ser, pd.DataFrame): ser = ser.iloc[:, 0]
                ser = ser.dropna()
                if not ser.empty:
                    prices[t] = float(ser.iloc[-1])
        return prices
    except: return {}
