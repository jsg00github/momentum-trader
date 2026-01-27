import pandas as pd
import numpy as np
import yfinance as yf
import requests
import logging
import sys
import os
import market_data

# Ensure backend directory is in path for imports if running as script
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import indicators


# Configuration
PERIOD = "1y"            # Increased to 1y to ensure 30+ weekly bars
INTERVAL = "1d"           # timeframe diario

# Ventanas (en barras de trading)
THREEM_BARS = 63   # ~3 meses
MONTH_BARS  = 21   # ~1 mes
WEEK_BARS   = 5    # ~1 semana

# Condiciones de performance
MIN_RET_3M      = 0.90    # > +90% en 3 meses
MIN_RET_1W      = 0.10    # > +10% en la semana
MIN_RET_1M      = -0.25   # -25% mínimo...
MAX_RET_1M      = 0.0     # ...hasta 0% (lateral / corrección suave)

# Filtros básicos
MIN_PRICE   = 2.0       # precio mínimo
MIN_AVG_VOL = 300_000   # volumen promedio mínimo (para evitar ilíquidos)

def get_sec_tickers():
    """Fetch tickers from SEC JSON."""
    # SEC requires a User-Agent with an email, but the specific format matters.
    # This one was confirmed working:
    url = "https://www.sec.gov/files/company_tickers.json"
    headers = {
        "User-Agent": "Javier Screener 3M Rally (contacto: test@example.com)"
    }
    # Priority 1: Check for tickers.txt (Manual Override)
    try:
        import os
        if os.path.exists("tickers.txt"):
            print("DEBUG: Found tickers.txt, loading custom list...")
            with open("tickers.txt", "r") as f:
                # Read lines, strip whitespace, ignore empty lines
                custom_tickers = [line.strip().upper() for line in f if line.strip()]
            
            if custom_tickers:
                print(f"DEBUG: Loaded {len(custom_tickers)} tickers from tickers.txt")
                return sorted(list(set(custom_tickers)))
    except Exception as e:
         print(f"DEBUG: Error reading tickers.txt: {e}")

    # Priority 2: SEC Fetch
    try:
        print("DEBUG: Fetching SEC tickers...")
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        tickers = []
        for _, v in data.items():
            t = v.get("ticker")
            if t:
                tickers.append(t)
        unique_tickers = sorted(list(set(tickers)))
        print(f"DEBUG: SUCCCESS - Fetched {len(unique_tickers)} tickers from SEC")
        return unique_tickers
    except Exception as e:
        print(f"DEBUG: ERROR fetching SEC tickers: {e}")
        # Priority 3: Fallback list
        print("DEBUG: Using fallback ticker list due to SEC error.")
        return ["VTYX", "SNDK", "EVAX", "BETR", "GSIT", "EOSE", "IHRT", "CIFR", "AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "META", "AMD", "NFLX", "INTC", "QCOM", "TXN", "HON", "AMGN", "SBUX", "GILD", "MDLZ", "BKNG", "ADI", "ADP", "LRCX", "VRTX", "CSX", "ISRG", "REGN", "ATVI", "FISV", "KLAC", "MAR", "SNPS", "CDNS", "PANW", "ASML", "NXPI", "FTNT", "KDP", "ORLY", "MNST", "ODFL", "PCAR", "ROST", "PAYX", "CTAS", "MCHP", "AEP", "LULU", "EXC", "IDXX", "BIIB", "AZN", "XEL", "EA", "CSGP", "FAST", "DLTR", "BKR", "GFS", "FANG", "DXCM", "ANSS", "WBD", "ALGN", "ILMN", "SIRI", "EBAY", "ZM", "JD", "LCID", "RIVN", "DDOG", "TEAM", "WDAY", "ZS", "CRWD", "SQ", "COIN", "DKNG", "PLTR", "HOOD", "AFRM", "U", "NET", "SNOW", "MDB", "OKTA", "DOCU", "TWLO", "SPLK", "SPOT", "SNAP", "PINS", "ROKU", "TTD", "SHOP", "SE", "MELI", "TSM", "BABA", "PDD", "BIDU", "NTES", "TCOM", "ZTO", "BEKE", "YUMC", "HTHT", "BZ", "VIPS", "IQ", "WB", "MOMO", "YY", "BILI", "TME", "HUYA", "DOYU", "NIO", "XPEV", "LI", "FUTU", "TIGR", "EH", "KC", "GDS", "DQ", "JKS", "CSIQ", "SOL", "YGE", "JASO", "TSL", "LDK", "STP", "SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "USO", "UNG", "TLT", "IEF", "SHy", "AGG", "LQD", "HYG", "JNK", "EEM", "EFA", "VWO", "VEA", "IVV", "VTI", "VOO", "XLK", "XLF", "XLV", "XLY", "XLP", "XLE", "XLI", "XLB", "XLRE", "XLU", "XBI", "KRE", "KBE", "SMH", "SOXX", "XOP", "XME", "GDX", "GDXJ", "SIL", "SILJ", "TAN", "ICLN", "PBW", "QCLN", "LIT", "URA", "REMX", "COPX", "PICK", "SLX", "WOOD", "KWEB", "CQQQ", "FXI", "MCHI", "ASHR", "ASHS", "CNYA", "CHXB", "KBA", "CNXT", "CHIQ", "CHIE", "CHIM", "CHIC", "CHII", "CHIS", "CHIU", "CHIR", "CHIH", "CHIK", "CHIL", "CHIB", "CHII", "CHIS"]


def compute_3m_pattern(df: pd.DataFrame):
    """
    Evalúa:
      - Suba > 90% en los últimos ~3 meses
      - Perf 1m entre -25% y 0%
      - Perf 1w > 10%
      - Devuelve mínimo y máximo del rally de 3 meses
    Si no se cumple algo, devuelve None.
    """

    if df is None or df.empty:
        return None

    # CRITICAL: Handle MultiIndex columns (yfinance sometimes returns this)
    df = indicators.normalize_dataframe(df)

    # Verify required columns exist
    required = ["Close", "High", "Low", "Volume"]
    for col in required:
        if col not in df.columns:
            print(f"ERROR: Missing column {col}. Available columns: {df.columns.tolist()}")
            return None

    df = df.sort_index().copy().dropna()

    # Necesitamos al menos 3 meses + algo de historial para volumen
    min_len = max(THREEM_BARS, 60) + 5
    if len(df) < min_len:
        return None

    close = df["Close"].values
    high  = df["High"].values
    low   = df["Low"].values
    vol   = df["Volume"].values

    i_last = len(df) - 1
    # Chequeos de longitud para 3m, 1m, 1w
    if i_last - THREEM_BARS < 0: return None
    if i_last - MONTH_BARS  < 0: return None
    if i_last - WEEK_BARS   < 0: return None

    last_close = close[-1]

    # Filtro de precio
    if last_close < MIN_PRICE:
        return None

    # Filtro de liquidez (volumen promedio 60 barras)
    vol_s = pd.Series(vol)
    avg_vol_60 = vol_s.rolling(60).mean().iloc[-1]
    if np.isnan(avg_vol_60) or avg_vol_60 < MIN_AVG_VOL:
        return None

    # -----------------------
    # 1) Performance 3 meses
    # -----------------------
    price_3m_ago = close[-1 - THREEM_BARS]
    if price_3m_ago <= 0:
        return None

    ret_3m = (last_close / price_3m_ago) - 1.0

    # Condición: > +90%
    if ret_3m <= MIN_RET_3M:
        return None

    # Mínimo y máximo del rally en los últimos 3 meses
    rally_window_highs = high[-THREEM_BARS:]
    rally_window_lows  = low[-THREEM_BARS:]

    rally_high = rally_window_highs.max()
    rally_low  = rally_window_lows.min()

    # -----------------------
    # 2) Performance último mes
    # -----------------------
    price_1m_ago = close[-1 - MONTH_BARS]
    if price_1m_ago <= 0:
        return None

    ret_1m = (last_close / price_1m_ago) - 1.0

    # Lateralización / corrección suave: entre 0% y -25%
    if not (MIN_RET_1M <= ret_1m <= MAX_RET_1M):
        return None

    # -----------------------
    # 3) Performance última semana
    # -----------------------
    price_1w_ago = close[-1 - WEEK_BARS]
    if price_1w_ago <= 0:
        return None

    ret_1w = (last_close / price_1w_ago) - 1.0

    if ret_1w <= MIN_RET_1W:
        return None

    # Si llegó hasta acá, cumple todas las condiciones
    last_row = df.iloc[-1]
    result = {
        "date": str(last_row.name.date()) if hasattr(last_row.name, "date") else str(last_row.name),
        "close": float(last_close),
        "ret_3m_pct": float(ret_3m * 100.0),
        "ret_1m_pct": float(ret_1m * 100.0),
        "ret_1w_pct": float(ret_1w * 100.0),
        "rally_low": float(rally_low),
        "rally_high": float(rally_high),
        "avg_vol_60": float(avg_vol_60),
    }
    return result

def scan_rsi_crossover(df: pd.DataFrame):
    """
    Scanner for Weekly RSI Strategy:
    - SMA3 > SMA14 (Bullish Trend)
    - RSI between 30 and 50 (Early Reversal Zone)
    """
    if df is None or df.empty:
        return None
        
    df = indicators.normalize_dataframe(df)
    # Ensure we sort by index (Date)
    df = df.sort_index()

    # Calculate Weekly Analytics using shared module
    # Note: df is Daily. calculate_weekly_rsi_analytics handles resampling.
    rsi_data = indicators.calculate_weekly_rsi_analytics(df)
    
    if not rsi_data:
        # print("DEBUG: RSI Data calculation failed (not enough bars?)")
        return None
        
    if rsi_data['signal_buy']:
        # NEW: Buying Volume Trend Filter (Accumulation)
        vol_data = indicators.calculate_buying_volume_trend(df, window=21)
        
        # Phase 16: Sector Alignment & Stars logic
        ticker_val = str(df.columns) # Fallback if we don't have ticker here
        # Note: process_ticker adds the 'ticker' key later, so we might not have it yet
        # However, we can use a placeholder or try to infer.
        # Actually, process_ticker passes df, but screener doesn't know the ticker.
        # I'll add 'sector' as a placeholder or 'Pending' and let scan_engine resolve it.
        # OR: I'll calculate the 'stars' here since I have the rsi_data.
        
        # Confidence Rating (Stars)
        stars = 1
        if vol_data['is_growing']:
            stars += 1
            
        # Freshness: EMA3 was below EMA14 in the previous 2 bars
        ema3_h = rsi_data.get('ema3_hist', [])
        ema14_h = rsi_data.get('ema14_hist', [])
        if len(ema3_h) >= 2:
            # Check if previous bar was NOT bullish
            if ema3_h[-2] <= ema14_h[-2]:
                stars += 1
        
        # Phase 17/18/19: Daily Intelligence
        macd_d = indicators.calculate_daily_macd(df)
        ema60_d = indicators.calculate_ema(df, 60)
        sma200_d = indicators.calculate_sma(df, 200) # Added SMA 200
        di_plus, di_minus, adx = indicators.calculate_adx_di(df)
        
        last_close = df['Close'].iloc[-1]
        
        # STRICT BULLISH FILTER (Requested by User)
        # 1. MACD en verde (macd_d > 0)
        # 2. EMA 60 dias en verde (price > ema60_d)
        # 3. DMI/ADX en bullish (di_plus > di_minus)
        # 4. D+ mayor a adx (di_plus > adx)
        is_bullish = (
            macd_d > 0 and 
            last_close > ema60_d and 
            di_plus > di_minus and 
            di_plus > adx
        )
        
        if not is_bullish:
            # We no longer return None here, so that High Probability results can still be seen.
            # But we pass the is_bullish flag so the frontend can filter the Watchlist.
            pass

        return {
            "date": str(df.index[-1].date()),
            "price": float(last_close),
            "rsi": round(rsi_data['rsi'], 2),
            "ema3": round(rsi_data['ema3'], 2),
            "ema14": round(rsi_data['ema14'], 2),
            "ema60_d": round(ema60_d, 2),
            "sma200_d": round(sma200_d, 2) if sma200_d else None,
            "is_above_sma200": last_close > (sma200_d or 999999), 
            "di_plus": round(di_plus, 2),
            "di_minus": round(di_minus, 2),
            "adx": round(adx, 2),
            "di_plus_above_adx": di_plus > adx,
            "vol_ratio": round(vol_data['ratio'], 2),
            "is_vol_growing": vol_data['is_growing'],
            "stars": stars,
            "macd_d": round(macd_d, 2),
            "is_bullish": bool(is_bullish),
            "setup": "Weekly RSI Reversal (w.rsi)"
        }
    
    return None


def scan_vcp_pattern(df: pd.DataFrame, ticker: str = None):
    """
    Scanner for VCP (Volatility Contraction Pattern) - Mark Minervini style.
    Looks for:
    - Price in Stage 2 uptrend (above 50 & 200 SMA)
    - Series of contracting price pivots
    - Volume drying up during contraction
    - Tight final consolidation
    - Relative Strength vs SPY > 0
    
    Returns dict with VCP metrics or None if not found.
    """
    if df is None or df.empty:
        return None
    
    df = indicators.normalize_dataframe(df)
    df = df.sort_index().dropna()
    
    # Need enough data for 200 SMA + analysis window
    # Relaxed to 210 to allow 1y data (~252 rows) with gaps
    if len(df) < 210:
        return None
    
    close = df['Close'].values
    high = df['High'].values
    low = df['Low'].values
    volume = df['Volume'].values
    
    last_close = close[-1]
    last_date = df.index[-1]
    
    # --- STAGE 2 UPTREND CHECK ---
    sma_50 = pd.Series(close).rolling(50).mean().values
    sma_200 = pd.Series(close).rolling(200).mean().values
    
    # Price must be above 200 SMA (Stage 2 Base)
    if last_close < sma_200[-1]:
        return None
    
    # RELAXED: Price technically should be above 50 SMA, but we allow 
    # it to be slightly below if it's building the right side.
    # We DO enforce 50 SMA > 200 SMA (Structural Uptrend)
    if sma_50[-1] < sma_200[-1]:
        return None
    
    # --- RELATIVE STRENGTH CALCULATION ---
    # Calculate RS vs starting point (simple momentum measure)
    price_30d_ago = close[-30] if len(close) > 30 else close[0]
    rs_30d = ((last_close / price_30d_ago) - 1) * 100
    
    # --- FIND CONTRACTIONS ---
    # Look for series of lower highs and higher lows over last 60 days
    analysis_window = 60
    window_high = high[-analysis_window:]
    window_low = low[-analysis_window:]
    window_close = close[-analysis_window:]
    
    # Divide into 3-4 segments and check for contraction
    segment_size = analysis_window // 4
    contractions = []
    
    for i in range(4):
        start = i * segment_size
        end = (i + 1) * segment_size
        seg_high = window_high[start:end].max()
        seg_low = window_low[start:end].min()
        seg_range = seg_high - seg_low
        seg_range_pct = (seg_range / seg_low) * 100 if seg_low > 0 else 100
        contractions.append({
            'high': seg_high,
            'low': seg_low,
            'range_pct': seg_range_pct
        })
    
    # Check if ranges are contracting (each segment tighter than previous)
    is_contracting = True
    contraction_count = 0
    
    for i in range(1, len(contractions)):
        # RELAXED: Allow small fluctuation (10% tolerance)
        if contractions[i]['range_pct'] < contractions[i-1]['range_pct'] * 1.1:
            contraction_count += 1
        else:
            is_contracting = False
    
    # Need at least 2 contractions
    if contraction_count < 2:
        return None
    
    # --- FINAL CONSOLIDATION CHECK ---
    # Last 10 days should be tight (< 20% range - RELAXED from 15%)
    final_10d_high = high[-10:].max()
    final_10d_low = low[-10:].min()
    final_range_pct = ((final_10d_high - final_10d_low) / final_10d_low) * 100
    
    if final_range_pct > 20:
        return None
    
    # --- VOLUME DRY UP CHECK ---
    avg_vol_50 = np.mean(volume[-50:])
    avg_vol_10 = np.mean(volume[-10:])
    
    # Volume in last 10 days should be below average (drying up)
    volume_dry_up = avg_vol_10 / avg_vol_50 if avg_vol_50 > 0 else 1.0
    
    # RELAXED: Allow up to 1.1 (breakouts can have early volume)
    if volume_dry_up > 1.1:
        return None
    
    # --- BASE DEPTH CHECK ---
    # Find the recent high (peak before consolidation)
    lookback_for_peak = 90
    recent_peak = high[-lookback_for_peak:].max()
    recent_trough = low[-lookback_for_peak:].min()
    base_depth = ((recent_peak - recent_trough) / recent_peak) * 100
    
    # Ideal VCP base depth is 10-35%
    # RELAXED: 3-50%
    if base_depth > 50 or base_depth < 3:
        return None
    
    # --- CALCULATE ENTRY/STOP/TARGETS ---
    # Entry: Just above recent 10-day high (breakout level)
    entry = final_10d_high * 1.005  # 0.5% buffer above pivot
    
    # Stop Loss: Below the final contraction low
    stop = final_10d_low * 0.97  # 3% below pivot low
    
    # Risk per share
    risk = entry - stop
    
    # Targets based on R multiples
    target_1r = entry + risk
    target_2r = entry + (risk * 2)
    target_3r = entry + (risk * 3)
    
    # Risk/Reward ratio
    r_r = risk / entry * 100 if entry > 0 else 0
    
    # --- QUALITY GRADE ---
    # A = Tight base + strong RS + volume dry up
    # B = Good setup with some weakness
    # C = Marginal setup
    quality_score = 0
    if final_range_pct < 10:
        quality_score += 3
    elif final_range_pct < 12:
        quality_score += 2
    else:
        quality_score += 1
        
    if volume_dry_up < 0.6:
        quality_score += 2
    elif volume_dry_up < 0.75:
        quality_score += 1
        
    if rs_30d > 15:
        quality_score += 2
    elif rs_30d > 5:
        quality_score += 1
        
    if contraction_count >= 3:
        quality_score += 1
        
    if quality_score >= 7:
        grade = "A"
    elif quality_score >= 5:
        grade = "B"
    else:
        grade = "C"
    
    # --- DAYS IN BASE ---
    # Count days since the peak
    peak_idx = np.argmax(high[-lookback_for_peak:])
    days_in_base = lookback_for_peak - peak_idx
    
    return {
        "date": str(last_date.date()),
        "price": float(last_close),
        "pattern": "VCP",
        "contractions": contraction_count + 1,  # +1 for the initial expansion
        "final_range_pct": round(final_range_pct, 2),
        "base_depth_pct": round(base_depth, 2),
        "volume_dry_up": round(volume_dry_up, 2),
        "entry": round(entry, 2),
        "stop_loss": round(stop, 2),
        "target_1r": round(target_1r, 2),
        "target_2r": round(target_2r, 2),
        "target_3r": round(target_3r, 2),
        "risk_pct": round(r_r, 2),
        "rs_30d": round(rs_30d, 2),
        "sma_50": round(sma_50[-1], 2),
        "sma_200": round(sma_200[-1], 2),
        "days_in_base": int(days_in_base),
        "quality_grade": grade,
        "quality_score": quality_score,
        "setup": f"VCP Grade {grade}"
    }


def analyze_bull_flag(ticker: str):
    """
    Detailed analysis for Bull Flag pattern.
    Fetches 12mo data.
    """
    try:
        # 1. Fetch Daily Data
        df = market_data.safe_yf_download(ticker, period="12mo", interval="1d", auto_adjust=False)
        if df is None or df.empty:
            return None
            
        if isinstance(df.columns, pd.MultiIndex):
            try:
                if ticker in df.columns.get_level_values(1):
                    df = df.xs(ticker, axis=1, level=1)
                else:
                    df = df.xs(ticker, axis=1, level=0)
            except:
                df.columns = [c[0] for c in df.columns]

        df = df.sort_index().dropna()
        if len(df) < max(THREEM_BARS, MONTH_BARS):
            return None

        # 2. Fetch Weekly Data for RSI
        # Fetch enough history to warm up RSI
        df_weekly = market_data.safe_yf_download(ticker, period="2y", interval="1wk", auto_adjust=False)
        if isinstance(df_weekly.columns, pd.MultiIndex):
            try:
                if ticker in df_weekly.columns.get_level_values(1):
                    df_weekly = df_weekly.xs(ticker, axis=1, level=1)
                else:
                    df_weekly = df_weekly.xs(ticker, axis=1, level=0)
            except:
                df_weekly.columns = [c[0] for c in df_weekly.columns]
        
        rsi_weekly_series = None
        rsi_weekly_series = None
        if not df_weekly.empty:
             df_weekly['RSI'] = indicators.calculate_rsi(df_weekly['Close'])
             df_weekly['RSI_SMA_3'] = df_weekly['RSI'].rolling(window=3).mean()
             df_weekly['RSI_SMA_14'] = df_weekly['RSI'].rolling(window=14).mean()
             df_weekly['RSI_SMA_21'] = df_weekly['RSI'].rolling(window=21).mean()
             rsi_weekly_series = df_weekly['RSI']

        # Calculate Stan Weinstein WEEKLY Moving Averages on Daily (approximation)
        df['SMA_50'] = df['Close'].rolling(window=50).mean()   # ~10 weeks
        df['SMA_150'] = df['Close'].rolling(window=150).mean() # ~30 weeks

        # Logic for Mast
        last_3m = df.iloc[-THREEM_BARS:]
        mast_low_date = last_3m["Low"].idxmin()
        mast_low = float(last_3m.loc[mast_low_date, "Low"])
        mast_high_date = last_3m["High"].idxmax()
        mast_high = float(last_3m.loc[mast_high_date, "High"])
        mast_height = mast_high - mast_low
        
        # Calculate mast duration (days from low to high)
        mast_duration_days = (mast_high_date - mast_low_date).days
        
        # Validation 1: Upward Mast (High must be AFTER Low)
        # Mast must be sharp (between 3 and 35 days)
        if mast_duration_days <= 3 or mast_duration_days > 35: 
             return None

        # Logic for Flag (Last Month)
        last_month = df.iloc[-MONTH_BARS:]
        flag_high = float(last_month["High"].max())
        flag_low = float(last_month["Low"].min())

        # Validation 2: Flag High must not exceed Mast High significantly
        if flag_high > mast_high * 1.02: # Allow small 2% overshoot validation
             return None
        
        # Channel Regression
        highs = last_month["High"].values
        x = np.arange(len(highs))
        slope, intercept = np.polyfit(x, highs, 1)

        # Validation 3: Flag should not slope up significantly (should be flat or down)
        # Normalize slope? Or just check raw.
        # Strict: slope <= 0 is ideal. Allow slight drift.
        if slope > 0.2: 
             return None

        # Validation 4: Mast must be significant (> 7% move)
        if (mast_high - mast_low) / mast_low < 0.07:
             return None
        
        entry_bar_date = last_month.index[-1]
        entry_bar_low = float(df.loc[entry_bar_date, "Low"])
        entry_bar_high = float(df.loc[entry_bar_date, "High"])
        current_close = float(df.loc[entry_bar_date, "Close"])

        # Channel Top at last bar
        channel_top_last = float(slope * (len(highs) - 1) + intercept)
        
        ENTRY_BUFFER_PCT = 0.01
        raw_entry = channel_top_last * (1.0 + ENTRY_BUFFER_PCT)
        entry_ideal = max(raw_entry, entry_bar_high * 1.001)
        
        SL_BUFFER_PCT = 0.05
        stop_loss = entry_bar_low * (1.0 - SL_BUFFER_PCT)
        
        target = entry_ideal + mast_height
        
        # Calculate expected timeframe
        distance_to_target = target - current_close
        percent_move = (distance_to_target / current_close) * 100
        
        if mast_duration_days > 0 and mast_height > 0:
            mast_velocity = (mast_height / mast_low) / mast_duration_days  # % per day
            if mast_velocity > 0:
                breakout_velocity = mast_velocity * 0.5
                expected_days = (percent_move / 100) / breakout_velocity
                expected_days = min(expected_days, 90)
            else:
                expected_days = 45
        else:
            expected_days = 45
        
        # Interpolate Weekly RSI indicators onto Daily Index for smooth visualization
        if not df_weekly.empty:
            # Select only the indicator columns we need
            interp_cols = ['RSI', 'RSI_SMA_3', 'RSI_SMA_14', 'RSI_SMA_21']
            # Create temporary DF with daily index and interpolate
            df_interp = df_weekly[interp_cols].reindex(df.index)
            df_interp = df_interp.interpolate(method='linear').bfill()
            
            # Add to main DF
            df['rsi_weekly'] = df_interp['RSI']
            df['rsi_sma_3'] = df_interp['RSI_SMA_3']
            df['rsi_sma_14'] = df_interp['RSI_SMA_14']
            df['rsi_sma_21'] = df_interp['RSI_SMA_21']

        # Prepare chart data (serialize dates) with SMAs and RSI
        chart_data = []
        for idx, row in df.iterrows():
            data_point = {
                "date": str(idx.date()),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"])
            }
            
            if not pd.isna(row['SMA_50']):
                data_point['sma_50'] = float(row['SMA_50'])
            if not pd.isna(row['SMA_150']):
                data_point['sma_150'] = float(row['SMA_150'])
            
            # Add interpolated RSI values
            for field in ['rsi_weekly', 'rsi_sma_3', 'rsi_sma_14', 'rsi_sma_21']:
                if field in row and not pd.isna(row[field]):
                    data_point[field] = float(row[field])

            chart_data.append(data_point)
        
        # Add future projection points
        last_date = pd.Timestamp(entry_bar_date)
        last_sma_50 = df['SMA_50'].iloc[-1] if not pd.isna(df['SMA_50'].iloc[-1]) else None
        last_sma_150 = df['SMA_150'].iloc[-1] if not pd.isna(df['SMA_150'].iloc[-1]) else None
        
        num_projection_points = min(int(expected_days / 7) + 1, 15)
        for i in range(1, num_projection_points + 1):
            future_date = last_date + pd.Timedelta(days=i*7)
            progress = (i * 7) / expected_days
            projected_price = current_close + (target - current_close) * min(progress, 1.0)
            
            proj_point = {
                "date": str(future_date.date()),
                "projected": float(projected_price),
                "is_projection": True
            }
            
            if last_sma_50:
                proj_point['sma_50'] = float(last_sma_50)
            if last_sma_150:
                proj_point['sma_150'] = float(last_sma_150)
            
            chart_data.append(proj_point)
            
        return {
            "symbol": ticker,
            "metrics": {
                "symbol": ticker,  # Add symbol for watermark
                "is_bull_flag": True,
                "mast_height": mast_height,
                "flag_depth": flag_high - flag_low,
                "slope": slope,
                "intercept": intercept,
                "channel_top_last": channel_top_last,
                "entry": entry_ideal,
                "stop_loss": stop_loss,
                "target": target,
                "expected_days": int(expected_days),
                "percent_move": round(percent_move, 2),
                "current_close": current_close,
                "mast_duration_days": mast_duration_days
            },
            "chart_data": chart_data,
            "mast_dates": {
                "low": str(mast_low_date.date()),
                "high": str(mast_high_date.date())
            },
            "flag_start_date": str(last_month.index[0].date())
        }

    except Exception as e:
        print(f"Error analyzing {ticker}: {e}")
        return None

def get_technical_levels(ticker: str, sentiment: str = "BULLISH"):
    """
    Calculates simple technical levels (Entry, Target, Stop) based on recent price action.
    Used as fallback for Options Scanner when specific patterns aren't found.
    """
    try:
        # Fetch 6mo daily data
        df = market_data.safe_yf_download(ticker, period="6mo", interval="1d", auto_adjust=False)
        if df is None or df.empty:
            return None
            
        if isinstance(df.columns, pd.MultiIndex):
            try:
                if ticker in df.columns.get_level_values(1):
                    df = df.xs(ticker, axis=1, level=1)
                else:
                    df = df.xs(ticker, axis=1, level=0)
            except:
                df.columns = [c[0] for c in df.columns]
            
        df = df.sort_index().dropna()
        if len(df) < 20: 
            return None
            
        last_close = float(df['Close'].iloc[-1])
        
        # Calculate volatility (ATR 14 approx)
        df['TR'] = np.maximum(df['High'] - df['Low'], 
                              np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                                         abs(df['Low'] - df['Close'].shift(1))))
        atr = df['TR'].rolling(window=14).mean().iloc[-1]
        
        levels = {
            "entry": last_close,
            "target": 0.0,
            "stop_loss": 0.0,
            "r_r": 0.0
        }
        
        if sentiment == "BULLISH":
            # Stop Loss: Recent Swing Low (20d) or 2*ATR
            swing_low = df['Low'].rolling(window=20).min().iloc[-1]
            levels['stop_loss'] = max(swing_low, last_close - (atr * 2))
            
            # Target: 2x Risk or Recent High
            risk = last_close - levels['stop_loss']
            levels['target'] = last_close + (risk * 2)
            
        elif sentiment == "BEARISH":
            # Stop Loss: Recent Swing High (20d) or 2*ATR
            swing_high = df['High'].rolling(window=20).max().iloc[-1]
            levels['stop_loss'] = min(swing_high, last_close + (atr * 2))
            
            # Target: 2x Risk
            risk = levels['stop_loss'] - last_close
            levels['target'] = last_close - (risk * 2)
            
        else: # NEUTRAL/VOLATILITY
             # Wide brackets
             levels['stop_loss'] = last_close - (atr * 2) # Downside protection
             levels['target'] = last_close + (atr * 2)    # Upside target
             
        levels['entry'] = round(levels['entry'], 2)
        levels['target'] = round(levels['target'], 2)
        levels['stop_loss'] = round(levels['stop_loss'], 2)
             
        if levels['target'] != levels['entry']:
             dist_target = abs(levels['target'] - levels['entry'])
             dist_stop = abs(levels['entry'] - levels['stop_loss'])
             if dist_stop > 0:
                 levels['r_r'] = round(dist_target / dist_stop, 2)
        
        return levels

    except Exception as e:
        print(f"Error getting levels for {ticker}: {e}")
        return None

def predict_future_path(df: pd.DataFrame, entry_price: float = None, target: float = None, days: int = 20):
    """
    Predicts future price path based on:
    1. Linear regression of recent prices (30 days).
    2. Momentum from Entry Price (if provided).
    3. Target/Stop levels weight.
    """
    try:
        if df is None or df.empty:
            return []
            
        close = df['Close'].values
        if len(close) < 10:
            return []
            
        last_price = float(close[-1])
        last_date = df.index[-1]
        
        # 1. Historical Trend (Recent 30-day slope)
        lookback = min(len(close), 30)
        recent_prices = close[-lookback:]
        x = np.arange(len(recent_prices))
        slope, intercept = np.polyfit(x, recent_prices, 1)
        
        # 2. Momentum from Entry (if available)
        momentum_slope = slope
        if entry_price and entry_price > 0:
            # If we know entry, calculate a 'target-seeking' slope
            # If target is provided, trend towards it
            if target and target > last_price:
                 # Calculate slope needed to reach target in 'days'
                 target_slope = (target - last_price) / days
                 momentum_slope = (slope * 0.4) + (target_slope * 0.6)
            else:
                 # Default momentum preservation
                 momentum_slope = slope
        
        # 3. Generate Predictions
        predictions = []
        current_pred = last_price
        
        import datetime
        
        for i in range(1, days + 1):
            next_date = last_date + datetime.timedelta(days=i)
            # Skip weekends for a more realistic trading view
            if next_date.weekday() >= 5: # Sat=5, Sun=6
                continue
                
            # Add some linear growth + a tiny bit of random noise (0.1% volatility)
            noise = (np.random.normal(0, 1) * last_price * 0.005) 
            current_pred += momentum_slope + (noise / days)
            
            # Ensure price doesn't go negative
            current_pred = max(current_pred, 0.01)
            
            predictions.append({
                "date": str(next_date.date()),
                "projected": float(current_pred),
                "is_projection": True
            })
            
        return predictions

    except Exception as e:
        print(f"Prediction Error: {e}")
        return []
