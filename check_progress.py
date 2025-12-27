import requests
import time

try:
    res = requests.get("http://127.0.0.1:8000/api/scan/progress")
    print(res.json())
except Exception as e:
    print(f"Error: {e}")
