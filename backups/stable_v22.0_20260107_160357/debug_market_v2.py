import yfinance as yf
import pandas as pd
import numpy as np

INDICES = ["SPY", "QQQ", "IWM", "^VIX"]

def test_download():
    print(f"Downloading {INDICES}...")
    data = yf.download(" ".join(INDICES), period="1mo", interval="1d", progress=False, auto_adjust=True)
    
    print("\n--- Data Structure ---")
    print(f"Shape: {data.shape}")
    print(f"Columns: {data.columns}")
    print(f"Is MultiIndex: {isinstance(data.columns, pd.MultiIndex)}")
    
    if not data.empty:
        closes = data['Close'] if isinstance(data.columns, pd.MultiIndex) else data
        print("\n--- 'Closes' Structure ---")
        print(f"Closes Columns: {closes.columns}")
        
        for ticker in ["SPY", "QQQ", "IWM"]:
            print(f"\nProcessing {ticker}:")
            try:
                if ticker in closes.columns:
                    ser = closes[ticker].dropna()
                    print(f"  Success! Length: {len(ser)}")
                    print(f"  Type of ser: {type(ser)}")
                    if not ser.empty:
                        val = ser.iloc[-1]
                        print(f"  Last Value: {val} (Type: {type(val)})")
                else:
                    print(f"  Ticker {ticker} NOT in closes.columns")
            except Exception as e:
                print(f"  Error processing {ticker}: {e}")

if __name__ == "__main__":
    test_download()
