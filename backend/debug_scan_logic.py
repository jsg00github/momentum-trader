
import sys
import os
import time

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import scan_engine
import screener
import logging

# Setup logging to see what happens
logging.basicConfig(level=logging.DEBUG)

print("--- Starting Debug Scan Logic ---")
try:
    print("Calling run_market_scan(limit=500, strategy='weekly_rsi')...")
    
    # Mocking cache to avoid interference
    # actually, use real cache to see if that's the issue
    
    result = scan_engine.run_market_scan(limit=500, strategy="weekly_rsi")
    
    print("\nScan Result:")
    print(result)
    
except Exception as e:
    print(f"\nCRASHED: {e}")
    import traceback
    traceback.print_exc()

print("--- End Debug Scan Logic ---")
