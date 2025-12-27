import yfinance as yf
import pandas as pd

tickers = ['BYON', 'MSTU', 'VSTS', 'LAR', 'SPY', 'SMC', 'ETHU', 'RDDT', 'FCEL'] # From logs
print(f"Downloading: {tickers}")

try:
    data = yf.download(tickers, period="2y", progress=False, threads=False)
    print("\nDownload complete.")
    print("Columns:", data.columns)
    print("Shape:", data.shape)
    
    # Simulate get_open_prices logic
    for t in tickers:
        print(f"\nProcessing {t}...")
        try:
            if isinstance(data.columns, pd.MultiIndex):
                try:
                    df = data.xs(t, axis=1, level=1)
                except KeyError:
                    # Try level 0?
                    df = data.xs(t, axis=1, level=0)
            else:
                df = data
            
            if df.empty:
                print(f"  DF Empty for {t}")
            else:
                print(f"  Success. Last close: {df['Close'].iloc[-1]}")
        except Exception as e:
            print(f"  Error extracting {t}: {e}")

except Exception as e:
    print(f"CRITICAL DOWNLOAD ERROR: {e}")
