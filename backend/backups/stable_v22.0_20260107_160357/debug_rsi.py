import sys
import os
import pandas as pd
import numpy as np
import yfinance as yf
# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

import screener

def test_rsi_calculation(ticker="AAPL"):
    print(f"Testing RSI for {ticker}...")
    
    # 1. Fetch Weekly Data
    df_weekly = yf.download(ticker, period="2y", interval="1wk", progress=False, auto_adjust=False)
    if isinstance(df_weekly.columns, pd.MultiIndex):
        df_weekly.columns = [c[0] for c in df_weekly.columns]
    
    if df_weekly.empty:
        print("Error: Empty dataframe")
        return

    print(f"Weekly Data: {len(df_weekly)} rows")
    
    # 2. Calculate RSI
    df_weekly['RSI'] = screener.calculate_rsi(df_weekly['Close'])
    
    print("RSI Sample (Last 5 weeks):")
    print(df_weekly['RSI'].tail(5))
    
    last_rsi = df_weekly['RSI'].iloc[-1]
    print(f"Last RSI Value: {last_rsi}")
    
    if pd.isna(last_rsi):
        print("WARNING: Last RSI is NaN")
    else:
        print("SUCCESS: Valid RSI calculated")

if __name__ == "__main__":
    test_rsi_calculation()
