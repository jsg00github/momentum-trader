
import yfinance as yf
import pandas as pd

def test_batch_download_extended():
    tickers = ["SPY", "QQQ", "TSLA"]
    print(f"\n--- Testing Batch Download (prepost=True) for {tickers} ---")
    
    try:
        # Requesting prepost=True to get extended hours data
        data = yf.download(tickers, period="1d", interval="1m", prepost=True, group_by='ticker', progress=False)
        
        if data.empty:
            print("Batch download empty")
            return

        for ticker in tickers:
            print(f"\nTicker: {ticker}")
            try:
                # Handle MultiIndex
                df = data[ticker]
                if df.empty:
                    print("  Empty df")
                    continue
                    
                last_row = df.iloc[-1]
                print(f"  Last Index: {last_row.name}")
                print(f"  Close: {last_row['Close']}")
            except Exception as e:
                print(f"  Error parsing: {e}")

    except Exception as e:
        print(f"Batch Error: {e}")

test_batch_download_extended()
