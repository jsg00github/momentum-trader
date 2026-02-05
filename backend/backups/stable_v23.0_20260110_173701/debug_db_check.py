
import sqlite3
import os
import pandas as pd

DB_PATH = r"C:\Users\micro\.gemini\antigravity\playground\ancient-glenn\backend\trades.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("--- Recent Trades ---")
cursor.execute("SELECT id, ticker, status, direction, shares, entry_date, created_at FROM trades ORDER BY id DESC LIMIT 10")
rows = cursor.fetchall()

if not rows:
    print("No recent trades found.")
else:
    print(f"{'ID':<5} {'Ticker':<10} {'Status':<10} {'Dir':<10} {'Shares':<10} {'Date':<15} {'Created':<20}")
    for row in rows:
        print(f"{row[0]:<5} {row[1]:<10} {row[2]:<10} {row[3]:<10} {row[4]:<10} {row[5]:<15} {row[6]:<20}")

conn.close()
