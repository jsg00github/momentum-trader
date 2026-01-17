
import os
import sys
# Default to trades.db
os.environ["DATABASE_URL"] = "sqlite:///trades.db"

from database import SessionLocal
import models
import market_data
import time

def check_tickers():
    db = SessionLocal()
    print("--- Checking Open Trades in trades.db ---")
    
    trades = db.query(models.Trade).filter(models.Trade.status == 'OPEN').all()
    tickers = list(set([t.ticker.upper() for t in trades if t.ticker]))
    print(f"Found {len(tickers)} unique tickers.")
    
    for ticker in tickers:
        print(f"Checking {ticker}...", end="", flush=True)
        try:
            # Test market data fetch (single)
            # safe_yf_download usually takes a list
            data = market_data.safe_yf_download([ticker], period="5d", threads=False)
            
            if data.empty:
                print(" [EMPTY/FAIL]")
            else:
                print(" [OK]")
                
        except Exception as e:
            print(f" [CRASH] {e}")

    db.close()

if __name__ == "__main__":
    check_tickers()
