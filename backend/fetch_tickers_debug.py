
import requests

def test_fetch():
    # Popular aggregated ticker source
    url = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"
    try:
        print(f"Fetching from {url}...")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        text = resp.text
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        print(f"SUCCESS: Fetched {len(lines)} tickers.")
        print(f"Sample: {lines[:5]}")
    except Exception as e:
        print(f"FAIL: {e}")

if __name__ == "__main__":
    test_fetch()
