
import sqlite3
import os

DB_PATH = "trades.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found. Skipping migration (maybe using Postgres?).")
        return

    print(f"Migrating {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(argentina_positions)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "manual_price" not in columns:
            print("Adding 'manual_price' column...")
            cursor.execute("ALTER TABLE argentina_positions ADD COLUMN manual_price REAL")
            print("Done.")
        else:
            print("'manual_price' column already exists.")

        if "manual_price_updated_at" not in columns:
             print("Adding 'manual_price_updated_at' column...")
             # SQLite doesn't strictly enforce DATETIME types like Postgres, typically TEXT or REAL/NUMERIC
             # SQLAlchemy uses DateTime, which often maps to TIMESTAMP or TEXT. 
             # We'll use DATETIME or TEXT for compatibility.
             cursor.execute("ALTER TABLE argentina_positions ADD COLUMN manual_price_updated_at DATETIME")
             print("Done.")
        else:
            print("'manual_price_updated_at' column already exists.")
            
        conn.commit()
        print("Migration successful.")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
