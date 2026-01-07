import market_data
import json

print("Starting Market Status Diagnosis...")
try:
    print("Testing get_market_status()...")
    status = market_data.get_market_status()
    print("\n--- INDICES STATUS ---")
    for k, v in status.get('indices', {}).items():
        print(f"{k}: {v.get('desc')} (Price: {v.get('price')})")
    
    print("\n--- EXPERT SUMMARY ---")
    print(status.get('expert_summary', {}).get('session'))
except Exception as e:
    print(f"\nCRITICAL ERROR: {e}")
