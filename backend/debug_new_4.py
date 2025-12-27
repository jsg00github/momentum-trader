import yfinance as yf
import screener
import pandas as pd
import numpy as np

tickers = ["GSIT", "EOSE", "IHRT", "CIFR"]

print(f"Debug Scan for: {tickers}")
print(f"Screener Config: 3M={screener.MIN_RET_3M}, 1M_range=[{screener.MIN_RET_1M}, {screener.MAX_RET_1M}], 1W={screener.MIN_RET_1W}")

for t in tickers:
    print(f"\n--- Checking {t} ---")
    try:
        # Exact same call as main.py
        df = yf.download(t, period=screener.PERIOD, interval=screener.INTERVAL, progress=False, auto_adjust=False)
        
        if df is None or df.empty:
            print("  FAIL: DataFrame is empty")
            continue

        if isinstance(df.columns, pd.MultiIndex):
            print("  Flattening MultiIndex columns")
            df.columns = [c[0] for c in df.columns]
            
        print(f"  Last date: {df.index[-1]}")
        
        res = screener.compute_3m_pattern(df)
        if res:
            print(f"  >>> MATCH FOUND: 3M={res['ret_3m_pct']:.2f}% 1W={res['ret_1w_pct']:.2f}%")
        else:
            print("  >>> NO MATCH. Logic breakdown:")
            # Re-run logic with prints to see why
            close = df["Close"].values
            if len(close) < screener.THREEM_BARS:
                print("    Not enough data")
                continue
                
            last_close = close[-1]
            price_3m = close[-1 - screener.THREEM_BARS]
            ret_3m = (last_close / price_3m) - 1.0
            print(f"    3M Ret: {ret_3m:.2%} (Needs > {screener.MIN_RET_3M:.0%})")
            
            if ret_3m <= screener.MIN_RET_3M: print("    FAIL: 3M Return too low")

            price_1m = close[-1 - screener.MONTH_BARS]
            ret_1m = (last_close / price_1m) - 1.0
            print(f"    1M Ret: {ret_1m:.2%} (Needs {screener.MIN_RET_1M:.0%} to {screener.MAX_RET_1M:.0%})")
            if not (screener.MIN_RET_1M <= ret_1m <= screener.MAX_RET_1M): print("    FAIL: 1M Return out of range")
            
            price_1w = close[-1 - screener.WEEK_BARS]
            ret_1w = (last_close / price_1w) - 1.0
            print(f"    1W Ret: {ret_1w:.2%} (Needs > {screener.MIN_RET_1W:.0%})")
            if ret_1w <= screener.MIN_RET_1W: print("    FAIL: 1W Return too low")

    except Exception as e:
        print(f"  Error: {e}")
