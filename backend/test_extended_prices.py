
import yfinance as yf
import datetime
import pytz

def get_extended_data(ticker):
    print(f"\n--- Testing {ticker} ---")
    t = yf.Ticker(ticker)
    
    # Method 1: fast_info
    print("1. fast_info:")
    try:
        info = t.fast_info
        print(f"   last_price: {info.last_price}")
        print(f"   previous_close: {info.previous_close}")
        if info.last_price and info.previous_close:
            change = ((info.last_price - info.previous_close) / info.previous_close) * 100
            print(f"   Calculated Change: {change:.2f}%")
    except Exception as e:
        print(f"   Error: {e}")

    # Method 2: History with prepost=True
    print("2. History (1d, 1m, prepost=True):")
    try:
        hist = t.history(period="1d", interval="1m", prepost=True)
        if not hist.empty:
            last_row = hist.iloc[-1]
            print(f"   Last Index: {last_row.name}")
            print(f"   Close: {last_row['Close']}")
        else:
            print("   Empty history")
    except Exception as e:
        print(f"   Error: {e}")

# Test known tickers (some likely to move in post-market)
get_extended_data("SPY")
get_extended_data("QQQ")
get_extended_data("TSLA")
