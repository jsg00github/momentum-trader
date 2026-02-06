import pandas as pd
import numpy as np

def normalize_dataframe(df):
    """
    Ensures the dataframe has standard columns (Close, High, Low, Volume, etc.)
    and handles MultiIndex flattening if necessary.
    """
    if df is None or df.empty:
        return df
        
    df_copy = df.copy()
    if isinstance(df_copy.columns, pd.MultiIndex):
        # Flatten MultiIndex to just the metric names
        df_copy.columns = df_copy.columns.get_level_values(0)
        
    return df_copy

def calculate_rsi(series, period=14):
    """
    Calculate RSI for a pandas Series using Wilder's Smoothing (Standard).
    """
    delta = series.diff()
    
    # Wilder's Smoothing: alpha = 1 / period
    # Note: adjust=False is crucial to mimic the recursive calculation of Wilder's
    
    up = delta.where(delta > 0, 0)
    down = -delta.where(delta < 0, 0)
    
    # Use ewm with alpha=1/period
    roll_up = up.ewm(alpha=1/period, adjust=False).mean()
    roll_down = down.ewm(alpha=1/period, adjust=False).mean()

    # Avoid division by zero
    rs = roll_up / roll_down
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_weekly_rsi_analytics(daily_df):
    """
    Calculates Weekly RSI and its SMAs (3 and 14) from Daily Data.
    """
    # Determine if MultiIndex and handle it
    df = normalize_dataframe(daily_df)
    if df is None or df.empty:
        return None
    
    # Verify 'Close' exists
    if 'Close' not in df.columns:
        return None

    # Resample to Weekly. We need High/Low for SMI.
    try:
        weekly_df = df.resample('W-FRI').agg({
            'Close': 'last',
            'High': 'max',
            'Low': 'min'
        })
    except:
        return None
    
    # Need enough data: 14 weeks for RSI + 8 weeks for EMA(14) warmup = ~22 weeks min
    # 6 months = ~26 weeks, so this should work
    # SMI needs 13 + 25 weeks ~ 38 weeks.
    if len(weekly_df) < 40:
        return None

    # Calculate Weekly RSI (14)
    weekly_df['RSI'] = calculate_rsi(weekly_df['Close'], period=14)

    # Calculate EMAs of the RSI (User Custom Indicator: w.rsi)
    weekly_df['RSI_EMA_3'] = weekly_df['RSI'].ewm(span=3, adjust=False).mean()
    weekly_df['RSI_EMA_14'] = weekly_df['RSI'].ewm(span=14, adjust=False).mean()
    
    # Calculate Weekly SMI (User Params: 10, 3, 3)
    # Mapping screenshot: %K Length=10 (Period), %D Length=3 (Smooth1), EMA Length=3 (Smooth2)
    weekly_df['SMI'] = calculate_smi(weekly_df, period=10, smooth1=3, smooth2=3)

    # Get latest complete values
    last_row = weekly_df.iloc[-1]
    
    # Check for NaN
    if pd.isna(last_row['RSI_EMA_14']):
        return None

    current_rsi = float(last_row['RSI'])
    current_ema3 = float(last_row['RSI_EMA_3'])
    current_ema14 = float(last_row['RSI_EMA_14'])
    
    # SMI
    current_smi = float(last_row['SMI']) if not pd.isna(last_row['SMI']) else 0.0
    smi_bullish = current_smi > 0
    
    # === 6-TIER COLOR LOGIC ===
    # Green:  RSI > 50, RSI > EMA3, RSI > EMA14 (Strong Bullish)
    # Pink:   RSI > 50, RSI < EMA3, RSI < EMA14 (Correction in Uptrend)
    # Yellow: RSI > 50, intermediate EMAs (Pullback above midline)
    # Blue:   RSI <= 50, RSI > EMA3, RSI > EMA14 (Accumulation)
    # Orange: RSI <= 50, intermediate EMAs (Pullback below midline)
    # Red:    RSI < EMA14 (Bearish)
    
    if current_rsi > 50:
        if current_rsi > current_ema3 and current_rsi > current_ema14:
            rsi_color = "green"
        elif current_rsi < current_ema3 and current_rsi < current_ema14:
            rsi_color = "pink"
        else:
            rsi_color = "yellow"
    else: # RSI <= 50
        if current_rsi > current_ema3 and current_rsi > current_ema14:
            rsi_color = "blue"
        elif current_rsi < current_ema14:
            rsi_color = "red"
        else:
            rsi_color = "orange"
    
    # Legacy bullish flag (for backward compatibility)
    is_bullish = current_ema3 > current_ema14
    trend = "BULLISH" if is_bullish else "BEARISH"

    # Signals
    # BUY: EMA3 > EMA14 (Bullish) AND RSI in Zone (current or recent)
    signal_buy = is_bullish and (30 <= current_rsi <= 50)
    
    # SELL: EMA3 < EMA14 (Bearish Crossover)
    signal_sell = current_ema3 < current_ema14

    # Convert to Series to avoid MultiIndex crashes in tolist()
    ema3_s = pd.Series(weekly_df['RSI_EMA_3'])
    ema14_s = pd.Series(weekly_df['RSI_EMA_14'])
    close_s = pd.Series(weekly_df['Close'])
    rsi_s = pd.Series(weekly_df['RSI'])
    smi_s = pd.Series(weekly_df['SMI'])

    return {
        "rsi": current_rsi,
        "ema3": current_ema3,
        "ema14": current_ema14,
        "sma3": current_ema3,  # Compatibility Alias
        "sma14": current_ema14, # Compatibility Alias
        "color": rsi_color,  # NEW: 4-tier color (green/blue/yellow/red)
        "smi": current_smi,
        "smi_bullish": smi_bullish,
        "signal_buy": signal_buy,
        "signal_sell": signal_sell,
        "trend": trend,
        "ema3_hist": ema3_s.tail(5).tolist(),
        "ema14_hist": ema14_s.tail(5).tolist(),
        "weekly_closes": close_s.tolist(), 
        "weekly_rsi_series": rsi_s.tolist(),
        "weekly_smi_series": smi_s.tail(5).tolist()
    }

def calculate_smi(df, period=13, smooth1=25, smooth2=2):
    """
    Calculates Stochastic Momentum Index (SMI).
    SMI = 100 * (DoubleSmoothed(Close - Midpoint) / (DoubleSmoothed(High - Low) / 2))
    """
    # High/Low over period
    hh = df['High'].rolling(window=period).max()
    ll = df['Low'].rolling(window=period).min()
    midpoint = (hh + ll) / 2
    
    diff = df['Close'] - midpoint
    diff_r = hh - ll
    
    # Double Smoothing
    def double_smooth(src, len1, len2):
        # EMA of EMA
        # Note: Some implementations use SMA then EMA, but Blau used EMAs (EWM)
        e1 = src.ewm(span=len1, adjust=False).mean()
        e2 = e1.ewm(span=len2, adjust=False).mean()
        return e2

    tsi = double_smooth(diff, smooth1, smooth2)
    dsi = double_smooth(diff_r, smooth1, smooth2) / 2
    
    smi = 100 * (tsi / dsi)
    return smi

def calculate_buying_volume_trend(daily_df, window=21):
    """
    Analyzes if 'Buying Volume' (Volume on Up Days) is increasing over the last month.
    """
    df = normalize_dataframe(daily_df)
    if df is None or len(df) < window:
        return {"ratio": 1.0, "is_growing": False}

    # Use tail of the data
    df = daily_df.tail(window * 2).copy()
    
    # Volume on up days
    up_days = df[df['Close'] > df['Close'].shift(1)]
    if len(up_days) < 5:
        return {"ratio": 1.0, "is_growing": False}
        
    # Split into two halves to check growth
    mid = len(up_days) // 2
    avg_vol_up_1 = up_days['Volume'].iloc[:mid].mean()
    avg_vol_up_2 = up_days['Volume'].iloc[mid:].mean()
    
    if avg_vol_up_1 == 0 or pd.isna(avg_vol_up_1):
        return {"ratio": 1.0, "is_growing": False}
        
    ratio = avg_vol_up_2 / avg_vol_up_1
    return {
        "ratio": float(ratio),
        "is_growing": ratio > 1.05,
        "up_days_count": len(up_days),
        "avg_vol_up_recent": float(avg_vol_up_2)
    }

def calculate_daily_macd(df: pd.DataFrame):
    """
    Calculates Daily MACD (12, 26, 9) from daily price data.
    """
    df = normalize_dataframe(df)
    if df is None or len(df) < 26:
        return 0.0
        
    # Ensure Series
    close = df['Close']
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
        
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    
    return float(macd_line.iloc[-1])

def calculate_ema(df: pd.DataFrame, span: int):
    """
    Calculates EMA for a given span.
    """
    df = normalize_dataframe(df)
    if df is None or len(df) < span:
        return 0.0
    
    # Ensure Series
    close = df['Close']
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
        
    return float(close.ewm(span=span, adjust=False).mean().iloc[-1])

def calculate_sma(df: pd.DataFrame, window: int):
    """
    Calculates SMA for a given window.
    """
    df = normalize_dataframe(df)
    if df is None or len(df) < window:
        return 0.0
    
    # Ensure Series
    close = df['Close']
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
        
    return float(close.rolling(window=window).mean().iloc[-1])

def calculate_adx_di(df: pd.DataFrame, period=14):
    """
    Calculates Plus & Minus Directional Indicators (DI+ and DI-).
    """
    df = normalize_dataframe(df)
    if df is None or len(df) < period + 1:
        return 0.0, 0.0

    # Ensure Series
    try:
        high = df['High']
        if isinstance(high, pd.DataFrame): high = high.iloc[:, 0]
        low = df['Low']
        if isinstance(low, pd.DataFrame): low = low.iloc[:, 0]
        close = df['Close']
        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
        
        # Calculate DM+ and DM-
        up_move = high.diff()
        down_move = low.diff().multiply(-1)
        
        dm_plus = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        dm_minus = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Smoothed values
        atr = tr.ewm(alpha=1/period, adjust=False).mean()
        smoothed_plus = pd.Series(dm_plus).ewm(alpha=1/period, adjust=False).mean()
        smoothed_minus = pd.Series(dm_minus).ewm(alpha=1/period, adjust=False).mean()
        
        di_plus = 100 * (smoothed_plus / atr.values)
        di_minus = 100 * (smoothed_minus / atr.values)
        
        # Calculate DX (Directional Movement Index)
        dx = 100 * (abs(di_plus - di_minus) / (di_plus + di_minus).replace(0, np.nan)).fillna(0)
        
        # Calculate ADX (Average Directional Index)
        adx = dx.ewm(alpha=1/period, adjust=False).mean()
        
        return float(di_plus.iloc[-1]), float(di_minus.iloc[-1]), float(adx.iloc[-1])
    except:
        return 0.0, 0.0, 0.0


def calculate_weinstein_stage(df: pd.DataFrame, current_price: float = None):
    """
    Calculates Weinstein Stage (1-4) based on price vs 30-week SMA (or 150-day EMA).
    Stage 1: Base - Price near flat/declining MA
    Stage 2: Uptrend - Price > rising MA
    Stage 3: Top - Price near flat MA after uptrend
    Stage 4: Downtrend - Price < declining MA
    """
    df = normalize_dataframe(df)
    if df is None or len(df) < 150:
        return {"stage": 0, "label": "N/A", "color": "gray"}
    
    try:
        close = df['Close']
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        
        if current_price is None:
            current_price = float(close.iloc[-1])
        
        # Use 150-day EMA as proxy for 30-week MA
        ma_150 = close.ewm(span=150, adjust=False).mean()
        current_ma = float(ma_150.iloc[-1])
        
        # Calculate MA slope (compare to 10 days ago)
        if len(ma_150) >= 10:
            ma_10_ago = float(ma_150.iloc[-10])
            slope_pct = ((current_ma - ma_10_ago) / ma_10_ago) * 100
        else:
            slope_pct = 0
        
        # Position relative to MA
        price_vs_ma_pct = ((current_price - current_ma) / current_ma) * 100
        
        # Determine Stage
        if price_vs_ma_pct > 5 and slope_pct > 0.5:
            # Price clearly above rising MA = Stage 2 (Uptrend)
            return {"stage": 2, "label": "Stage 2", "color": "green"}
        elif price_vs_ma_pct < -5 and slope_pct < -0.5:
            # Price clearly below declining MA = Stage 4 (Downtrend)
            return {"stage": 4, "label": "Stage 4", "color": "red"}
        elif abs(slope_pct) < 0.5 and price_vs_ma_pct > 0:
            # MA flat, price above = Stage 3 (Top/Distribution)
            return {"stage": 3, "label": "Stage 3", "color": "yellow"}
        elif abs(slope_pct) < 0.5 and price_vs_ma_pct <= 0:
            # MA flat, price below = Stage 1 (Base)
            return {"stage": 1, "label": "Stage 1", "color": "blue"}
        elif price_vs_ma_pct > 0:
            # Ambiguous but above MA = Stage 2-ish
            return {"stage": 2, "label": "Stage 2", "color": "green"}
        else:
            # Ambiguous but below MA = Stage 4-ish
            return {"stage": 4, "label": "Stage 4", "color": "red"}
    except Exception as e:
        print(f"[Weinstein Stage] Error: {e}")
        return {"stage": 0, "label": "N/A", "color": "gray"}


def calculate_52w_range(df: pd.DataFrame, current_price: float = None):
    """
    Calculates the position of current price within 52-week (252 trading days) range.
    Returns low, high, and position percentage (0-100).
    """
    df = normalize_dataframe(df)
    if df is None or len(df) < 50:  # Minimum 50 days
        return {"low": 0, "high": 0, "position_pct": 50}
    
    try:
        # Get last 252 trading days (or available)
        lookback = min(252, len(df))
        df_52w = df.tail(lookback)
        
        high = df_52w['High']
        low = df_52w['Low']
        close = df_52w['Close']
        
        if isinstance(high, pd.DataFrame): high = high.iloc[:, 0]
        if isinstance(low, pd.DataFrame): low = low.iloc[:, 0]
        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
        
        week_52_high = float(high.max())
        week_52_low = float(low.min())
        
        if current_price is None:
            current_price = float(close.iloc[-1])
        
        # Calculate position percentage
        range_size = week_52_high - week_52_low
        if range_size > 0:
            position_pct = ((current_price - week_52_low) / range_size) * 100
            position_pct = max(0, min(100, position_pct))  # Clamp to 0-100
        else:
            position_pct = 50
        
        return {
            "low": round(week_52_low, 2),
            "high": round(week_52_high, 2),
            "position_pct": round(position_pct, 1)
        }
    except Exception as e:
        print(f"[52w Range] Error: {e}")
        return {"low": 0, "high": 0, "position_pct": 50}


def calculate_multi_tf_di(df_dict: dict):
    """
    Calculates DI+ > DI- alignment across multiple timeframes.
    df_dict should contain: {'h1': df, 'h4': df, 'd1': df}
    Returns dict of True/False for each timeframe.
    """
    result = {"h1": None, "h4": None, "d1": None}
    
    for tf, df in df_dict.items():
        if df is None or len(df) < 15:
            result[tf] = None
            continue
        try:
            di_plus, di_minus, _ = calculate_adx_di(df, period=14)
            result[tf] = di_plus > di_minus
        except:
            result[tf] = None
    
    return result


def calculate_momentum_score(price: float, emas: dict, rsi_data: dict, di_alignment: dict):
    """
    Calculates a 0-100 momentum score based on multiple factors:
    - EMAs (55 pts max): Price vs EMA8, EMA21, EMA35, EMA200
    - W.RSI (25 pts max): Bullish cross + color
    - DI Alignment (20 pts max): ~7 pts each for H1, H4, D1
    """
    score = 0
    
    # EMA Points (55 max)
    if emas:
        if emas.get('ema_8') and price > emas['ema_8']:
            score += 20
        if emas.get('ema_21') and price > emas['ema_21']:
            score += 15
        if emas.get('ema_35') and price > emas['ema_35']:
            score += 10
        if emas.get('ema_200') and price > emas['ema_200']:
            score += 10
    
    # W.RSI Points (25 max)
    if rsi_data:
        # Bullish crossover: EMA3 > EMA14
        if rsi_data.get('bullish'):
            score += 15
        # Color bonus
        color = rsi_data.get('color', 'red')
        if color == 'green':
            score += 10
        elif color == 'blue':
            score += 8
        elif color == 'yellow':
            score += 5
        elif color == 'orange':
            score += 3
    
    # DI Alignment Points (20 max, ~7 pts each for H1, H4, D1)
    if di_alignment:
        for tf in ['h1', 'h4', 'd1']:
            if di_alignment.get(tf) is True:
                score += 7
    
    return min(100, max(0, score))


# ============================================
# PRESSURE GAUGE INDICATOR
# ============================================

def calculate_udvr(df: pd.DataFrame, period: int = 50):
    """
    Up/Down Volume Ratio (UDVR) Indicator.
    
    Measures the ratio of buying volume to selling volume over a rolling window.
    - If close > prev_close: volume is classified as "up volume" (buying)
    - If close < prev_close: volume is classified as "down volume" (selling)
    
    Returns:
        dict with udvr_raw (ratio), udvr_normalized (0-100), udvr_trend
    """
    df = normalize_dataframe(df)
    if df is None or len(df) < period:
        return {"udvr_raw": 1.0, "udvr_normalized": 50, "udvr_trend": "neutral"}
    
    try:
        close = df['Close']
        volume = df['Volume']
        
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        if isinstance(volume, pd.DataFrame):
            volume = volume.iloc[:, 0]
        
        # Classify volume as up or down
        price_change = close.diff()
        up_volume = volume.where(price_change > 0, 0)
        down_volume = volume.where(price_change < 0, 0)
        
        # Rolling sums over period
        up_sum = up_volume.rolling(window=period, min_periods=1).sum()
        down_sum = down_volume.rolling(window=period, min_periods=1).sum()
        
        # Calculate UDVR (avoid division by zero)
        udvr = up_sum / down_sum.replace(0, np.nan)
        udvr = udvr.fillna(1.0)
        
        current_udvr = float(udvr.iloc[-1])
        prev_udvr = float(udvr.iloc[-2]) if len(udvr) > 1 else current_udvr
        
        # Normalize to 0-100 scale (1.0 = 50, 2.0 = 75, 0.5 = 25)
        # Using log scale for better distribution
        if current_udvr > 0:
            normalized = 50 + (np.log(current_udvr) * 25)
            normalized = max(0, min(100, normalized))
        else:
            normalized = 50
        
        # Determine trend
        if current_udvr > prev_udvr:
            trend = "rising"
        elif current_udvr < prev_udvr:
            trend = "falling"
        else:
            trend = "neutral"
        
        return {
            "udvr_raw": round(current_udvr, 3),
            "udvr_normalized": round(normalized, 1),
            "udvr_trend": trend
        }
    except Exception as e:
        print(f"[UDVR] Error: {e}")
        return {"udvr_raw": 1.0, "udvr_normalized": 50, "udvr_trend": "neutral"}


def calculate_rs_score(df: pd.DataFrame, benchmark_df: pd.DataFrame, lookback: int = 63):
    """
    Relative Strength Score vs Benchmark (e.g., SPY).
    
    Calculates how well the asset is performing compared to the benchmark.
    - RS = asset_close / benchmark_close
    - Normalized to 1-99 scale over lookback period
    
    Lookback options:
    - 63 bars = ~3 months
    - 126 bars = ~6 months  
    - 251 bars = ~12 months
    
    Returns:
        dict with rs_score (1-99), rs_trend
    """
    df = normalize_dataframe(df)
    benchmark_df = normalize_dataframe(benchmark_df)
    
    if df is None or benchmark_df is None:
        return {"rs_score": 50, "rs_trend": "neutral"}
    
    if len(df) < lookback or len(benchmark_df) < lookback:
        return {"rs_score": 50, "rs_trend": "neutral"}
    
    try:
        asset_close = df['Close']
        bench_close = benchmark_df['Close']
        
        if isinstance(asset_close, pd.DataFrame):
            asset_close = asset_close.iloc[:, 0]
        if isinstance(bench_close, pd.DataFrame):
            bench_close = bench_close.iloc[:, 0]
        
        # Align dataframes by index (date)
        # Take the last 'lookback' rows from each
        asset_close = asset_close.tail(lookback)
        bench_close = bench_close.tail(lookback)
        
        # Calculate relative strength ratio
        # Use percentage change to normalize different price scales
        asset_return = (asset_close.iloc[-1] / asset_close.iloc[0] - 1) * 100
        bench_return = (bench_close.iloc[-1] / bench_close.iloc[0] - 1) * 100
        
        # RS = asset return - benchmark return (outperformance)
        outperformance = asset_return - bench_return
        
        # Normalize to 1-99 scale
        # Assume typical range is -50% to +50% outperformance
        rs_score = 50 + outperformance
        rs_score = max(1, min(99, rs_score))
        
        # Calculate trend (compare recent RS to older RS)
        if len(asset_close) > 5:
            recent_asset = asset_close.iloc[-5:].mean() / asset_close.iloc[-1]
            older_asset = asset_close.iloc[-10:-5].mean() / asset_close.iloc[-6] if len(asset_close) > 10 else recent_asset
            
            if recent_asset > older_asset * 1.01:
                trend = "rising"
            elif recent_asset < older_asset * 0.99:
                trend = "falling"
            else:
                trend = "neutral"
        else:
            trend = "neutral"
        
        return {
            "rs_score": round(rs_score, 1),
            "rs_trend": trend
        }
    except Exception as e:
        print(f"[RS Score] Error: {e}")
        return {"rs_score": 50, "rs_trend": "neutral"}


def calculate_pressure_gauge(df: pd.DataFrame, benchmark_df: pd.DataFrame = None, 
                              udvr_period: int = 50, rs_lookback: int = 63):
    """
    Combined Pressure Gauge Indicator.
    
    Combines UDVR (volume pressure) and RS Score (relative strength) for 
    a comprehensive view of momentum and institutional activity.
    
    Signal interpretation:
    - UDVR > 60 + RS > 70 = Strong Buy (institutional accumulation)
    - UDVR > 55 + RS > 50 = Buy
    - UDVR 45-55 + RS 40-60 = Neutral
    - UDVR < 45 + RS < 50 = Sell
    - UDVR < 40 + RS < 30 = Strong Sell (distribution)
    
    Returns:
        dict with all pressure gauge metrics
    """
    # Calculate UDVR
    udvr_data = calculate_udvr(df, udvr_period)
    
    # Calculate RS Score (if benchmark provided)
    if benchmark_df is not None:
        rs_data = calculate_rs_score(df, benchmark_df, rs_lookback)
    else:
        rs_data = {"rs_score": 50, "rs_trend": "neutral"}
    
    udvr_norm = udvr_data["udvr_normalized"]
    rs_score = rs_data["rs_score"]
    
    # Determine composite signal
    if udvr_norm >= 60 and rs_score >= 70:
        signal = "strong_buy"
        signal_color = "green"
    elif udvr_norm >= 55 and rs_score >= 50:
        signal = "buy"
        signal_color = "lime"
    elif udvr_norm <= 40 and rs_score <= 30:
        signal = "strong_sell"
        signal_color = "red"
    elif udvr_norm <= 45 and rs_score <= 50:
        signal = "sell"
        signal_color = "orange"
    else:
        signal = "neutral"
        signal_color = "gray"
    
    # Composite score (weighted average)
    composite = (udvr_norm * 0.5) + (rs_score * 0.5)
    
    return {
        "udvr_raw": udvr_data["udvr_raw"],
        "udvr_normalized": udvr_norm,
        "udvr_trend": udvr_data["udvr_trend"],
        "rs_score": rs_score,
        "rs_trend": rs_data["rs_trend"],
        "composite": round(composite, 1),
        "signal": signal,
        "signal_color": signal_color
    }

