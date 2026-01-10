import requests
import json

response = requests.get("http://localhost:8000/api/trades/analytics/open")
data = response.json()

print("=== BACKEND API RESPONSE ===")
print(json.dumps(data, indent=2))

# Check for key fields
print("\n=== VALIDATION ===")
print(f"Has 'exposure': {'exposure' in data}")
print(f"Has 'asset_allocation': {'asset_allocation' in data}")
print(f"Has 'holdings': {'holdings' in data}")
print(f"Has 'suggestions': {'suggestions' in data}")

if 'exposure' in data:
    print(f"\nExposure keys: {list(data['exposure'].keys())}")
    print(f"Portfolio Beta: {data['exposure'].get('portfolio_beta')}")
    print(f"Portfolio PE: {data['exposure'].get('portfolio_pe')}")

if 'asset_allocation' in data:
    print(f"\nAsset Allocation: {data['asset_allocation']}")

if 'holdings' in data:
    print(f"\nHoldings count: {len(data['holdings'])}")
    if data['holdings']:
        print(f"First holding: {data['holdings'][0]}")
