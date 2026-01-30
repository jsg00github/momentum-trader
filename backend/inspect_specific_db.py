
import sqlite3
import pandas as pd
import sys
import os

if len(sys.argv) < 2:
    print("Usage: python inspect_specific_db.py <db_filename>")
    sys.exit(1)

db_path = sys.argv[1]
if not os.path.exists(db_path):
    print(f"File not found: {db_path}")
    sys.exit(1)

print(f"Inspecting: {db_path}")
conn = sqlite3.connect(db_path)

try:
    # List tables
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:", [t[0] for t in tables])
    
    # Check users
    if ('users',) in tables:
        print("\n--- USERS ---")
        print(pd.read_sql("SELECT * FROM users", conn))
    
    # Check trades
    if ('trades',) in tables:
        print("\n--- TRADES ---")
        print(pd.read_sql("SELECT count(*) as count, status FROM trades GROUP BY status", conn))
        
    # Check argentina
    if ('argentina_positions',) in tables:
        print("\n--- ARG POS ---")
        print(pd.read_sql("SELECT count(*) as count FROM argentina_positions", conn))

except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
