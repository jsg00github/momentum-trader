
import pandas as pd
import yfinance as yf
from backend import indicators

def debug_rsi_error():
    ticker = "DXYZ"
    print(f"Downloading {ticker}...")
    # Simulate the main.py logic
    df_weekly = yf.download(ticker, period="2y", interval="1wk", progress=False, auto_adjust=False)
    
    print("Columns before flatten:", df_weekly.columns)
    
    if isinstance(df_weekly.columns, pd.MultiIndex):
        print("Flattening MultiIndex...")
        df_weekly.columns = [c[0] for c in df_weekly.columns]
    
    print("Columns after flatten:", df_weekly.columns)
    print("Number of 'Close' columns:", list(df_weekly.columns).count('Close'))
    
    try:
        series = df_weekly['Close']
        print(f"Type of df['Close']: {type(series)}")
        
        if isinstance(series, pd.DataFrame):
            print("ERROR: df['Close'] is a DataFrame! (Duplicate columns likely)")
        
        rsi = indicators.calculate_rsi(series)
        print(f"Type of RSI result: {type(rsi)}")
        
        df_weekly['RSI'] = rsi
        print("Success! RSI assigned.")
        
    except Exception as e:
        print(f"Caught Expected Error: {e}")

if __name__ == "__main__":
    debug_rsi_error()
