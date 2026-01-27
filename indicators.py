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
    
    # Calculate Weekly SMI (13, 25, 2)
    weekly_df['SMI'] = calculate_smi(weekly_df, period=13, smooth1=25, smooth2=2)

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
    
    # Trend
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
