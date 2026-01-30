import os
import sqlite3

def check_db(path):
    try:
        if os.path.getsize(path) == 0: return None
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        
        # Check for tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        
        counts = {}
        if 'portfolio_snapshots' in tables:
            cursor.execute("SELECT count(*) FROM portfolio_snapshots")
            counts['snapshots'] = cursor.fetchone()[0]
            
        if 'trades' in tables:
             cursor.execute("SELECT count(*) FROM trades")
             counts['trades'] = cursor.fetchone()[0]
             
        conn.close()
        
        if counts and (counts.get('snapshots', 0) > 0 or counts.get('trades', 0) > 0):
            return counts
        return None
    except:
        return None

print("Scanning for active databases...")
root_dir = os.path.abspath("../")
for root, dirs, files in os.walk(root_dir):
    for file in files:
        if file.endswith(".db"):
            full_path = os.path.join(root, file)
            res = check_db(full_path)
            if res:
                print(f"FOUND DATA in: {full_path}")
                print(f"  Counts: {res}")
                
print("Scan complete.")
