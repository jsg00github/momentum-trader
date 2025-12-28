import yfinance as yf
import pandas as pd

def check_options_info(ticker_symbol="AAPL"):
    print(f"Checking options info for {ticker_symbol}...")
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        
        print("--- Info Keys relevant to Options ---")
        keys = [k for k in info.keys() if 'put' in k.lower() or 'call' in k.lower() or 'ratio' in k.lower()]
        for k in keys:
            print(f"{k}: {info[k]}")
            
        if 'putCallRatio' in info:
            print(f"Direct Put/Call Ratio: {info['putCallRatio']}")
        else:
            print("No direct putCallRatio found.")
            
        print("\n--- Options Chain Check ---")
        expirations = ticker.options
        if expirations:
            print(f"Expirations found: {len(expirations)}")
            print(f"First exp: {expirations[0]}")
            
            chain = ticker.option_chain(expirations[0])
            calls = chain.calls
            puts = chain.puts
            
            print(f"Calls Vol: {calls['volume'].sum()}")
            print(f"Puts Vol: {puts['volume'].sum()}")
            print(f"Calls OI: {calls['openInterest'].sum()}")
            print(f"Puts OI: {puts['openInterest'].sum()}")
        else:
            print("No options found.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_options_info()
