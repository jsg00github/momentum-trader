import yfinance as yf
import pandas as pd
import backend.screener as screener
import logging
import sys

# Setup basic logging to see what's happening
logging.basicConfig(level=logging.INFO)

target_tickers = ["VTYX", "SNDK", "EVAX", "BETR"]
print(f"Checking targets: {target_tickers}")

# 1. Check if they exist in the Universe
print("\n--- Checking Universe Availability ---")
try:
    universe = screener.get_sec_tickers()
    print(f"Total tickers in universe: {len(universe)}")
    
    missing = []
    for t in target_tickers:
        if t in universe:
            print(f"[FOUND] {t} is in the universe list.")
        else:
            print(f"[MISSING] {t} is NOT in the universe list.")
            missing.append(t)
            
    if missing:
        print(f"WARNING: The following tickers are not being scanned: {missing}")
except Exception as e:
    print(f"Error fetching universe: {e}")

# 2. Analyze Logic
print("\n--- Analyzing Logic per Ticker ---")
for ticker in target_tickers:
    print(f"\n[{ticker}]")
    try:
        df = yf.download(ticker, period=screener.PERIOD, interval=screener.INTERVAL, progress=False, auto_adjust=False)
        
        if df.empty:
            print("  DataFrame is empty!")
            continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]

        df = df.sort_index().dropna()
        if len(df) == 0:
             print("  Dataframe empty after dropna")
             continue

        result = screener.compute_3m_pattern(df)
        if result:
            print("  >>> PASS: Pattern Found!")
            print(f"      3M: {result['ret_3m_pct']:.2f}%")
            print(f"      1M: {result['ret_1m_pct']:.2f}%")
            print(f"      1W: {result['ret_1w_pct']:.2f}%")
        else:
            print("  >>> FAIL: Pattern NOT Found")
            # print metrics manually to see why
            close = df["Close"].values
            i_last = len(df) - 1
            if i_last > screener.THREEM_BARS:
                last = close[-1]
                p3 = close[-1 - screener.THREEM_BARS]
                r3 = (last/p3) - 1.0
                print(f"      3M Date: {df.index[-1 - screener.THREEM_BARS].date()} -> {r3*100:.2f}% (Req > {screener.MIN_RET_3M*100}%)")
            
            if i_last > screener.MONTH_BARS:
                p1 = close[-1 - screener.MONTH_BARS]
                r1 = (last/p1) - 1.0
                print(f"      1M Date: {df.index[-1 - screener.MONTH_BARS].date()} -> {r1*100:.2f}% (Req {screener.MIN_RET_1M*100}% to {screener.MAX_RET_1M*100}%)")

            if i_last > screener.WEEK_BARS:
                pw = close[-1 - screener.WEEK_BARS]
                rw = (last/pw) - 1.0
                print(f"      1W Date: {df.index[-1 - screener.WEEK_BARS].date()} -> {rw*100:.2f}% (Req > {screener.MIN_RET_1W*100}%)")

    except Exception as e:
        print(f"  Exception: {e}")
