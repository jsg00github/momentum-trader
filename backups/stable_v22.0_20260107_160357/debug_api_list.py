
# Simulate the logic of "/api/trades/list"
import sqlite3
import pandas as pd

DB_PATH = r"C:\Users\micro\.gemini\antigravity\playground\ancient-glenn\backend\trades.db"

def get_trades_list():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM trades ORDER BY entry_date DESC, id DESC")
    trades = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    print(f"Total trades fetched: {len(trades)}")
    open_count = sum(1 for t in trades if t['status'] == 'OPEN')
    print(f"Open trades: {open_count}")
    
    # Check tickers
    tickers = set(t['ticker'] for t in trades)
    print(f"Unique tickers: {tickers}")

get_trades_list()
