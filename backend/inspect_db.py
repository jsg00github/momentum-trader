
import sqlite3
import pandas as pd
import os

db_path = "trades.db"
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    # try backend dir
    db_path = "backend/trades.db"

conn = sqlite3.connect(db_path)
try:
    print("--- USERS ---")
    users = pd.read_sql("SELECT * FROM users", conn)
    print(users)

    print("\n--- TRADES (ALL) ---")
    trades = pd.read_sql("SELECT id, ticker, status, entry_price, shares FROM trades", conn)
    print(trades)
    print("\nStatus Counts:")
    print(trades['status'].value_counts())

    print("\n--- ARGENTINA POSITIONS ---")
    arg_pos = pd.read_sql("SELECT id, ticker, asset_type, status, entry_price, shares FROM argentina_positions", conn)
    print(arg_pos)
    
    print("\n--- CRYPTO POSITIONS ---")
    crypto = pd.read_sql("SELECT id, ticker, status, amount FROM crypto_positions", conn)
    print(crypto)

except Exception as e:
    print(e)
finally:
    conn.close()
