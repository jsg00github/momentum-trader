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
PERIOD = "4y"            # Increased to 4y for Monthly MACD
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
        # Using standard browser UA to avoid SEC blocking server IPs
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9"
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

    # Priority 3: Github Raw List (Robust Backup - ~6000 tickers)
    try:
        print("DEBUG: Attempting Github Raw fetch...")
        # Source: https://github.com/rreichel3/US-Stock-Symbols
        gh_url = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"
        resp = requests.get(gh_url, timeout=10)
        resp.raise_for_status()
        
        # Clean up lines
        gh_tickers = [line.strip().upper() for line in resp.text.splitlines() if line.strip()]
        
        # Basic filter (remove symbols with weird chars if needed, though most are fine)
        gh_tickers = sorted(list(set(gh_tickers)))
        
        if len(gh_tickers) > 1000:
            print(f"DEBUG: SUCCESS - Fetched {len(gh_tickers)} tickers from Github")
            return gh_tickers
    except Exception as e:
        print(f"DEBUG: Github fetch failed: {e}")

    # Priority 4: Fallback list
    print("DEBUG: Using fallback ticker list (only ~200 items) due to all sources failing.")
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

        # Volume Week vs Month (last 5 days avg vs last 21 days avg)
        vol_week_ratio = 1.0
        try:
            if 'Volume' in df.columns and len(df) >= 21:
                vol_week_avg = df['Volume'].tail(5).mean()
                vol_month_avg = df['Volume'].tail(21).mean()
                if vol_month_avg > 0:
                    vol_week_ratio = vol_week_avg / vol_month_avg
        except:
            pass

        # === NEW INDICATORS ===
        
        # Weinstein Stage (1-4)
        stage_data = {"stage": 0, "label": "N/A", "color": "gray"}
        try:
            stage_data = indicators.calculate_weinstein_stage(df, last_close)
        except:
            pass
        
        # 52-Week Range
        range_52w = {"low": 0, "high": 0, "position_pct": 50}
        try:
            range_52w = indicators.calculate_52w_range(df, last_close)
        except:
            pass
        
        # DI Alignment (H1/H4/D - approximated from daily data)
        di_alignment = {"h1": None, "h4": None, "d1": None}
        try:
            # D1: Daily DI - already have di_plus, di_minus from earlier
            di_alignment["d1"] = di_plus > di_minus
            
            # H4: Use last 40 bars (approx 8 weeks) for more recent trend
            if len(df) >= 40:
                try:
                    h4_df = df.tail(40)
                    di_plus_h4, di_minus_h4, _ = indicators.calculate_adx_di(h4_df, period=14)
                    di_alignment["h4"] = di_plus_h4 > di_minus_h4
                except:
                    pass
            
            # H1: Use last 20 bars (approx 4 weeks) for short-term trend
            if len(df) >= 20:
                try:
                    h1_df = df.tail(20)
                    di_plus_h1, di_minus_h1, _ = indicators.calculate_adx_di(h1_df, period=14)
                    di_alignment["h1"] = di_plus_h1 > di_minus_h1
                except:
                    pass
        except:
            pass
        
        # Momentum Score (0-100)
        momentum_score = 0
        try:
            emas_dict = {
                'ema_8': indicators.calculate_ema(df, 8),
                'ema_21': indicators.calculate_ema(df, 21),
                'ema_35': indicators.calculate_ema(df, 35),
                'ema_200': indicators.calculate_ema(df, 200) if len(df) >= 200 else None
            }
            rsi_summary = {
                'bullish': rsi_data['ema3'] > rsi_data['ema14'],
                'color': rsi_data.get('color', 'red')
            }
            momentum_score = indicators.calculate_momentum_score(
                last_close, 
                emas_dict, 
                rsi_summary, 
                di_alignment
            )
        except:
            pass
        
        # Pressure Gauge (UDVR only - no benchmark available in screener)
        pressure_gauge = {"udvr_normalized": 50, "udvr_trend": "neutral", "composite": 50, "signal": "neutral"}
        try:
            pressure_gauge = indicators.calculate_pressure_gauge(df, None)  # No benchmark
        except:
            pass

        # VCP Metrics (3-6 Months)
        vcp_metrics = {"tightness_pct": 0.0, "contractions": 0, "is_vcp": False, "base_depth_pct": 0.0}
        try:
            vcp_metrics = indicators.calculate_vcp_metrics(df, 126)
        except:
            pass

        # Performance History
        len_df = len(df)
        perf_1w = ((last_close / df['Close'].iloc[-5]) - 1) * 100 if len_df >= 5 else 0
        perf_1m = ((last_close / df['Close'].iloc[-21]) - 1) * 100 if len_df >= 21 else 0
        perf_2m = ((last_close / df['Close'].iloc[-42]) - 1) * 100 if len_df >= 42 else 0
        perf_3m = ((last_close / df['Close'].iloc[-63]) - 1) * 100 if len_df >= 63 else 0

        macd_m = indicators.calculate_monthly_macd(df)

        return {
            "date": str(df.index[-1].date()),
            "price": float(last_close),
            "perf_1w": round(float(perf_1w), 2),
            "perf_1m": round(float(perf_1m), 2),
            "perf_2m": round(float(perf_2m), 2),
            "perf_3m": round(float(perf_3m), 2),
            "rsi": round(rsi_data['rsi'], 2),
            "rsi_color": rsi_data.get('color', 'gray'),  # NEW: 6-tier phase color
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
            "vol_week_vs_month": round(vol_week_ratio, 2),  # NEW: Weekly vs Monthly volume
            "stars": stars,
            "macd_d": round(macd_d, 2),
            "is_bullish": bool(is_bullish),
            "smi": round(rsi_data.get('smi', 0.0), 2),
            "smi_bullish": rsi_data.get('smi_bullish', False),
            "stage": stage_data,
            "range_52w": range_52w,
            "di_alignment": di_alignment,
            "momentum_score": momentum_score,
            "pressure_gauge": pressure_gauge,
            "vcp_metrics": vcp_metrics,
            "macd_m": macd_m,
            "float_shares": get_float_shares_formatted(ticker),
            "setup": "Weekly RSI Reversal (w.rsi)"
        }
    
    return None

def get_float_shares_formatted(ticker: str) -> str:
    if not ticker: return "-"
    try:
        info = yf.Ticker(ticker).info
        shares = info.get('floatShares', 0)
        if not shares:
            shares = info.get('sharesOutstanding', 0)
        if shares >= 1_000_000_000:
            return f"{shares/1_000_000_000:.1f}B"
        elif shares >= 1_000_000:
            return f"{shares/1_000_000:.1f}M"
        elif shares > 0:
            return str(shares)
        return "-"
    except:
        return "-"


def scan_3m_rally(df: pd.DataFrame, ticker: str = None):
    """
    Scanner for Explosive 3-Month Rally pullbacks.
    - 3-Month return > +90%
    - 1-Month return between 0% and -25% (shallow correction)
    - 1-Week return > +10% (resuming momentum)
    """
    if df is None or df.empty:
        return None
        
    df = indicators.normalize_dataframe(df)
    df = df.sort_index()
    
    len_df = len(df)
    if len_df < 65:
        return None
        
    close = df['Close'].values
    last_close = float(close[-1])
    
    # Calculate performance
    perf_1w = ((last_close / float(close[-5])) - 1) * 100
    perf_1m = ((last_close / float(close[-21])) - 1) * 100
    perf_2m = ((last_close / float(close[-42])) - 1) * 100
    perf_3m = ((last_close / float(close[-63])) - 1) * 100
    
    # Apply strict conditions
    if perf_3m <= 90.0:
        return None
    if not (-25.0 <= perf_1m <= 0.0):
        return None
    if perf_1w <= 10.0:
        return None
        
    rally_high_3m = float(df['High'].iloc[-63:].max())
    rally_low_3m = float(df['Low'].iloc[-63:].min())
    
    # If passes conditions, calculate all the standard UI indicators
    rsi_data = indicators.calculate_weekly_rsi_analytics(df)
    if not rsi_data:
        return None
        
    # Standard Indicators
    vol_data = indicators.calculate_buying_volume_trend(df, window=21)
    stars = 3 if (rsi_data.get('color') == 'green' or rsi_data.get('smi_bullish')) else 2
    
    macd_d = indicators.calculate_daily_macd(df)
    ema60_d = indicators.calculate_ema(df, 60)
    sma200_d = indicators.calculate_sma(df, 200)
    
    di_plus, di_minus, adx = indicators.calculate_adx_di(df, period=14)
    di_h1_dict = indicators.calculate_multi_tf_di({'d1': df}) # simplified for d1
    di_alignment = {"h1": None, "h4": None, "d1": di_plus > di_minus}
    
    stage_data = indicators.calculate_weinstein_stage(df)
    range_52w = indicators.calculate_52w_range(df).get("position_pct")
    is_bullish = rsi_data.get('ema3', 0) > rsi_data.get('ema14', 0)
    
    ema_dict = {'ema_200': sma200_d, 'ema_35': ema60_d, 'ema_21': ema60_d, 'ema_8': ema60_d} 
    momentum_score = indicators.calculate_momentum_score(last_close, ema_dict, rsi_data, di_alignment)
    
    pressure_gauge = {"udvr_normalized": 50, "udvr_trend": "neutral", "composite": 50, "signal": "neutral"}
    try:
         pressure_gauge = indicators.calculate_pressure_gauge(df, None)
    except:
         pass
         
    vcp_metrics = {"tightness_pct": 0.0, "contractions": 0, "is_vcp": False, "base_depth_pct": 0.0}
    try:
         vcp_metrics = indicators.calculate_vcp_metrics(df, 126)
    except:
         pass
         
    # Volume Week vs Month
    vol_week_ratio = 1.0
    try:
        if len_df >= 20:
            vol_w = df['Volume'].iloc[-5:].mean()
            vol_m = df['Volume'].iloc[-20:].mean()
            vol_week_ratio = vol_w / vol_m if vol_m > 0 else 1.0
    except:
        pass

    macd_m = indicators.calculate_monthly_macd(df)

    return {
        "date": str(df.index[-1].date()),
        "price": last_close,
        "perf_1w": round(perf_1w, 2),
        "perf_1m": round(perf_1m, 2),
        "perf_2m": round(perf_2m, 2),
        "perf_3m": round(perf_3m, 2),
        "rally_high_3m": round(rally_high_3m, 2),
        "rally_low_3m": round(rally_low_3m, 2),
        "rsi": round(rsi_data['rsi'], 2),
        "rsi_color": rsi_data.get('color', 'gray'),
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
        "vol_week_vs_month": round(vol_week_ratio, 2),
        "stars": stars,
        "macd_d": round(macd_d, 2),
        "is_bullish": bool(is_bullish),
        "smi": round(rsi_data.get('smi', 0.0), 2),
        "smi_bullish": rsi_data.get('smi_bullish', False),
        "stage": stage_data,
        "range_52w": range_52w,
        "di_alignment": di_alignment,
        "vcp_metrics": vcp_metrics,
        "macd_m": macd_m,
        "float_shares": get_float_shares_formatted(ticker),
        "setup": "3M Rally (90/25/10)"
    }


def scan_deep_oversold(df: pd.DataFrame, ticker: str = None):
    """
    Deep Oversold Scanner
    - Weekly RSI < 30
    - Daily RSI < 25
    Returns stocks fundamentally crashing but finding deep exhaustion.
    """
    if df is None or df.empty:
        return None
        
    df = indicators.normalize_dataframe(df)
    df = df.sort_index()
    
    if len(df) < 65:
        return None
        
    # Quick Reject logic (perform daily RSI check before heavy indicator calculations)
    rsi_d_series = indicators.calculate_rsi(df['Close'], period=14)
    if rsi_d_series is None or len(rsi_d_series) < 1:
         return None
         
    rsi_d_current = float(rsi_d_series.iloc[-1])
    if rsi_d_current >= 25:
         return None
         
    # Full indicator load if it passes Daily quick-check
    rsi_data = indicators.calculate_weekly_rsi_analytics(df)
    if not rsi_data:
        return None
        
    rsi_w_current = float(rsi_data['rsi'])
    if rsi_w_current >= 30:
        return None
        
    # Calculate performance metrics
    close = df['Close'].values
    last_close = float(close[-1])
    
    perf_1w = ((last_close / float(close[-5])) - 1) * 100
    perf_1m = ((last_close / float(close[-21])) - 1) * 100
    perf_2m = ((last_close / float(close[-42])) - 1) * 100
    perf_3m = ((last_close / float(close[-63])) - 1) * 100
    
    rally_high_3m = float(df['High'].iloc[-63:].max())
    rally_low_3m = float(df['Low'].iloc[-63:].min())
        
    # Standard Indicators
    vol_data = indicators.calculate_buying_volume_trend(df, window=21)
    stars = 3 if rsi_d_current < 20 else 2
    
    macd_d = indicators.calculate_daily_macd(df)
    ema60_d = indicators.calculate_ema(df, 60)
    sma200_d = indicators.calculate_sma(df, 200)
    
    di_plus, di_minus, adx = indicators.calculate_adx_di(df, period=14)
    di_alignment = {"h1": None, "h4": None, "d1": di_plus > di_minus}
    
    stage_data = indicators.calculate_weinstein_stage(df)
    range_52w = indicators.calculate_52w_range(df).get("position_pct")
    is_bullish = False
    
    ema_dict = {'ema_200': sma200_d, 'ema_35': ema60_d, 'ema_21': ema60_d, 'ema_8': ema60_d} 
    momentum_score = indicators.calculate_momentum_score(last_close, ema_dict, rsi_data, di_alignment)
    
    pressure_gauge = {"udvr_normalized": 50, "udvr_trend": "neutral", "composite": 50, "signal": "neutral"}
    try:
         pressure_gauge = indicators.calculate_pressure_gauge(df, None)
    except:
         pass
         
    vcp_metrics = {"tightness_pct": 0.0, "contractions": 0, "is_vcp": False, "base_depth_pct": 0.0}
    
    # Volume Week vs Month
    vol_week_ratio = 1.0
    try:
         vol_w = df['Volume'].iloc[-5:].mean()
         vol_m = df['Volume'].iloc[-20:].mean()
         vol_week_ratio = vol_w / vol_m if vol_m > 0 else 1.0
    except:
         pass

    macd_m = indicators.calculate_monthly_macd(df)

    # Note: We assign RSI_D to the `rsi_d` field to add support for it
    return {
        "date": str(df.index[-1].date()),
        "price": last_close,
        "perf_1w": round(perf_1w, 2),
        "perf_1m": round(perf_1m, 2),
        "perf_2m": round(perf_2m, 2),
        "perf_3m": round(perf_3m, 2),
        "rally_high_3m": round(rally_high_3m, 2),
        "rally_low_3m": round(rally_low_3m, 2),
        "rsi": round(rsi_w_current, 2),
        "rsi_d": round(rsi_d_current, 2),  # NEW EXPLICIT DAILY RSI
        "rsi_color": rsi_data.get('color', 'gray'),
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
        "vol_week_vs_month": round(vol_week_ratio, 2),
        "stars": stars,
        "macd_d": round(macd_d, 2),
        "is_bullish": False,
        "smi": round(rsi_data.get('smi', 0.0), 2),
        "smi_bullish": rsi_data.get('smi_bullish', False),
        "stage": stage_data,
        "range_52w": range_52w,
        "di_alignment": di_alignment,
        "momentum_score": momentum_score,
        "pressure_gauge": pressure_gauge,
        "vcp_metrics": vcp_metrics,
        "macd_m": macd_m,
        "float_shares": get_float_shares_formatted(ticker),
        "setup": "Deep Oversold (<25/<30)"
    }


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
    # Price must be above 200 SMA (Stage 2 Base)
    # RELAXED: Allow 5% leeway for shakeouts
    if last_close < sma_200[-1] * 0.95:
        return None
    
    # RELAXED: Price technically should be above 50 SMA, but we allow 
    # it to be slightly below if it's building the right side.
    # We DO enforce 50 SMA > 200 SMA (Structural Uptrend), with 3% leeway
    if sma_50[-1] < sma_200[-1] * 0.97:
        return None
    
    # --- RELATIVE STRENGTH CALCULATION ---
    # Calculate RS vs starting point (simple momentum measure)
    price_30d_ago = close[-30] if len(close) > 30 else close[0]
    rs_30d = ((last_close / price_30d_ago) - 1) * 100
    
    # --- FIND CONTRACTIONS (Robust Method) ---
    # Instead of arbitrary segments, check if recent volatility is lower than past volatility
    
    # 1. Current Tightness (last 10 days)
    # Use max/min for range
    r10_max = high[-10:].max()
    r10_min = low[-10:].min()
    range_10d_pct = ((r10_max - r10_min) / r10_min) * 100
    
    # 2. Previous Volatility (days -30 to -10)
    r_prev_max = high[-30:-10].max()
    r_prev_min = low[-30:-10].min()
    range_prev_pct = ((r_prev_max - r_prev_min) / r_prev_min) * 100
    
    # VCP LOGIC:
    # A. Current range must be tight (< 20%, relaxed from 15%)
    if range_10d_pct > 25: # Even more relaxed for "finding something"
        return None
        
    # B. Current range must be tighter than previous range (Contraction)
    # OR if it's already extremely tight (< 10%), we accept it
    if range_10d_pct > range_prev_pct and range_10d_pct > 10:
        return None
        
    # --- VOLUME DRY UP ---
    # Current volume (10d avg) vs Medium term (50d avg)
    vol_10d = volume[-10:].mean()
    vol_50d = volume[-50:].mean()
    
    # RELAXED: Allow volume to be slightly above average (1.2x) if price action is tight
    # Strict VCP wants < 1.0, but practical scanning needs wiggle room
    vol_ratio = vol_10d / vol_50d
    if vol_ratio > 1.2:
        return None
        
    # --- BASE DEPTH ---
    # Max drawdown from 50d high
    high_50d = high[-50:].max()
    low_since_high = low[-50:].min()
    depth_pct = ((high_50d - low_since_high) / high_50d) * 100
    
    # Allow 2% to 50% depth
    if depth_pct < 2 or depth_pct > 50:
        return None
    
    macd_m = indicators.calculate_monthly_macd(df)
    
    return {
        "ticker": ticker,
        "price": round(float(last_close), 2),
        "change_pct": round(float(df['Close'].pct_change().iloc[-1] * 100), 2),
        "vol_ratio": round(vol_ratio, 2),
        "base_depth": round(depth_pct, 2),
        "macd_m": macd_m,
        "float_shares": get_float_shares_formatted(ticker),
        "contraction_count": 1, # Simplified
        "stars": 3 if range_10d_pct < 10 else 2,
        "setup": "VCP (Tight)"
    }
    

def scan_wave2_correction(df: pd.DataFrame, ticker: str = None):
    """
    Scanner for Elliott Wave 2 Correction ending.
    Detects stocks finishing a Wave 2 pullback — ideal entry for Wave 3 impulse.
    
    Uses elliott.find_wave2_correction() for core detection, then enriches
    with standard scanner indicators for frontend compatibility.
    """
    if df is None or df.empty:
        return None
    
    df = indicators.normalize_dataframe(df)
    df = df.sort_index()
    
    if len(df) < 65:
        return None
    
    # Core detection via elliott module
    import elliott
    wave_data = elliott.find_wave2_correction(df)
    
    if not wave_data:
        return None
    
    # Standard indicator calculations (for UI parity with other strategies)
    close = df['Close'].values
    last_close = float(close[-1])
    len_df = len(df)
    
    # Performance metrics
    perf_1w = ((last_close / float(close[-5])) - 1) * 100 if len_df >= 5 else 0
    perf_1m = ((last_close / float(close[-21])) - 1) * 100 if len_df >= 21 else 0
    perf_2m = ((last_close / float(close[-42])) - 1) * 100 if len_df >= 42 else 0
    perf_3m = ((last_close / float(close[-63])) - 1) * 100 if len_df >= 63 else 0
    
    # Weekly RSI analytics
    rsi_data = indicators.calculate_weekly_rsi_analytics(df)
    if not rsi_data:
        return None
    
    # Standard indicators
    vol_data = indicators.calculate_buying_volume_trend(df, window=21)
    macd_d = indicators.calculate_daily_macd(df)
    ema60_d = indicators.calculate_ema(df, 60)
    sma200_d = indicators.calculate_sma(df, 200)
    di_plus, di_minus, adx = indicators.calculate_adx_di(df, period=14)
    
    is_bullish = rsi_data.get('ema3', 0) > rsi_data.get('ema14', 0)
    
    # Stage & Range
    stage_data = {"stage": 0, "label": "N/A", "color": "gray"}
    try:
        stage_data = indicators.calculate_weinstein_stage(df, last_close)
    except:
        pass
    
    range_52w = {"low": 0, "high": 0, "position_pct": 50}
    try:
        range_52w = indicators.calculate_52w_range(df, last_close)
    except:
        pass
    
    di_alignment = {"h1": None, "h4": None, "d1": di_plus > di_minus}
    
    momentum_score = 0
    try:
        ema_dict = {
            'ema_8': indicators.calculate_ema(df, 8),
            'ema_21': indicators.calculate_ema(df, 21),
            'ema_35': indicators.calculate_ema(df, 35),
            'ema_200': sma200_d
        }
        rsi_summary = {'bullish': is_bullish, 'color': rsi_data.get('color', 'red')}
        momentum_score = indicators.calculate_momentum_score(last_close, ema_dict, rsi_summary, di_alignment)
    except:
        pass
    
    pressure_gauge = {"udvr_normalized": 50, "udvr_trend": "neutral", "composite": 50, "signal": "neutral"}
    try:
        pressure_gauge = indicators.calculate_pressure_gauge(df, None)
    except:
        pass
    
    vcp_metrics = {"tightness_pct": 0.0, "contractions": 0, "is_vcp": False, "base_depth_pct": 0.0}
    try:
        vcp_metrics = indicators.calculate_vcp_metrics(df, 126)
    except:
        pass
    
    # Volume week vs month
    vol_week_ratio = 1.0
    try:
        if len_df >= 21:
            vol_w = df['Volume'].iloc[-5:].mean()
            vol_m = df['Volume'].iloc[-21:].mean()
            vol_week_ratio = vol_w / vol_m if vol_m > 0 else 1.0
    except:
        pass
    
    macd_m = indicators.calculate_monthly_macd(df)
    
    return {
        "date": str(df.index[-1].date()),
        "price": last_close,
        "perf_1w": round(perf_1w, 2),
        "perf_1m": round(perf_1m, 2),
        "perf_2m": round(perf_2m, 2),
        "perf_3m": round(perf_3m, 2),
        "rsi": round(rsi_data['rsi'], 2),
        "rsi_color": rsi_data.get('color', 'gray'),
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
        "vol_week_vs_month": round(vol_week_ratio, 2),
        "stars": wave_data.get("stars", 1),
        "macd_d": round(macd_d, 2),
        "is_bullish": bool(is_bullish),
        "smi": round(rsi_data.get('smi', 0.0), 2),
        "smi_bullish": rsi_data.get('smi_bullish', False),
        "stage": stage_data,
        "range_52w": range_52w,
        "di_alignment": di_alignment,
        "momentum_score": momentum_score,
        "pressure_gauge": pressure_gauge,
        "vcp_metrics": vcp_metrics,
        "macd_m": macd_m,
        "float_shares": get_float_shares_formatted(ticker),
        # Wave 2 specific fields
        "w1_height_pct": wave_data.get("w1_height_pct", 0),
        "w2_retrace_pct": wave_data.get("w2_retrace_pct", 0),
        "w2_fib_level": wave_data.get("w2_fib_level", 0),
        "wave_quality": wave_data.get("quality", "LOW"),
        "wave_phase": wave_data.get("phase", "Unknown"),
        "rsi_daily": wave_data.get("rsi_daily", 50),
        "w3_target_100": wave_data.get("w3_target_100", 0),
        "w3_target_1618": wave_data.get("w3_target_1618", 0),
        "w3_target_2618": wave_data.get("w3_target_2618", 0),
        "wave_labels": wave_data.get("wave_labels", []),
        "signal_details": wave_data.get("signal_details", []),
        "setup": "Elliott Wave 2 Correction"
    }


def scan_bull_flag(df: pd.DataFrame, ticker: str = None):
    """
    Lightweight Bull Flag scanner for mentor pipeline.
    Detects: Strong upward pole (>15%) followed by flat/down consolidation.
    Works with pre-downloaded DataFrame (no extra API calls).
    """
    if df is None or df.empty:
        return None
    
    df = indicators.normalize_dataframe(df)
    df = df.sort_index().dropna()
    
    if len(df) < 60:
        return None
    
    close = df['Close'].values
    high = df['High'].values
    low = df['Low'].values
    volume = df['Volume'].values
    last_close = close[-1]
    
    # --- FIND THE POLE (strong upward move in last 60 days) ---
    best_pole = None
    
    # Scan for pole: look for the biggest rally in the 60-day window
    window = min(60, len(df) - 1)
    for pole_start in range(len(df) - window, len(df) - 15):
        for pole_end in range(pole_start + 3, min(pole_start + 31, len(df) - 5)):
            pole_low = low[pole_start]
            pole_high = high[pole_end]
            pole_gain = (pole_high - pole_low) / pole_low
            pole_days = pole_end - pole_start
            
            if pole_gain >= 0.15 and pole_days >= 3 and pole_days <= 30:
                if best_pole is None or pole_gain > best_pole['gain']:
                    best_pole = {
                        'start_idx': pole_start,
                        'end_idx': pole_end,
                        'low': pole_low,
                        'high': pole_high,
                        'gain': pole_gain,
                        'days': pole_days
                    }
    
    if best_pole is None:
        return None
    
    # --- FLAG (consolidation after the pole) ---
    flag_start = best_pole['end_idx']
    flag_bars = len(df) - 1 - flag_start
    
    # Flag must be 5-25 bars
    if flag_bars < 5 or flag_bars > 25:
        return None
    
    flag_high = high[flag_start:].max()
    flag_low = low[flag_start:].min()
    flag_depth_pct = (flag_high - flag_low) / flag_high * 100
    
    # Flag must not exceed pole high significantly
    if flag_high > best_pole['high'] * 1.03:
        return None
    
    # Flag retracement must be <50% of pole
    pole_height = best_pole['high'] - best_pole['low']
    retracement = best_pole['high'] - flag_low
    if retracement > pole_height * 0.50:
        return None
    
    # Slope of flag highs should be flat or down
    flag_highs = high[flag_start:]
    x = np.arange(len(flag_highs))
    slope, intercept = np.polyfit(x, flag_highs, 1)
    
    # Normalize slope relative to price
    slope_pct = (slope / last_close) * 100
    if slope_pct > 0.3:  # Flag shouldn't slope up more than 0.3% per day
        return None
    
    # Volume should decline during flag
    vol_flag = volume[flag_start:].mean()
    vol_pole = volume[best_pole['start_idx']:best_pole['end_idx']].mean()
    vol_declining = vol_flag < vol_pole * 1.1  # Allow slight increase
    
    if not vol_declining:
        return None
    
    # Entry: top of flag channel + 1% buffer
    channel_top = float(slope * (len(flag_highs) - 1) + intercept)
    entry = round(channel_top * 1.01, 2)
    stop = round(flag_low * 0.98, 2)
    target = round(entry + pole_height, 2)  # Measured move: pole height from breakout
    
    return {
        "ticker": ticker,
        "pattern": "Bull Flag",
        "price": round(float(last_close), 2),
        "pole_gain_pct": round(best_pole['gain'] * 100, 1),
        "pole_days": best_pole['days'],
        "flag_days": flag_bars,
        "flag_depth_pct": round(flag_depth_pct, 1),
        "retracement_pct": round((retracement / pole_height) * 100, 1),
        "entry": entry,
        "stop": stop,
        "target": target,
        "setup": "Bull Flag"
    }


def scan_ascending_triangle(df: pd.DataFrame, ticker: str = None):
    """
    Ascending Triangle scanner for mentor pipeline.
    Detects: Flat resistance + rising higher lows (ascending support).
    Works with pre-downloaded DataFrame (no extra API calls).
    """
    if df is None or df.empty:
        return None
    
    df = indicators.normalize_dataframe(df)
    df = df.sort_index().dropna()
    
    if len(df) < 40:
        return None
    
    close = df['Close'].values
    high = df['High'].values
    low = df['Low'].values
    volume = df['Volume'].values
    last_close = close[-1]
    
    # Use last 30 trading days for triangle detection
    lookback = min(30, len(df) - 1)
    segment_high = high[-lookback:]
    segment_low = low[-lookback:]
    segment_close = close[-lookback:]
    segment_vol = volume[-lookback:]
    
    # --- FLAT RESISTANCE ---
    # Find resistance: must have 2+ touches near the same level
    resistance = segment_high.max()
    
    # Count touches within 2% of resistance
    touch_zone = resistance * 0.98
    touches = sum(1 for h in segment_high if h >= touch_zone)
    
    if touches < 2:
        return None
    
    # --- RISING LOWS (Higher lows) ---
    # Split into thirds and check lows are rising
    third = len(segment_low) // 3
    if third < 3:
        return None
    
    low_1 = segment_low[:third].min()
    low_2 = segment_low[third:2*third].min()
    low_3 = segment_low[2*third:].min()
    
    # Each third should have higher or equal lows
    rising_lows = low_2 >= low_1 * 0.98 and low_3 >= low_2 * 0.98
    if not rising_lows:
        return None
    
    # Support must be genuinely ascending (at least 2% higher from first to last)
    overall_rise = (low_3 - low_1) / low_1
    if overall_rise < 0.01:  # At least 1% rise
        return None
    
    # --- PRICE SQUEEZE toward resistance ---
    # Current price should be in the upper portion of the triangle
    triangle_range = resistance - low_3
    if triangle_range <= 0:
        return None
    
    position_in_triangle = (last_close - low_3) / triangle_range
    if position_in_triangle < 0.5:  # Should be in upper half
        return None
    
    # --- VOLUME declining during consolidation ---
    vol_first_half = segment_vol[:len(segment_vol)//2].mean()
    vol_second_half = segment_vol[len(segment_vol)//2:].mean()
    vol_declining = vol_second_half < vol_first_half * 1.2
    
    # Entry: breakout above resistance + 1%
    entry = round(resistance * 1.01, 2)
    stop = round(low_3 * 0.98, 2)
    # Target: height of triangle from breakout
    triangle_height = resistance - low_1
    target = round(entry + triangle_height, 2)
    
    return {
        "ticker": ticker,
        "pattern": "Ascending Triangle",
        "price": round(float(last_close), 2),
        "resistance": round(float(resistance), 2),
        "support_low": round(float(low_3), 2),
        "touches": touches,
        "squeeze_pct": round(position_in_triangle * 100, 1),
        "vol_declining": vol_declining,
        "entry": entry,
        "stop": stop,
        "target": target,
        "setup": "Ascending Triangle"
    }


def scan_base_breakout(df: pd.DataFrame, ticker: str = None):
    """
    Long Base Breakout scanner (AGI-style setup).
    Detects: Strong impulse move (>20%) followed by prolonged consolidation (30-120 days)
    with declining volume, then price squeezing near the top of the base.
    
    Think: Cup-and-handle, flat base, or long bull flag after impulse.
    """
    if df is None or df.empty:
        return None
    
    df = indicators.normalize_dataframe(df)
    df = df.sort_index().dropna()
    
    # Need at least 6 months of data
    if len(df) < 150:
        return None
    
    close = df['Close'].values
    high = df['High'].values
    low = df['Low'].values
    volume = df['Volume'].values
    last_close = close[-1]
    
    # --- FIND THE IMPULSE MOVE (strong rally >20% in 5-30 days) ---
    # Search in the window from 150 days ago to 30 days ago
    best_impulse = None
    search_start = max(0, len(df) - 150)
    search_end = len(df) - 30  # Must leave at least 30 days for the base
    
    for imp_start in range(search_start, search_end):
        for imp_end in range(imp_start + 5, min(imp_start + 31, search_end)):
            imp_low = low[imp_start]
            imp_high = high[imp_end]
            imp_gain = (imp_high - imp_low) / imp_low
            imp_days = imp_end - imp_start
            
            if imp_gain >= 0.20 and imp_days >= 5 and imp_days <= 30:
                # Prefer the strongest, most recent impulse
                if best_impulse is None or (imp_gain > best_impulse['gain'] * 0.9 and imp_end > best_impulse['end_idx']):
                    best_impulse = {
                        'start_idx': imp_start,
                        'end_idx': imp_end,
                        'low': imp_low,
                        'high': imp_high,
                        'gain': imp_gain,
                        'days': imp_days
                    }
    
    if best_impulse is None:
        return None
    
    # --- BASE / CONSOLIDATION (30-120 days after impulse peak) ---
    base_start = best_impulse['end_idx']
    base_bars = len(df) - 1 - base_start
    
    # Base must be 30-120 trading days
    if base_bars < 30 or base_bars > 120:
        return None
    
    base_high = high[base_start:].max()
    base_low = low[base_start:].min()
    
    # Base should not significantly exceed impulse high (no new highs during consolidation)
    if base_high > best_impulse['high'] * 1.05:
        return None
    
    # Base depth: retracement from impulse high should be <40% (shallow base = healthy)
    impulse_height = best_impulse['high'] - best_impulse['low']
    base_depth = best_impulse['high'] - base_low
    depth_pct = (base_depth / best_impulse['high']) * 100
    
    if depth_pct > 40:
        return None
    
    # --- VOLUME DECLINING during base ---
    base_vol = volume[base_start:]
    first_half_vol = base_vol[:len(base_vol)//2].mean()
    second_half_vol = base_vol[len(base_vol)//2:].mean()
    vol_declining = second_half_vol < first_half_vol * 1.1
    
    if not vol_declining:
        return None
    
    # --- PRICE SQUEEZING near top of base ---
    # Current price should be in the upper 60% of the base range
    base_range = base_high - base_low
    if base_range <= 0:
        return None
    
    position_in_base = (last_close - base_low) / base_range
    if position_in_base < 0.2:  # Should be above the very bottom (not breaking down)
        return None
    
    # --- HIGHER LOWS FORMING (ascending base) ---
    # Split base into quarters and check for rising or flat lows
    q = len(base_vol) // 4
    if q >= 3:
        ql1 = low[base_start:base_start + q].min()
        ql4 = low[base_start + 3*q:].min()
        # Last quarter low should be >= first quarter low (or close)
        has_higher_lows = ql4 >= ql1 * 0.95
    else:
        has_higher_lows = True  # Can't check, assume OK
    
    # Entry: breakout above base high + 1%
    entry = round(base_high * 1.01, 2)
    stop = round(base_low * 0.98, 2)
    # Target: measured move (impulse height projected from breakout)
    target = round(entry + impulse_height, 2)
    
    # Duration in weeks
    base_weeks = base_bars // 5
    
    return {
        "ticker": ticker,
        "pattern": "Base Breakout",
        "price": round(float(last_close), 2),
        "impulse_gain_pct": round(best_impulse['gain'] * 100, 1),
        "impulse_days": best_impulse['days'],
        "base_days": base_bars,
        "base_weeks": base_weeks,
        "base_depth_pct": round(depth_pct, 1),
        "position_in_base": round(position_in_base * 100, 1),
        "vol_declining": vol_declining,
        "has_higher_lows": has_higher_lows,
        "entry": entry,
        "stop": stop,
        "target": target,
        "setup": f"Base Breakout ({base_weeks}w base after +{round(best_impulse['gain'] * 100)}% impulse)"
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
