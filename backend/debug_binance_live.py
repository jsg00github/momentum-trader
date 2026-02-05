import sys
import os
import ccxt
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models

def debug_connection():
    db = SessionLocal()
    try:
        print("--- Debugging Binance Connection ---")
        config = db.query(models.BinanceConfig).first()
        if not config:
            print("ERROR: No Binance Configuration found in 'trades.db' (table: binance_config).")
            print("Please configure keys in the UI first.")
            return

        print(f"Found Config for User ID: {config.user_id}")
        masked_key = config.api_key[:4] + "..." + config.api_key[-4:] if config.api_key else "None"
        print(f"API Key: {masked_key}")
        
        if not config.api_key or not config.api_secret:
            print("ERROR: API Key or Secret is missing.")
            return

        print("Attempting CCXT connection...")
        exchange = ccxt.binance({
            'apiKey': config.api_key,
            'secret': config.api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'} 
        })
        
        # Test 1: Public Endpoint (Time)
        try:
            time = exchange.fetch_time()
            print(f"Public API Check: OK (Server Time: {time})")
        except Exception as e:
            print(f"Public API Check FAILED: {e}")
            print("Check internet connection or DNS.")
            return

        # Test 2: Private Endpoint (Balance)
        try:
            print("Fetching Balance...")
            balance = exchange.fetch_balance()
            total_usdt = balance['total'].get('USDT', 0)
            print(f"Private API Check: OK. USDT Balance: {total_usdt}")
            
            # Print non-zero assets
            print("Assets > 0:")
            for coin, amount in balance['total'].items():
                if amount > 0:
                    print(f" - {coin}: {amount}")
                    
        except ccxt.AuthenticationError:
            print("ERROR: Authentication Failed. Invalid API Key or Secret.")
            print("Details: API rejected the credentials.")
        except ccxt.PermissionDenied:
            print("ERROR: Permission Denied. Check API Key permissions (IP restriction?).")
        except Exception as e:
            print(f"ERROR: Private API Check Failed: {e}")

    finally:
        db.close()

if __name__ == "__main__":
    debug_connection()
