
import pandas as pd
import yfinance as yf
import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
import elliott

print("Fetching data for NVDA...")
df = yf.download("NVDA", period="1y", interval="1d", progress=False, auto_adjust=False)
if isinstance(df.columns, pd.MultiIndex):
    df.columns = [c[0] for c in df.columns]
    
print(f"Data shape: {df.shape}")

result = elliott.analyze_elliott_waves(df)
print("\n--- ABC Logic Result ---")
print(f"Pattern: {result['elliott_wave'].get('pattern')}")
print(f"Expert: {result['elliott_wave'].get('expert_analysis')}")
print(f"Labels: {[l['label'] + '@' + str(l['price']) for l in result['wave_labels']]}")
print(f"Interpretation: {result.get('interpretation')}")
