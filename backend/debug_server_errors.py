
import os
# FORCE CORRECT DB BEFORE IMPORTS
os.environ["DATABASE_URL"] = "sqlite:///crypto_journal.db"

import sys
from sqlalchemy.orm import Session
# Force reload database module to pick up new env var
if 'database' in sys.modules:
    del sys.modules['database']
    
from database import SessionLocal
import models
import trade_journal 
import crypto_journal

def debug_errors():
    db = SessionLocal()
    try:
        print(f"--- DEBUGGING with DB: crypto_journal.db ---")
        
        # Mock User (We need to find the REAL user ID from BinanceConfig)
        real_user_id = 1
        config = db.query(models.BinanceConfig).first()
        if config:
            real_user_id = config.user_id
            print(f"   Found Real User ID: {real_user_id}")
        
        class DummyUser:
            id = real_user_id
            email = "debug@example.com"
        
        user = DummyUser()
        
        # 1. Test /api/trades/open-prices (Stock) - Is this causing 500?
        print("\n1. Testing 'get_open_prices' (Stock)...")
        try:
            trades = db.query(models.Trade).filter(models.Trade.status == 'OPEN').all()
            print(f"   Found {len(trades)} open stock trades.")
            if trades:
                for t in trades:
                     print(f"   - {t.ticker}")
                
                # Execute function
                res = trade_journal.get_open_prices(user, db)
                print(f"   SUCCESS! Result count: {len(res) if res else 0}")
                
        except Exception as e:
            print(f"   CRITICAL ERROR in get_open_prices: {e}")
            import traceback
            traceback.print_exc()

        # 2. Test Binance Sync (Crypto)
        print("\n2. Testing Binance Sync...")
        try:
            if config:
                print(f"   Using Key: {config.api_key[:4]}...")
                if hasattr(crypto_journal, 'sync_binance_internal'):
                     print("   Calling sync_binance_internal...")
                     count = crypto_journal.sync_binance_internal(user, config.api_key, config.api_secret, db)
                     print(f"   Sync Result: Processed {count} positions.")
                else:
                     print("   sync_binance_internal function not found.")
            else:
                 print("   No Binance keys found in crypto_journal.db (Unexpected).")

        except Exception as e:
            print(f"   CRITICAL ERROR in Binance Sync: {e}")
            import traceback
            traceback.print_exc()

    finally:
        db.close()

if __name__ == "__main__":
    debug_errors()
