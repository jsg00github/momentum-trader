
import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from backend.main import process_ticker

def test_api_scan():
    # Test a ticker that might have the setup or just generic test
    # NVDA is bullish, might trigger or not depending on the specific week
    # But let's just see if it runs and returns a structure (or None) without error.
    
    ticker = "NVDA"
    print(f"Testing process_ticker with strategy='weekly_rsi' for {ticker}...")
    
    try:
        result = process_ticker(ticker, use_cache=False, strategy="weekly_rsi")
        
        if result:
            print("SUCCESS: Result found!")
            print(result)
        else:
            print("SUCCESS: Logic ran, but no signal found (expected for most stocks).")
            
    except Exception as e:
        print(f"FAILED: Error running process_ticker: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api_scan()
