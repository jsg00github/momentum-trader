import requests
import json

url = "http://127.0.0.1:8000/api/analyze"
payload = {"ticker": "DXYZ"}

print(f"Testing {url} with {payload}")
res = requests.post(url, json=payload)

if res.status_code == 200:
    data = res.json()
    print("\n=== RESPONSE SUMMARY ===")
    print(f"Symbol: {data.get('metrics', {}).get('symbol')}")
    print(f"Current Close: {data.get('metrics', {}).get('current_close')}")
    print(f"Chart Data Points: {len(data.get('chart_data', []))}")
    
    if data.get('chart_data'):
        last = data['chart_data'][-1]
        print(f"\nLast Data Point:")
        print(f"  Date: {last.get('date')}")
        print(f"  Close: {last.get('close')}")
        print(f"  RSI Weekly: {last.get('rsi_weekly')}")
else:
    print(f"ERROR: {res.status_code}")
    print(res.text)
