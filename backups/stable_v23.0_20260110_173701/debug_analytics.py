import sqlite3
import os
import yfinance as yf
import pandas as pd

DB_PATH = "trades.db"

def debug_analytics():
    if not os.path.exists(DB_PATH):
        print("Database not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT ticker FROM trades WHERE status = 'OPEN'")
    rows = cursor.fetchall()
    tickers = list(set(row['ticker'] for row in rows if row['ticker']))
    print(f"Open Tickers: {tickers}")
    
    if not tickers:
        print("No open positions found.")
        return

    print("--- Testing yfinance Tickers.info ---")
    try:
        yf_tickers = yf.Tickers(" ".join(tickers))
        for t in tickers:
            try:
                info = yf_tickers.tickers[t].info
                print(f"Ticker: {t}")
                print(f"  ShortName: {info.get('shortName')}")
                print(f"  Beta: {info.get('beta')}")
                print(f"  PE: {info.get('trailingPE') or info.get('forwardPE')}")
                print(f"  DivYield: {info.get('trailingAnnualDividendYield')}")
            except Exception as e:
                print(f"  Error fetching {t}: {e}")
    except Exception as e:
        print(f"Global Error: {e}")

if __name__ == "__main__":
    debug_analytics()
