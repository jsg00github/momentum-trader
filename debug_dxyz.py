
import yfinance as yf
import pandas as pd
from backend import screener

def debug_dxyz():
    ticker = "DXYZ"
    print(f"--- Debugging {ticker} ---")
    
    # 1. Raw Download
    print("1. Raw Download...")
    df = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=False)
    
    if df.empty:
        print("DF Empty!")
    else:
        print(f"DF Shape: {df.shape}")
        if isinstance(df.columns, pd.MultiIndex):
            print("MultiIndex Columns detected")
            print(df.columns)
            # Try to fix
            try:
                df_fixed = df.xs(ticker, axis=1, level=1)
                print(f"Fixed Shape: {df_fixed.shape}")
                print(f"Last Close (Fixed): {df_fixed['Close'].iloc[-1]}")
            except:
                print("Could not fix MultiIndex via xs")
                # Maybe level 0?
                print("Cols level 0:", df.columns.get_level_values(0))
        else:
            print(f"Last Close (Single): {df['Close'].iloc[-1]}")

    # 2. Screener Logic
    print("\n2. Testing screener.analyze_bull_flag...")
    try:
        res = screener.analyze_bull_flag(ticker)
        if res:
            print("Result found via Bull Flag Logic")
            # inspect chart data last point
            last_pt = res['chart_data'][-1]
            print(f"Chart Data Last Close: {last_pt['close']}")
        else:
            print("No Bull Flag result (Good, fall through to main)")
    except Exception as e:
        print(f"Screener Error: {e}")

if __name__ == "__main__":
    debug_dxyz()
