
import yfinance as yf
import sys

# Windows console encoding fix
sys.stdout.reconfigure(encoding='utf-8')

tickers = [
    "GFGV6730FE.BA",
    "GFGV6730FE",
    "GFGC6730FE.BA",
    "GGAL.BA",
    "GFG.BA" 
]

print("Testing YFinance for Argentina Options...")

for t in tickers:
    print(f"\nChecking {t}...")
    try:
        tick = yf.Ticker(t)
        hist = tick.history(period="5d")
        if not hist.empty:
            print(f"[OK] Found data for {t}!")
            print(hist.tail())
        else:
            print(f"[NO DATA] No data for {t}")
            
            # Try getting info just in case
            try:
                info = tick.fast_info
                if info.last_price:
                    print(f"   (But found fast_info price: {info.last_price})")
            except:
                pass
                
    except Exception as e:
        print(f"[ERROR] fetching {t}: {e}")
