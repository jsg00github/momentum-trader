import yfinance as yf
import screener
import pandas as pd
import numpy as np

tickers = ["GSIT", "BE"]

print(f"Debug Scan for: {tickers}")
print(f"Screener Config: 3M={screener.MIN_RET_3M}, 1M_range=[{screener.MIN_RET_1M}, {screener.MAX_RET_1M}], 1W={screener.MIN_RET_1W}")

for t in tickers:
    print(f"\n--- Checking {t} ---")
    try:
        df = yf.download(t, period=screener.PERIOD, interval=screener.INTERVAL, progress=False, auto_adjust=False)
        
        if df is None or df.empty:
            print("  DataFrame is empty")
            continue

        if isinstance(df.columns, pd.MultiIndex):
            print("  Flattening MultiIndex columns")
            df.columns = [c[0] for c in df.columns]
            
        print(f"  Last date: {df.index[-1]}")
        
        # Check volume
        vol_s = pd.Series(df["Volume"].values)
        avg_vol_60 = vol_s.rolling(60).mean().iloc[-1]
        print(f"  Avg Vol (60): {avg_vol_60:,.0f} (Min: {screener.MIN_AVG_VOL:,.0f})")
        
        close = df["Close"].values
        last_close = close[-1]
        print(f"  Close: {last_close:.2f}")

        # 3M
        if len(close) > screener.THREEM_BARS:
            price_3m_ago = close[-1 - screener.THREEM_BARS]
            ret_3m = (last_close / price_3m_ago) - 1.0
            print(f"  3M Ret: {ret_3m:.2%} (Min: {screener.MIN_RET_3M:.0%}) -> {'PASS' if ret_3m > screener.MIN_RET_3M else 'FAIL'}")
        else:
            print("  Not enough data for 3M")

        # 1M
        if len(close) > screener.MONTH_BARS:
            price_1m_ago = close[-1 - screener.MONTH_BARS]
            ret_1m = (last_close / price_1m_ago) - 1.0
            print(f"  1M Ret: {ret_1m:.2%} (Range: {screener.MIN_RET_1M:.0%} to {screener.MAX_RET_1M:.0%}) -> {'PASS' if screener.MIN_RET_1M <= ret_1m <= screener.MAX_RET_1M else 'FAIL'}")
        else:
            print("  Not enough data for 1M")

        # 1W
        if len(close) > screener.WEEK_BARS:
            price_1w_ago = close[-1 - screener.WEEK_BARS]
            ret_1w = (last_close / price_1w_ago) - 1.0
            print(f"  1W Ret: {ret_1w:.2%} (Min: {screener.MIN_RET_1W:.0%}) -> {'PASS' if ret_1w > screener.MIN_RET_1W else 'FAIL'}")
        else:
            print("  Not enough data for 1W")

        # Full check
        res = screener.compute_3m_pattern(df)
        if res:
            print("  >>> FUNCTION RESULT: MATCH FOUND")
        else:
            print("  >>> FUNCTION RESULT: NO MATCH")

    except Exception as e:
        print(f"  Error: {e}")
