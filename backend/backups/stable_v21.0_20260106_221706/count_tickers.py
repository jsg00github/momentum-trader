import sqlite3

conn = sqlite3.connect('trades.db')
cursor = conn.cursor()
cursor.execute("SELECT COUNT(DISTINCT ticker) FROM trades WHERE status = 'OPEN'")
print(f"Open tickers: {cursor.fetchone()[0]}")
