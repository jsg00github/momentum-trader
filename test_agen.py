import yfinance as yf
import pandas as pd

ticker = "AGEN"
print(f"=== Testing {ticker} ===\n")

# Test 1: What does yfinance return?
df = yf.download(ticker, period="5d", interval="1d", progress=False)
print(f"Downloaded {len(df)} rows")
print(f"Columns: {df.columns.tolist()}")

if isinstance(df.columns, pd.MultiIndex):
    print("WARNING: MultiIndex detected!")
    print(df.columns)
    
if not df.empty:
    print(f"\nLast Close: ${df['Close'].iloc[-1]:.2f}")
    print(f"Last 5 closes:")
    print(df['Close'].tail())
    
# Test 2: Get ticker info
try:
    t = yf.Ticker(ticker)
    info = t.info
    print(f"\nTicker Info:")
    print(f"  Long Name: {info.get('longName', 'N/A')}")
    print(f"  Symbol: {info.get('symbol', 'N/A')}")
    print(f"  Current Price: ${info.get('currentPrice', 'N/A')}")
    print(f"  Previous Close: ${info.get('previousClose', 'N/A')}")
except Exception as e:
    print(f"Error getting info: {e}")
