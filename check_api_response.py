
import requests
import json


tickers = ["GOOGL", "AMZN", "MSFT", "TSLA", "AMD", "META"]
for t in tickers:
    print(f"\nChecking {t}...")
    try:
        r = requests.post("http://127.0.0.1:8000/api/analyze", json={"ticker": t})
        if r.status_code == 200:
            data = r.json()
            metrics = data.get("metrics", {})
            print(f"{t} is_bull_flag: {metrics.get('is_bull_flag')}")
            if metrics.get('is_bull_flag'):
                print(f"  Mast Duration: {metrics.get('mast_duration_days')}")
                print(f"  Height: {metrics.get('mast_height')}")
                print(f"  Slope: {metrics.get('slope')}")
        else:
            print(f"Error {r.status_code}")
    except Exception as e:
        print(f"Failed: {e}")

