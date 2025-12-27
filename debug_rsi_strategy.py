
import yfinance as yf
import pandas as pd
from backend import indicators
import sys
import os

def test_rsi_logic():
    ticker = "NVDA"
    print(f"Fetching data for {ticker}...")
    
    # Simulate what trade_journal does (1y daily)
    df = yf.download(ticker, period="2y", interval="1d", progress=False)
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
        
    print(f"Data fetched: {len(df)} rows")
    
    print("Calculating Weekly RSI Analytics...")
    start_time = pd.Timestamp.now()
    results = indicators.calculate_weekly_rsi_analytics(df)
    end_time = pd.Timestamp.now()
    
    print(f"Calculation took: {(end_time - start_time).total_seconds():.4f}s")
    
    if results:
        print("\n--- RESULTS ---")
        print(f"RSI (Weekly): {results['rsi']:.2f}")
        print(f"SMA 3:        {results['sma3']:.2f}")
        print(f"SMA 14:       {results['sma14']:.2f}")
        print(f"Trend:        {results['trend']}")
        print(f"Signal BUY:   {results['signal_buy']}")
        print(f"Signal SELL:  {results['signal_sell']}")
        
        # Validation
        rsi = results['rsi']
        sma3 = results['sma3']
        sma14 = results['sma14']
        
        # Check calculation math manually effectively
        print("\n--- DEBUG DATA ---")
        print(f"Last 5 Weekly Closes: {results['weekly_closes'][-5:]}")
        print(f"Last 5 RSI values:    {results['weekly_rsi_series'][-5:]}")
        
    else:
        print("No results returned (insufficient data?)")

if __name__ == "__main__":
    test_rsi_logic()
