
import yfinance as yf
import pandas as pd
from backend import indicators

def debug_exits():
    tickers = ["FCEL", "GSIT", "ARCT"]
    print(f"Checking Exit Signals for: {tickers}")
    
    # Fetch data (1y daily, same as trade_journal)
    data = yf.download(tickers, period="2y", interval="1d", progress=False, threads=False)
    
    for t in tickers:
        print(f"\n--- {t} ---")
        try:
            # Handle MultiIndex extraction
            if isinstance(data.columns, pd.MultiIndex):
                try:
                    df = data.xs(t, axis=1, level=1)
                except:
                    df = data.xs(t, axis=1, level=0)
            else:
                df = data

            if df.empty:
                print("No data found.")
                continue
                
            # Run Indicators
            results = indicators.calculate_weekly_rsi_analytics(df)
            
            if not results:
                print("Calculation returned None (insufficient data?)")
                continue
                
            sma3 = results['sma3']
            sma14 = results['sma14']
            rsi = results['rsi']
            sell_signal = results['signal_sell']
            
            print(f"Last Date: {results['weekly_closes'][-1]}") # Crude way to check date logic if I returned indices, but lists don't have dates.
            # Let's check the DF used inside just to be sure about dates
            weekly_df = df.resample('W-FRI').agg({'Close': 'last'})
            last_date = weekly_df.index[-1]
            
            print(f"Analysis Date: {last_date.date()}")
            print(f"RSI:   {rsi:.2f}")
            print(f"SMA 3: {sma3:.2f}")
            print(f"SMA 14:{sma14:.2f}")
            print(f"Diff:  {sma3 - sma14:.4f}")
            print(f"Signal SELL (SMA3 < SMA14): {sell_signal}")
            
            if sma3 < sma14:
                print(">> CROSS CONFIRMED (Bearish)")
            else:
                print(">> NO CROSS (SMA3 >= SMA14)")
                
        except Exception as e:
            print(f"Error processing {t}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    debug_exits()
