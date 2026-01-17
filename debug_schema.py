
import glob
import sqlite3

def check_schemas():
    db_files = glob.glob("*.db")
    print(f"Checking schemas in: {db_files}")
    
    for db_file in db_files:
        print(f"\n--- {db_file} ---")
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # 1. Binance Config Schema
            try:
                cursor.execute("PRAGMA table_info(binance_config)")
                columns = cursor.fetchall()
                if columns:
                    print(f"   [Table: binance_config]")
                    for col in columns:
                        print(f"     - {col[1]} ({col[2]})")
                    
                    # Count rows
                    cursor.execute("SELECT count(*) FROM binance_config")
                    print(f"     Row Count: {cursor.fetchone()[0]}")
                else:
                    print("   [Table: binance_config] NOT FOUND")
            except Exception as e:
                print(f"   Error reading binance_config: {e}")

            # 2. Trades Schema (Stock) - relevant for open-prices 500
            try:
                cursor.execute("PRAGMA table_info(trades)")
                columns = cursor.fetchall()
                if columns:
                    print(f"   [Table: trades] Found ({len(columns)} cols)")
                    # Count open trades
                    cursor.execute("SELECT count(*) FROM trades WHERE status='OPEN'")
                    print(f"     Open Trades: {cursor.fetchone()[0]}")
                else:
                    print("   [Table: trades] NOT FOUND")
            except Exception as e:
                print(f"   Error reading trades: {e}")

            conn.close()
        except Exception as e:
            print(f"   Failed to connect: {e}")

if __name__ == "__main__":
    check_schemas()
