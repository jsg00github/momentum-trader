import yfinance as yf
import pandas as pd
import sqlite3
import os

# Connect to DB to get VSTS entry date
DB_PATH = 'backend/trades.db'
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT ticker, entry_date FROM trades WHERE ticker='VSTS' AND status='OPEN'")
rows = cursor.fetchall()
conn.close()

print(f"Trades for VSTS: {rows}")

if not rows:
    print("No open trades for VSTS found. Using hardcoded dummy date if needed or exiting.")
    # Assuming user has it open, maybe recent import?
    # Let's try to fetch VSTS data anyway with a hypothetical date if empty
    dates = ['2025-06-11'] # From previous valid log in step 445 output
else:
    dates = [r[1] for r in rows]

ticker = 'VSTS'
print(f"Fetching data for {ticker}...")
try:
    data = yf.download(ticker, period="2y", progress=False)
    
    if data.empty:
        print("Empty data!")
        exit()

    print(f"Data shape: {data.shape}")
    print(f"Data index Start: {data.index[0]}, End: {data.index[-1]}")
    
    # Handle cleaning like in main app
    df = data
    # yfinance 0.2.x might return MultiIndex columns even for single ticker? 
    # Let's check columns
    print(f"Columns: {df.columns}")
    
    # Calculate EMAs
    close = df['Close']
    low = df['Low']
    
    # Support both Series (if single level) and DataFrame (if multi level) access
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    if isinstance(low, pd.DataFrame):
        low = low.iloc[:, 0]
        
    ema_8 = close.ewm(span=8, adjust=False).mean()
    
    for d_str in dates:
        print(f"\nAnalyzing from Entry Date: {d_str}")
        try:
            entry_ts = pd.Timestamp(d_str)
            mask = df.index >= entry_ts
            
            # Slice
            c_slice = close[mask]
            l_slice = low[mask]
            e8_slice = ema_8[mask]
            
            print(f"Days since entry: {len(c_slice)}")
            
            # Check Low < EMA
            v_low = (l_slice < e8_slice).sum()
            print(f"Violations (Low < EMA8): {v_low}")
            
            # Check Close < EMA
            violation_mask = c_slice < e8_slice
            v_close = violation_mask.sum()
            print(f"Violations (Close < EMA8): {v_close}")
            
            # Print ALL violation dates to debug
            violated_dates = c_slice[violation_mask].index
            print(f"Violation Dates: {[d.strftime('%Y-%m-%d') for d in violated_dates]}")
            
            # Print first 5 and last 5 for quick check
            if len(violated_dates) > 0:
                print(f"First violation: {violated_dates[0]}")
                print(f"Last violation: {violated_dates[-1]}")
                
            # Verify filtering
            print(f"Filter Start Date: {entry_ts}")
            print(f"First Data Date in Slice: {c_slice.index[0]}")
            
        except Exception as e:
            print(f"Error parsing date: {e}")

except Exception as e:
    print(f"Error downloading: {e}")
