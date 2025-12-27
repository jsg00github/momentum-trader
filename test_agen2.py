import yfinance as yf
import pandas as pd

ticker = "AGEN"
print(f"=== Testing {ticker} ===\n")

# Test with auto_adjust=False like in backend
df = yf.download(ticker, period="5d", interval="1d", progress=False, auto_adjust=False)
print(f"Downloaded {len(df)} rows")
print(f"Type: {type(df)}")
print(f"Columns type: {type(df.columns)}")

if isinstance(df.columns, pd.MultiIndex):
    print("\n⚠️ MultiIndex detected!")
    print(f"Levels: {df.columns.names}")
    print(f"Columns:\n{df.columns.tolist()}")
    
    # Try to fix it
    try:
        df_fixed = df.xs(ticker, level=1, axis=1)
        print(f"\n✅ Fixed with xs()")
        print(f"New columns: {df_fixed.columns.tolist()}")
        print(f"Last Close: ${df_fixed['Close'].iloc[-1]:.2f}")
    except Exception as e:
        print(f"\n❌ xs() failed: {e}")
        # Try alternative
        df.columns = [c[0] for c in df.columns]
        print(f"Fixed with [c[0]]")
        print(f"New columns: {df.columns.tolist()}")
        
        # Check for duplicates
        if df.columns.duplicated().any():
            print(f"⚠️ DUPLICATE COLUMNS FOUND!")
            dup_cols = df.columns[df.columns.duplicated()].tolist()
            print(f"Duplicates: {dup_cols}")
        
        df = df.loc[:, ~df.columns.duplicated()]
        print(f"After dedup: {df.columns.tolist()}")
        print(f"Last Close: ${df['Close'].iloc[-1]:.2f}")
else:
    print("Single index columns")
    print(f"Columns: {df.columns.tolist()}")
    if not df.empty:
        print(f"Last Close: ${df['Close'].iloc[-1]:.2f}")
