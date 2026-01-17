
import sqlite3
import os

DB_PATH = "trades.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return

    print(f"Migrating {DB_PATH} for Crypto Parity...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check existing columns
        cursor.execute("PRAGMA table_info(crypto_positions)")
        existing_cols = [info[1] for info in cursor.fetchall()]
        
        # New columns to add
        new_columns = {
            "entry_date": "TEXT",
            "exit_date": "TEXT",
            "exit_price": "REAL",
            "status": "TEXT DEFAULT 'OPEN'",
            "strategy": "TEXT",
            "stop_loss": "REAL",
            "target": "REAL",
            "notes": "TEXT",
            "initial_risk": "REAL"
        }
        
        for col, dtype in new_columns.items():
            if col not in existing_cols:
                print(f"Adding '{col}' column...")
                cursor.execute(f"ALTER TABLE crypto_positions ADD COLUMN {col} {dtype}")
            else:
                print(f"'{col}' already exists.")
            
        conn.commit()
        print("Migration successful.")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
