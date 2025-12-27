import pandas as pd
import numpy as np

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
    
    Returns a dict with:
    - rsi: Last Weekly RSI value
    - sma3: Last SMA(3) of RSI
    - sma14: Last SMA(14) of RSI
    - signal_buy: True if SMA3 > SMA14 (Crossover) AND 30 <= RSI <= 50 (Zone)
    - signal_sell: True if SMA3 < SMA14 (Bearish Cross) - Used for Exit Warnings
    - trend: "BULLISH" or "BEARISH" based on crossover
    """
    if daily_df is None or daily_df.empty:
        return None

    # Resample to Weekly. We use 'Close' for RSI.
    # 'W-FRI' ensures we end weeks on Friday.
    # .last() gets the close of the week (or current price if mid-week).
    weekly_df = daily_df.resample('W-FRI').agg({'Close': 'last'})
    
    # Need enough data: 14 weeks for RSI + 14 weeks for SMA(14) = ~28 weeks min
    if len(weekly_df) < 30:
        return None

    # Calculate Weekly RSI (14)
    weekly_df['RSI'] = calculate_rsi(weekly_df['Close'], period=14)

    # Calculate SMAs of the RSI
    weekly_df['RSI_SMA_3'] = weekly_df['RSI'].rolling(window=3).mean()
    weekly_df['RSI_SMA_14'] = weekly_df['RSI'].rolling(window=14).mean()

    # Get latest complete values
    last_row = weekly_df.iloc[-1]
    prev_row = weekly_df.iloc[-2]

    # Check for NaN (not enough data yet at the end)
    if pd.isna(last_row['RSI_SMA_14']):
        return None

    current_rsi = float(last_row['RSI'])
    current_sma3 = float(last_row['RSI_SMA_3'])
    current_sma14 = float(last_row['RSI_SMA_14'])
    
    prev_sma3 = float(prev_row['RSI_SMA_3'])
    prev_sma14 = float(prev_row['RSI_SMA_14'])

    # Trend
    is_bullish = current_sma3 > current_sma14
    trend = "BULLISH" if is_bullish else "BEARISH"

    # Signals
    # BUY: Cross UP (Bullish) AND RSI in Zone (current or recent)
    # Strict Cross check: Previous SMA3 < Prev SMA14 (Cross happened recently) check is optional
    # User asked: "Si la SMA 3 ... esta por encima ... y el RSI ... entre 30 y 50"
    # Doesn't explicitly demand the "Cross just happened", but usually scanners look for the condition being True.
    # However, "Crossover" implies the event.
    # Let's support "Condition Active" mode for now (SMA3 > SMA14).
    
    # Refined Logic based on user prompt: "Si SMA3 > SMA14 AND RSI between 30 and 50 -> Recomiende compra"
    # This identifies the "Sweet Spot".
    
    signal_buy = (current_sma3 > current_sma14) and (30 <= current_rsi <= 50)
    
    # SELL: SMA3 < SMA14 (Bearish Crossover)
    signal_sell = current_sma3 < current_sma14

    return {
        "rsi": current_rsi,
        "sma3": current_sma3,
        "sma14": current_sma14,
        "signal_buy": signal_buy,
        "signal_sell": signal_sell,
        "trend": trend,
        "weekly_closes": weekly_df['Close'].tolist(), # Debug / Charting help
        "weekly_rsi_series": weekly_df['RSI'].tolist()
    }
