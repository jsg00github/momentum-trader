import sqlite3
import ccxt
import json
from pathlib import Path

DB_PATH = Path('crypto_journal.db')

def get_keys():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT api_key, api_secret FROM binance_config WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return row

def debug():
    keys = get_keys()
    if not keys:
        print("No keys found in DB")
        return

    api_key, api_secret = keys
    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True
    })

    print("--- Fetching SPOT Balance ---")
    try:
        balance = exchange.fetch_balance()
        total = balance['total']
        print("Non-zero SPOT balances:")
        for coin, amount in total.items():
            if amount > 0:
                print(f"{coin}: {amount}")
    except Exception as e:
        print(f"Error fetching SPOT: {e}")

    print("\n--- Fetching FUNDING Balance ---")
    try:
        balance_funding = exchange.fetch_balance({'type': 'funding'})
        total = balance_funding['total']
        print("Non-zero FUNDING balances:")
        for coin, amount in total.items():
            if amount > 0:
                print(f"{coin}: {amount}")
    except Exception as e:
        print(f"Error fetching FUNDING: {e}")

    print("\n--- Fetching FUTURE Balance ---")
    try:
        balance_future = exchange.fetch_balance({'type': 'future'})
        total = balance_future['total']
        print("Non-zero FUTURE balances:")
        for coin, amount in total.items():
            if amount > 0:
                print(f"{coin}: {amount}")
    except Exception as e:
        print(f"Error fetching FUTURE: {e}")

if __name__ == "__main__":
    debug()
