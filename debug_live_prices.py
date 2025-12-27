import requests
import json

try:
    response = requests.get("http://127.0.0.1:8000/api/trades/open-prices")
    print(f"Status Code: {response.status_code}")
    try:
        data = response.json()
        print(f"Key Count: {len(data)}")
        print("Sample Data:", json.dumps(data, indent=2)[:500])
    except:
        print("Response not JSON:", response.text[:500])
except Exception as e:
    print(f"Request failed: {e}")
