
import yfinance as yf
import pandas as pd
import numpy as np
from backend import indicators

def calculate_rsi_wilder(series, period=14):
    """
    Calculate RSI using Wilder's Smoothing (Standard RSI).
    """
    delta = series.diff()
    
    # Get initial SMA for the first 'period'
    # Then use Wilder's smoothing: (Prev * (n-1) + Curr) / n
    # This is equivalent to EWMA with alpha = 1 / period
    
    up = delta.where(delta > 0, 0)
    down = -delta.where(delta < 0, 0)
    
    # Use ewm with com=(period-1) which corresponds to alpha=1/period
    roll_up = up.ewm(alpha=1/period, adjust=False).mean()
    roll_down = down.ewm(alpha=1/period, adjust=False).mean()
    
    rs = roll_up / roll_down
    rsi = 100 - (100 / (1 + rs))
    return rsi

def check_rddt():
    ticker = "RDDT"
    print(f"DEBUG: Fetching data for {ticker}...")
    
    # Fetch ample data
    df = yf.download(ticker, period="2y", interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    print(f"Daily Rows: {len(df)}")
    
    # Resample Weekly
    weekly = df.resample('W-FRI').agg({'Close': 'last'})
    print(f"Weekly Rows: {len(weekly)}")
    
    # 1. Use My Current Implementation (Simple Average)
    current_rsi = indicators.calculate_rsi(weekly['Close'], 14)
    sma3 = current_rsi.rolling(3).mean()
    sma14 = current_rsi.rolling(14).mean()
    
    # 2. Use Wilder's Implementation
    wilder_rsi = calculate_rsi_wilder(weekly['Close'], 14)
    w_sma3 = wilder_rsi.rolling(3).mean()
    w_sma14 = wilder_rsi.rolling(14).mean()
    
    # Last 3 weeks comparison
    print("\n--- COMPARISON (Last 3 Weeks) ---")
    dates = weekly.index[-3:]
    
    for i in [-3, -2, -1]:
        d = weekly.index[i].date()
        c = weekly['Close'].iloc[i]
        
        print(f"\nWeek ending {d} | Close: {c:.2f}")
        
        # Current
        cur_r = current_rsi.iloc[i]
        cur_s3 = sma3.iloc[i]
        cur_s14 = sma14.iloc[i]
        print(f"  [Simple RSI] Val: {cur_r:.2f} | SMA3: {cur_s3:.2f} | SMA14: {cur_s14:.2f}")
        print(f"               Diff (3-14): {cur_s3 - cur_s14:.2f}")
        
        # Wilder
        w_r = wilder_rsi.iloc[i]
        w_s3 = w_sma3.iloc[i]
        w_s14 = w_sma14.iloc[i]
        print(f"  [Wilder RSI] Val: {w_r:.2f} | SMA3: {w_s3:.2f} | SMA14: {w_s14:.2f}")
        print(f"               Diff (3-14): {w_s3 - w_s14:.2f}")

if __name__ == "__main__":
    check_rddt()
