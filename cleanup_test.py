import requests
try:
    requests.delete("http://127.0.0.1:8000/api/trades/25", timeout=5)
    print("Deleted trade 25")
except Exception as e:
    print(e)
