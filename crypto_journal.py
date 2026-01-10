import sqlite3
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import json

router = APIRouter()

# Database setup
DB_PATH = Path(__file__).parent / "crypto_journal.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crypto_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            amount REAL NOT NULL,
            entry_price REAL NOT NULL,
            current_price REAL,
            source TEXT DEFAULT 'MANUAL', -- 'MANUAL' or 'BINANCE'
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS binance_config (
            id INTEGER PRIMARY KEY DEFAULT 1,
            api_key TEXT,
            api_secret TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("[Crypto Journal] Database initialized.")

init_db()

# Pydantic models
class CryptoPosition(BaseModel):
    ticker: str
    amount: float
    entry_price: float
    source: str = "MANUAL"

class BinanceConfig(BaseModel):
    api_key: str
    api_secret: str

# --- Binance Sync Logic ---
def sync_binance_internal(api_key, api_secret):
    try:
        import ccxt
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True
        })
        
        # Fetch balances
        print("[Crypto] Fetching Binance balance...")
        balance = exchange.fetch_balance()
        # balance['total'] contains { 'BTC': 0.1, ... }
        
        # Filter non-zero
        assets = {k: v for k, v in balance['total'].items() if v > 0}
        if not assets:
            print("[Crypto] No assets found in Binance.")
            return 0

        # Get Prices for all assets
        print("[Crypto] Fetching all tickers to map prices...")
        try:
            # Fetching all is safer than list if some symbols are invalid
            all_tickers = exchange.fetch_tickers()
            
            prices = {}
            for symbol, data in all_tickers.items():
                # We only care about USDT pairs for now
                if symbol.endswith('/USDT'):
                    base = symbol.split('/')[0]
                    prices[base] = data['last']
                    
            print(f"[Crypto] Loaded prices for {len(prices)} assets.")
        except Exception as e:
            print(f"[Crypto] Error fetching tickers: {e}")
            prices = {}
        
        # Set stablecoin prices
        prices['USDT'] = 1.0
        prices['USDC'] = 1.0
        prices['DAI'] = 1.0
        prices['FDUSD'] = 1.0

        # Filter dust (value < 1 USD)
        valid_positions = []
        for coin, amount in assets.items():
            price = prices.get(coin, 0)
            value = amount * price
            if value > 1.0: # Filter dust > $1
                valid_positions.append({
                    'ticker': coin,
                    'amount': amount,
                    'price': price
                })
        
        if not valid_positions:
            print("[Crypto] No positions > $1 found.")
            return 0
            
        # DB Update
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM crypto_positions WHERE source = 'BINANCE'")
        
        count = 0
        for pos in valid_positions:
            cursor.execute('''
                INSERT INTO crypto_positions (ticker, amount, entry_price, current_price, source, created_at)
                VALUES (?, ?, ?, ?, 'BINANCE', ?)
            ''', (pos['ticker'], pos['amount'], pos['price'], pos['price'], datetime.now().isoformat()))
            count += 1
        
        conn.commit()
        conn.close()
        print(f"[Crypto] Synced {count} positions from Binance.")
        return count
        
    except Exception as e:
        print(f"[Crypto] Sync Error: {e}")
        raise e

# --- Endpoints ---

@router.get("/api/crypto/positions")
def get_positions():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM crypto_positions")
    rows = cursor.fetchall()
    
    positions = []
    tickers_to_fetch = set()
    for row in rows:
        pos = dict(row)
        tickers_to_fetch.add(pos["ticker"])
        positions.append(pos)
    
    # Check if we need to fetch live prices (mostly for manual trades)
    # For Binance trades, current_price is updated on sync, but let's try to be fresh
    live_prices = {}
    
    # Try using CCXT for fresh prices if available, else simple fallback
    try:
        import ccxt
        # No auth needed for public ticker
        exchange = ccxt.binance() 
        
        # Fetch all tickers to avoid errors with invalid pairs
        all_tickers = exchange.fetch_tickers()
        for symbol, data in all_tickers.items():
            if symbol.endswith('/USDT'):
                base = symbol.split('/')[0]
                if base in tickers_to_fetch:
                    live_prices[base] = data['last']
                    
    except Exception as e:
        print(f"Error fetching live prices: {e}")
        # Could fallback to requests if ccxt fails
    
    # Add stablecoins
    live_prices['USDT'] = 1.0
    live_prices['USDC'] = 1.0

    # Calculate metrics
    enriched_positions = []
    total_invested = 0
    total_value = 0
    
    for pos in positions:
        current_price = live_prices.get(pos["ticker"], pos["current_price"] or pos["entry_price"])
        value = pos["amount"] * current_price
        invested = pos["amount"] * pos["entry_price"]
        pnl = value - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0
        
        enriched_positions.append({
            **pos,
            "current_price": current_price,
            "value": round(value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2)
        })
        
        total_invested += invested
        total_value += value
        
    conn.close()
    
    return {
        "positions": enriched_positions,
        "metrics": {
            "total_invested": round(total_invested, 2),
            "total_value": round(total_value, 2),
            "total_pnl": round(total_value - total_invested, 2)
        }
    }

@router.post("/api/crypto/positions")
def add_position(position: CryptoPosition):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO crypto_positions (ticker, amount, entry_price, current_price, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (position.ticker.upper(), position.amount, position.entry_price, position.entry_price, position.source, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Position added"}

@router.delete("/api/crypto/positions/{position_id}")
def delete_position(position_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM crypto_positions WHERE id = ?", (position_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@router.post("/api/crypto/binance/connect")
def connect_binance(config: BinanceConfig):
    # Save keys
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO binance_config (id, api_key, api_secret) VALUES (1, ?, ?)", 
                   (config.api_key, config.api_secret))
    conn.commit()
    conn.close()
    
    # Trigger Sync
    try:
        count = sync_binance_internal(config.api_key, config.api_secret)
        return {"status": "success", "message": f"Connected! Synced {count} positions."}
    except Exception as e:
        print(f"Sync failed: {e}")
        # Don't fail the request if sync fails, but warn
        return {"status": "warning", "message": f"Keys saved, but sync failed: {str(e)}"}

@router.post("/api/crypto/binance/sync")
def trigger_sync():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT api_key, api_secret FROM binance_config WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    
    if not row or not row[0]:
        raise HTTPException(status_code=400, detail="Binance keys not configured")
    
    try:
        count = sync_binance_internal(row[0], row[1])
        return {"status": "success", "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Internal function for portfolio snapshots
def get_portfolio_metrics():
    data = get_positions()
    metrics = data["metrics"]
    return {
        "total_invested": metrics["total_invested"],
        "total_value": metrics["total_value"],
        "total_pnl": metrics["total_pnl"]
    }


@router.get("/api/crypto/ai/portfolio-insight")
def api_ai_crypto_insight():
    """Generate AI portfolio analysis for Crypto positions using Gemini."""
    import market_brain
    
    try:
        # Get positions with enriched data
        data = get_positions()
        positions = data.get("positions", [])
        metrics = data.get("metrics", {})
        
        if not positions:
            return {"insight": "No hay posiciones crypto para analizar."}
        
        # Build portfolio summary
        positions_list = []
        winners = []
        losers = []
        
        for p in positions:
            ticker = p['ticker']
            amount = p['amount']
            entry = p['entry_price']
            current = p.get('current_price', entry)
            pnl_pct = p.get('pnl_pct', 0)
            
            positions_list.append(f"{ticker} ({amount} @ ${entry})")
            
            if pnl_pct > 0:
                winners.append(f"{ticker}: +{pnl_pct:.1f}%")
            elif pnl_pct < 0:
                losers.append(f"{ticker}: {pnl_pct:.1f}%")
        
        # Sort by magnitude
        winners = sorted(winners, key=lambda x: float(x.split('+')[1].replace('%', '')), reverse=True)[:3]
        losers = sorted(losers, key=lambda x: float(x.split(':')[1].replace('%', '')))[:3]
        
        portfolio_data = {
            "positions": ", ".join(positions_list[:10]) if positions_list else "Sin posiciones",
            "total_value": f"${metrics.get('total_value', 0):,.2f}",
            "unrealized_pnl": f"${metrics.get('total_pnl', 0):,.2f}",
            "sectors": "Cryptocurrency Market",
            "winners": ", ".join(winners) if winners else "Ninguno",
            "losers": ", ".join(losers) if losers else "Ninguno"
        }
        
        insight = market_brain.get_portfolio_insight(portfolio_data)
        return {"insight": insight}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"insight": f"Error analyzing crypto portfolio: {e}"}
