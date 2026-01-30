"""
Railway PostgreSQL Migration Script
Run on production to add missing columns.
"""
import os
import psycopg2
from psycopg2 import sql

DATABASE_URL = os.environ.get("DATABASE_URL")

def migrate():
    if not DATABASE_URL:
        print("DATABASE_URL not set")
        return
    
    print("Connecting to Railway PostgreSQL...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cursor = conn.cursor()
    
    try:
        # ---- crypto_positions: Add missing columns ----
        print("\n=== Migrating crypto_positions ===")
        
        # Get existing columns
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'crypto_positions'
        """)
        existing_cols = [row[0] for row in cursor.fetchall()]
        print(f"Existing columns: {existing_cols}")
        
        new_columns = {
            "entry_date": "VARCHAR",
            "exit_date": "VARCHAR",
            "exit_price": "DOUBLE PRECISION",
            "status": "VARCHAR DEFAULT 'OPEN'",
            "strategy": "VARCHAR",
            "stop_loss": "DOUBLE PRECISION",
            "target": "DOUBLE PRECISION",
            "notes": "VARCHAR",
            "initial_risk": "DOUBLE PRECISION"
        }
        
        for col, dtype in new_columns.items():
            if col not in existing_cols:
                print(f"  Adding '{col}' column...")
                cursor.execute(f'ALTER TABLE crypto_positions ADD COLUMN "{col}" {dtype}')
            else:
                print(f"  '{col}' already exists.")
        
        conn.commit()
        print("\n=== Migration complete ===")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    migrate()
