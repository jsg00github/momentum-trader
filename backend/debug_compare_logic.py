
import sys
import os
import pandas as pd
import yfinance as yf
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import screener

def test_ticker(ticker):
    print(f"\n--- Testing {ticker} ---")
    try:
        df = yf.download(ticker, period=screener.PERIOD, interval=screener.INTERVAL, progress=False, auto_adjust=False)
        print(f"Data shape: {df.shape}")
        if df.empty:
            print("DATAFRAME IS EMPTY!")
            return

        print("Last 5 dates:")
        print(df.index[-5:])
        
        # Manually run the checks from screener.py to see where it fails
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        
        df = df.sort_index().dropna()
        close = df["Close"].values
        # Debugging calculations
        
        last_close = close[-1]
        print(f"Last Close: {last_close}")

        i_last = len(df) - 1
        
        # Check indices logic
        min_len = max(screener.THREEM_BARS, 60) + 5
        print(f"Len: {len(df)} vs Min Len: {min_len}")
        
        if len(df) < min_len:
            print(f"Valid length fail: {len(df)} < {min_len}")
        
        price_3m_ago = close[-1 - screener.THREEM_BARS]
        ret_3m = (last_close / price_3m_ago) - 1.0
        print(f"Limit 3M {screener.THREEM_BARS} bars ago index: {-1 - screener.THREEM_BARS}")
        print(f"3M Price: {price_3m_ago:.2f}, Ret 3M: {ret_3m*100:.2f}% (Req: >{screener.MIN_RET_3M*100}%)")
        
        price_1m_ago = close[-1 - screener.MONTH_BARS]
        ret_1m = (last_close / price_1m_ago) - 1.0
        print(f"1M Price: {price_1m_ago:.2f}, Ret 1M: {ret_1m*100:.2f}% (Req: {screener.MIN_RET_1M*100}% to {screener.MAX_RET_1M*100}%)")
        
        price_1w_ago = close[-1 - screener.WEEK_BARS]
        ret_1w = (last_close / price_1w_ago) - 1.0
        print(f"1W Price: {price_1w_ago:.2f}, Ret 1W: {ret_1w*100:.2f}% (Req: >{screener.MIN_RET_1W*100}%)")

        # Now run actual function
        result = screener.compute_3m_pattern(df)
        if result:
            print(">>> RESULT: MATCH FOUND!")
            print(result)
        else:
            print(">>> RESULT: None (Filtered out)")
            
    except Exception as e:
        print(f"Exception: {e}")


if __name__ == "__main__":
    # Check if GSIT is in tickers
    tickers = screener.get_sec_tickers()
    if "GSIT" in tickers:
        print("GSIT found in SEC ticker list.")
    else:
        print("GSIT NOT found in SEC ticker list.")

    test_ticker("GSIT")

