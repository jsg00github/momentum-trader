import sys
import os
import pandas as pd
import numpy as np
import yfinance as yf
# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

import screener

def test_rsi_integration(ticker="AAPL"):
    print(f"Testing RSI Integration for {ticker}...")
    
    # 1. Fetch Daily Data (Simulate main.py)
    df = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df = df.sort_index().dropna()
    
    # 2. Fetch Weekly Data
    df_weekly = yf.download(ticker, period="1y", interval="1wk", progress=False, auto_adjust=False)
    if isinstance(df_weekly.columns, pd.MultiIndex):
        df_weekly.columns = [c[0] for c in df_weekly.columns]
    
    rsi_weekly_series = None
    if not df_weekly.empty:
         df_weekly['RSI'] = screener.calculate_rsi(df_weekly['Close'])
         rsi_weekly_series = df_weekly['RSI']
    
    print("Merging data...")
    chart_data = []
    
    rsi_found_count = 0
    
    for idx, row in df.iterrows():
        rsi_val = None
        if rsi_weekly_series is not None:
            # Replicating main.py logic exactly
            past_weeks = rsi_weekly_series[rsi_weekly_series.index <= idx]
            if not past_weeks.empty:
                rsi_val = float(past_weeks.iloc[-1])

        data_point = {
            "date": str(idx.date()),
            "close": float(row["Close"])
        }
        if rsi_val is not None: # Not filtering NaN here to see what we get
            data_point['rsi_weekly'] = rsi_val
            if not pd.isna(rsi_val):
                rsi_found_count += 1
        
        chart_data.append(data_point)
    
    print(f"Total chart points: {len(chart_data)}")
    print(f"Points with Valid RSI: {rsi_found_count}")
    
    if rsi_found_count == 0:
        print("ERROR: No valid RSI values found after merge!")
        print("Sample Daily Index:", df.index[0])
        print("Sample Weekly Index:", df_weekly.index[0])
    else:
        print("SUCCESS: RSI merged correctly.")
        print("Last point:", chart_data[-1])

if __name__ == "__main__":
    test_rsi_integration()
