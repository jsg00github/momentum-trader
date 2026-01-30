
import sys
import os
import pandas as pd
import yfinance as yf

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import screener
import indicators
import scan_engine

def debug_vcp(ticker):
    print(f"\n--- Debugging VCP for {ticker} ---")
    
    # 1. Download Data (Force 2y to ensure we have enough)
    print("Downloading 2y data...")
    df = yf.download(ticker, period="2y", interval="1d", progress=False, auto_adjust=False)
    
    if df.empty:
        print("Data is empty.")
        return

    # Normalize
    df = indicators.normalize_dataframe(df)
    
    print(f"Data Length: {len(df)} rows")
    
    # 2. Run VCP Logic manually to see where it fails
    # Copy-paste critical parts of scan_vcp_pattern to debug
    
    if len(df) < 250:
        print(f"FAIL: Length {len(df)} < 250")
        return

    close = df['Close'].values
    high = df['High'].values
    low = df['Low'].values
    volume = df['Volume'].values
    
    last_close = close[-1]
    
    sma_50 = pd.Series(close).rolling(50).mean().values
    sma_200 = pd.Series(close).rolling(200).mean().values
    
    s50 = sma_50[-1]
    s200 = sma_200[-1]
    
    print(f"Price: {last_close:.2f}, SMA50: {s50:.2f}, SMA200: {s200:.2f}")
    
    if last_close < s50:
        print("FAIL: Price < SMA50")
    if last_close < s200:
        print("FAIL: Price < SMA200")
    if s50 < s200:
        print("FAIL: SMA50 < SMA200 (Not in Stage 2)")
        
    # Relative Strength
    price_30d_ago = close[-30]
    rs_30d = ((last_close / price_30d_ago) - 1) * 100
    print(f"RS 30d: {rs_30d:.2f}%")
    
    # Contractions
    analysis_window = 60
    window_high = high[-analysis_window:]
    window_low = low[-analysis_window:]
    
    segment_size = analysis_window // 4
    contractions = []
    
    print("Contractions:")
    for i in range(4):
        start = i * segment_size
        end = (i + 1) * segment_size
        seg_high = window_high[start:end].max()
        seg_low = window_low[start:end].min()
        seg_range = seg_high - seg_low
        seg_range_pct = (seg_range / seg_low) * 100 if seg_low > 0 else 100
        contractions.append(seg_range_pct)
        print(f"  Seg {i}: Range {seg_range_pct:.2f}% (High: {seg_high:.2f}, Low: {seg_low:.2f})")
        
    contraction_count = 0
    for i in range(1, len(contractions)):
        if contractions[i] < contractions[i-1]:
            contraction_count += 1
            
    print(f"Contraction Count: {contraction_count} (Need >= 2)")
    
    if contraction_count < 2:
        print("FAIL: No volatility contraction detected")
        
    # Final Consolidation
    final_10d_high = high[-10:].max()
    final_10d_low = low[-10:].min()
    final_range_pct = ((final_10d_high - final_10d_low) / final_10d_low) * 100
    print(f"Final 10d Range: {final_range_pct:.2f}% (Limit: 15%)")
    
    if final_range_pct > 15:
        print("FAIL: Final consolidation too loose")

    # Volume Dry Up
    avg_vol_50 = volume[-50:].mean()
    avg_vol_10 = volume[-10:].mean()
    volume_dry_up = avg_vol_10 / avg_vol_50
    print(f"Volume Ratio (10d/50d): {volume_dry_up:.2f} (Limit: 0.9)")
    
    if volume_dry_up > 0.9:
        print("FAIL: Volume not drying up")
        
    # Base Depth
    lookback_for_peak = 90
    recent_peak = high[-lookback_for_peak:].max()
    recent_trough = low[-lookback_for_peak:].min()
    base_depth = ((recent_peak - recent_trough) / recent_peak) * 100
    print(f"Base Depth: {base_depth:.2f}% (Limit: 5-40%)")

    if base_depth > 40 or base_depth < 5:
        print("FAIL: Base depth invalid")

    result = screener.scan_vcp_pattern(df, ticker)
    if result:
        print("SUCCESS: VCP Pattern Found!")
    else:
        print("RESULT: None (filtered out)")

if __name__ == "__main__":
    # Test with strong momentum stocks or potential setups
    tickers = ["NVDA", "PLTR", "APP", "MSTR", "TSLA"] 
    for t in tickers:
        debug_vcp(t)
