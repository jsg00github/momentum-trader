
import requests
import json

try:
    print("Checking Market Dashboard Endpoint...")
    r = requests.get("http://127.0.0.1:8000/api/market-status")
    if r.status_code == 200:
        data = r.json()
        print("Success!")
        print(json.dumps(data, indent=2))
    else:
        print(f"Error {r.status_code}: {r.text}")
except Exception as e:
    print(f"Failed: {e}")
