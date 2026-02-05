
import yfinance as yf
import pandas as pd

print("--- Single Ticker (GSIT) ---")
data_single = yf.download(["GSIT"], period="5d", progress=False)
print("Columns:", data_single.columns)
print("Head:\n", data_single.head())

print("\n--- Multi Ticker (GSIT, SPY) ---")
data_multi = yf.download(["GSIT", "SPY"], period="5d", progress=False)
print("Columns:", data_multi.columns)
print("Head:\n", data_multi.head())

# Test the extraction logic
print("\n--- Extraction Test ---")
tickers = ["GSIT", "SPY"]
for ticker in tickers:
    try:
        # Mimic logic in app
        if isinstance(data_multi.columns, pd.MultiIndex):
            # Check levels
            print(f"Checking {ticker} in MultiIndex levels...")
            # print(data_multi.columns.get_level_values(0))
            # print(data_multi.columns.get_level_values(1))
            
            try:
                df = data_multi.xs(ticker, axis=1, level=0)
                print(f"XS level=0 success for {ticker}. generic head: {df.head(1)}")
            except:
                print(f"XS level=0 failed for {ticker}")
                try:
                    df = data_multi.xs(ticker, axis=1, level=1)
                    print(f"XS level=1 success for {ticker}. generic head: {df.head(1)}")
                except:
                    print(f"XS level=1 failed for {ticker}")

    except Exception as e:
        print(e)
