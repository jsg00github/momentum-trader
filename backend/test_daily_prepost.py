
import yfinance as yf

def test_daily_prepost():
    tickers = ["SPY", "TSLA"]
    print(f"Testing Batch 5d prepost=True for {tickers}...")
    
    # Intentionally using defaults (interval=1d implicitly)
    data = yf.download(tickers, period="5d", prepost=True, group_by='ticker', progress=False)
    
    for ticker in tickers:
        print(f"\n{ticker}:")
        if ticker in data.columns or (isinstance(data.columns, pd.MultiIndex) and ticker in data.columns.levels[0]):
             # Handle weird multiindex if needed, but group_by ticker usually gives top level ticker
             try:
                 df = data[ticker]
                 last_price = df['Close'].iloc[-1]
                 last_time = df.index[-1]
                 print(f"  Time: {last_time}")
                 print(f"  Close: {last_price}")
             except:
                 pass
        else:
             print("  No data")

import pandas as pd
test_daily_prepost()
