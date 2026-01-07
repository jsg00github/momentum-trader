import requests
import time

print("Testing analytics endpoint...")
start = time.time()

try:
    response = requests.get("http://localhost:8000/api/trades/analytics/open", timeout=10)
    elapsed = time.time() - start
    print(f"Response received in {elapsed:.2f}s")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("\n✓ API returned successfully")
        print(f"  - Has exposure: {'exposure' in data}")
        print(f"  - Has asset_allocation: {'asset_allocation' in data}")
        print(f"  - Has holdings: {'holdings' in data}")
        
        if 'asset_allocation' in data:
            print(f"\n Asset Allocation items: {len(data.get('asset_allocation', []))}")
        if 'holdings' in data:
            print(f" Holdings items: {len(data.get('holdings', []))}")
    else:
        print(f"✗ Error: {response.text}")
        
except requests.Timeout:
    print("✗ Request timed out after 10s")
except Exception as e:
    print(f"✗ Error: {e}")
