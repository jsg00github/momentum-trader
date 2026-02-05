
import yfinance as yf
import pandas as pd

tickers = ["GSIT", "DEBUG"]
print(f"Downloading: {tickers}")

try:
    data = yf.download(tickers, period="5d", progress=False)
    print("Download complete.")
    print("Columns:", data.columns)
    
    # Simulate Backend Logic
    results = {}
    
    for ticker in tickers:
        print(f"\nProcessing {ticker}...")
        try:
            if len(tickers) == 1:
                df = data
            else:
                if isinstance(data.columns, pd.MultiIndex):
                    try:
                        df = data.xs(ticker, axis=1, level=1)
                        print("Extracted via Level 1")
                    except KeyError:
                        try:
                            df = data.xs(ticker, axis=1, level=0)
                            print("Extracted via Level 0")
                        except KeyError:
                            print(f"Could not find {ticker} in columns")
                            continue
                else:
                    df = data
            
            if df.empty:
                print("DataFrame is empty for this ticker")
                continue
                
            # logic...
            close = df['Close']
            last = close.iloc[-1]
            print(f"Found price for {ticker}: {last}")

        except Exception as e:
            print(f"Error processing {ticker}: {e}")

except Exception as e:
    print(f"Overall download failed: {e}")
