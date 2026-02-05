from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import yfinance as yf
from datetime import datetime

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

# Database path
DB_PATH = "momentum_trader.db"

class WatchlistItem(BaseModel):
    ticker: str
    entry_price: Optional[float] = None # Added Price
    alert_price: Optional[float] = None # Buy Alert Price
    stop_alert: Optional[float] = None  # SL Alert Price
    strategy: Optional[str] = None
    notes: Optional[str] = None
    hypothesis: Optional[str] = None

def init_db():
    """Initialize database with watchlist table and perform migrations"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Ensure table exists (in case it's a fresh DB)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL UNIQUE,
            entry_price REAL NOT NULL,
            alert_price REAL,
            stop_alert REAL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            strategy TEXT,
            hypothesis TEXT
        )
    """)
    
    # Ensure all columns exist (basic migration)
    try:
        cursor.execute("SELECT strategy FROM watchlist LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE watchlist ADD COLUMN strategy TEXT")
        conn.commit()

    try:
        cursor.execute("SELECT hypothesis FROM watchlist LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE watchlist ADD COLUMN hypothesis TEXT")
        conn.commit()

    # Data Migration from trades.db if exists
    TRADES_DB = "trades.db"
    if os.path.exists(TRADES_DB):
        try:
            t_conn = sqlite3.connect(TRADES_DB)
            t_cursor = t_conn.cursor()
            t_cursor.execute("SELECT ticker, note, hypothesis, added_at FROM watchlist")
            legacy_items = t_cursor.fetchall()
            
            for ticker, note, hypothesis, added_at in legacy_items:
                try:
                    # Check if already exists in new DB
                    cursor.execute("SELECT ticker FROM watchlist WHERE ticker = ?", (ticker.upper(),))
                    if not cursor.fetchone():
                        # Use a default price of 0.0 for legacy items to avoid blocking sequential fetches
                        cursor.execute("""
                            INSERT INTO watchlist (ticker, notes, hypothesis, entry_price, created_at)
                            VALUES (?, ?, ?, ?, ?)
                        """, (ticker.upper(), note, hypothesis, 0.0, added_at))
                except Exception as e:
                    print(f"Migration error for {ticker}: {e}")
            conn.commit()
            t_conn.close()
        except Exception as e:
            print(f"Watchlist migration from trades.db failed: {e}")
    
    conn.close()

import os
import market_data

def get_live_price(ticker: str) -> float:
    """Get current price for a ticker"""
    try:
        stock = yf.Ticker(ticker)
        # Using 1d period, 1m interval might be too slow, history(period='1d') is usually fine
        data = stock.history(period="1d")
        if not data.empty:
            return float(data['Close'].iloc[-1])
        return 0.0
    except:
        return 0.0

@router.get("")
def get_watchlist():
    """Get all watchlist items with current prices and P/L"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT ticker, entry_price, alert_price, stop_alert, strategy, notes, hypothesis, created_at
        FROM watchlist
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return []

    # Get batch prices
    tickers = [row[0] for row in rows]
    prices_map = market_data.get_batch_latest_prices(tickers)
    
    items = []
    for row in rows:
        ticker = row[0]
        entry_price = row[1]
        
        # Get current price from map
        current_price = prices_map.get(ticker, 0.0)
        
        # Calculate metrics
        change_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        pl = current_price - entry_price
        
        # Check if stop alert is triggered (price below SL)
        stop_alert = row[3]
        is_triggered = False
        if stop_alert and current_price > 0 and current_price <= stop_alert:
            is_triggered = True

        items.append({
            'ticker': ticker,
            'entry_price': entry_price, # This is the Price when added
            'current_price': current_price,
            'change_pct': round(change_pct, 2),
            'pl': round(pl, 2),
            'alert_price': row[2], # Buy Alert
            'stop_alert': stop_alert,  # SL Alert (Watchlist SL)
            'is_triggered': is_triggered,
            'strategy': row[4],
            'notes': row[5],
            'hypothesis': row[6],
            'added_date': row[7]
        })
    
    return items

@router.post("")
def add_watchlist_item(item: WatchlistItem):
    """Add a new item to watchlist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # If entry_price is not provided, fetch current price
        added_price = item.entry_price
        if not added_price or added_price <= 0:
            added_price = get_live_price(item.ticker)

        cursor.execute("""
            INSERT INTO watchlist (ticker, entry_price, alert_price, stop_alert, strategy, notes, hypothesis)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (item.ticker.upper(), added_price, item.alert_price, item.stop_alert, item.strategy, item.notes, item.hypothesis))
        
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Ticker {item.ticker} already in watchlist")
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    
    return {"success": True, "ticker": item.ticker.upper()}

@router.put("/{ticker}")
def update_watchlist_item(ticker: str, item: WatchlistItem):
    """Update an existing watchlist item"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE watchlist 
            SET entry_price = ?, alert_price = ?, stop_alert = ?, strategy = ?, notes = ?, hypothesis = ?
            WHERE ticker = ?
        """, (item.entry_price, item.alert_price, item.stop_alert, item.strategy, item.notes, item.hypothesis, ticker.upper()))
        
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found in watchlist")
        
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    
    return {"success": True}

@router.delete("/{ticker}")
def remove_watchlist_item(ticker: str):
    """Remove item from watchlist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.upper(),))
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found in watchlist")
    
    conn.commit()
    conn.close()
    
    return {"success": True}

# Initialize database on module load
init_db()
