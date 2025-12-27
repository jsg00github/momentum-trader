import requests
import json

try:
    response = requests.get("http://127.0.0.1:8000/api/trades/analytics/open")
    print(f"Status Code: {response.status_code}")
    print(response.text[:500])
except Exception as e:
    print(f"Request failed: {e}")
