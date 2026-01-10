import requests
import pandas as pd

def get_sec_tickers():
    print("Attempting to fetch SEC tickers...")
    url = "https://www.sec.gov/files/company_tickers.json"

    # User's suggested header
    headers = {
        "User-Agent": "Javier Screener 3M Rally (contacto: test@example.com)"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {resp.status_code}")
        resp.raise_for_status()

        data = resp.json()
        print(f"Successfully fetched {len(data)} items from SEC.")
        
        tickers = []
        for _, v in data.items():
            t = v.get("ticker")
            if t:
                tickers.append(t)
        
        print(f"Parsed {len(tickers)} unique tickers.")
        return tickers

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return []

if __name__ == "__main__":
    get_sec_tickers()
