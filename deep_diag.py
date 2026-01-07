import yfinance as yf
import pandas as pd
import indicators
import screener
import scan_engine
import numpy as np

def debug_one_ticker(ticker):
    print(f"\n--- DEBUGGING: {ticker} ---")
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=False, threads=False)
        if df.empty:
            print(f"FAILED: No data for {ticker}")
            return
            
        print(f"Data shape: {df.shape}")
        
        # Handle MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            print(f"MultiIndex detected: {df.columns.levels[0].tolist()}")
            if ticker in df.columns.get_level_values(1):
                df = df.xs(ticker, axis=1, level=1)
                print("Resolved via level 1")
            elif ticker in df.columns.get_level_values(0):
                df = df.xs(ticker, axis=1, level=0)
                print("Resolved via level 0")
            else:
                print("Ticker not found in levels, flattening...")
                df.columns = [str(c[0]) if isinstance(c, tuple) else str(c) for c in df.columns]

        # Calculate Weekly Analytics
        print("Calculating Weekly RSI Analytics...")
        rsi_data = indicators.calculate_weekly_rsi_analytics(df)
        
        if not rsi_data:
            print("FAILED: rsi_data is None. Check weekly_df length or NaN.")
            # Let's inspect weekly_df manually
            weekly_df = df.resample('W-FRI').agg({'Close': 'last'})
            print(f"Weekly bars: {len(weekly_df)}")
            return
            
        print(f"Weekly RSI: {rsi_data['rsi']:.1f}")
        print(f"EMA3: {rsi_data['ema3']:.1f}, EMA14: {rsi_data['ema14']:.1f}")
        print(f"Bullish Trend (EMA3 > EMA14): {rsi_data['ema3'] > rsi_data['ema14']}")
        print(f"Signal Buy (30-50 RSI): {rsi_data['signal_buy']}")
        
        # Calculate other indicators
        print("Calculating Daily Indicators...")
        try:
            macd = indicators.calculate_daily_macd(df)
            ema60 = indicators.calculate_ema(df, 60)
            di_p, di_m, adx = indicators.calculate_adx_di(df)
            print(f"MACD: {macd:.2f}, EMA60: {ema60:.2f}")
            print(f"DI+: {di_p:.1f}, DI-: {di_m:.1f}, ADX: {adx:.1f}")
        except Exception as e:
            print(f"CRASH in Daily Indicators: {e}")
            import traceback
            traceback.print_exc()

        # Full Scan Call
        print("Running full scan logic...")
        res = screener.scan_rsi_crossover(df)
        if res:
            print(f"SUCCESS: Match found! {res}")
        else:
            print("NO MATCH found by screener logic.")

    except Exception as e:
        print(f"FATAL ERROR for {ticker}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Test a few diverse tickers
    test_tickers = ["AAPL", "IWM", "SPY", "AMZN", "NVDA", "TSLA"]
    for t in test_tickers:
        debug_one_ticker(t)
