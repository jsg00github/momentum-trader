"""
Crypto Journal Module (ORM Version)
Refactored to support Multi-Tenancy and PostgreSQL via SQLAlchemy.
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
import models
from database import get_db
import auth

router = APIRouter()

# Pydantic models
class CryptoPositionCreate(BaseModel):
    ticker: str
    amount: float
    entry_price: float
    source: str = "MANUAL"

class BinanceConfigCreate(BaseModel):
    api_key: str
    api_secret: str

# --- Binance Sync Logic ---
def sync_binance_internal(user: models.User, api_key: str, api_secret: str, db: Session):
    try:
        import ccxt
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True
        })
        
        # Fetch balances
        print(f"[Crypto] Fetching Binance balance for user {user.email}...")
        balance = exchange.fetch_balance()
        
        # Filter non-zero
        assets = {k: v for k, v in balance['total'].items() if v > 0}
        if not assets:
            print("[Crypto] No assets found in Binance.")
            return 0

        # Get Prices for all assets
        print("[Crypto] Fetching all tickers to map prices...")
        try:
            all_tickers = exchange.fetch_tickers()
            prices = {}
            for symbol, data in all_tickers.items():
                if symbol.endswith('/USDT'):
                    base = symbol.split('/')[0]
                    prices[base] = data['last']
        except Exception as e:
            print(f"[Crypto] Error fetching tickers: {e}")
            prices = {}
        
        # Stablecoins
        for stable in ['USDT', 'USDC', 'DAI', 'FDUSD']:
            prices[stable] = 1.0

        # Filter dust & Prepare positions
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
            
        # DB Update: Delete ONLY this user's Binance positions
        db.query(models.CryptoPosition).filter(
            models.CryptoPosition.user_id == user.id,
            models.CryptoPosition.source == 'BINANCE'
        ).delete()
        
        count = 0
        for pos in valid_positions:
            new_pos = models.CryptoPosition(
                user_id=user.id,
                ticker=pos['ticker'],
                amount=pos['amount'],
                entry_price=pos['price'], # Using current price as entry for synced positions (limitation of sync)
                current_price=pos['price'],
                source='BINANCE'
            )
            db.add(new_pos)
            count += 1
        
        db.commit()
        print(f"[Crypto] Synced {count} positions from Binance for {user.email}.")
        return count
        
    except Exception as e:
        print(f"[Crypto] Sync Error: {e}")
        raise e

# --- Endpoints ---

@router.get("/api/crypto/positions")
def get_positions(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    # 1. Get positions from DB
    positions = db.query(models.CryptoPosition).filter(models.CryptoPosition.user_id == current_user.id).all()
    
    # 2. Map to list and collect tickers
    pos_list = []
    tickers_to_fetch = set()
    for p in positions:
        pos_list.append(p)
        tickers_to_fetch.add(p.ticker)
    
    # 3. Live Prices (Optional, but good for Manual trades updates)
    live_prices = {}
    try:
        import ccxt
        exchange = ccxt.binance()
        all_tickers = exchange.fetch_tickers()
        for symbol, data in all_tickers.items():
             if symbol.endswith('/USDT'):
                base = symbol.split('/')[0]
                if base in tickers_to_fetch:
                    live_prices[base] = data['last']
    except:
        pass
    
    for stable in ['USDT', 'USDC']: live_prices[stable] = 1.0
    
    # 4. Enrich
    enriched_positions = []
    total_invested = 0
    total_value = 0
    
    for p in pos_list:
        price = live_prices.get(p.ticker, p.current_price or p.entry_price)
        value = p.amount * price
        invested = p.amount * p.entry_price
        pnl = value - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0
        
        enriched_positions.append({
            "id": p.id,
            "ticker": p.ticker,
            "amount": p.amount,
            "entry_price": p.entry_price,
            "source": p.source,
            "current_price": round(price, 5),
            "value": round(value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2)
        })
        total_invested += invested
        total_value += value
        
    return {
        "positions": enriched_positions,
        "metrics": {
            "total_invested": round(total_invested, 2),
            "total_value": round(total_value, 2),
            "total_pnl": round(total_value - total_invested, 2)
        }
    }

@router.post("/api/crypto/positions")
def add_position(pos: CryptoPositionCreate, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    new_pos = models.CryptoPosition(
        user_id=current_user.id,
        ticker=pos.ticker.upper(),
        amount=pos.amount,
        entry_price=pos.entry_price,
        current_price=pos.entry_price,
        source=pos.source
    )
    db.add(new_pos)
    db.commit()
    return {"status": "success", "message": "Position added"}

@router.delete("/api/crypto/positions/{position_id}")
def delete_position(position_id: int, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    pos = db.query(models.CryptoPosition).filter(
        models.CryptoPosition.id == position_id,
        models.CryptoPosition.user_id == current_user.id
    ).first()
    
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
        
    db.delete(pos)
    db.commit()
    return {"status": "success"}

@router.post("/api/crypto/binance/connect")
def connect_binance(config: BinanceConfigCreate, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    # Save/Update Keys
    existing = db.query(models.BinanceConfig).filter(models.BinanceConfig.user_id == current_user.id).first()
    if existing:
        existing.api_key = config.api_key
        existing.api_secret = config.api_secret
    else:
        new_config = models.BinanceConfig(
            user_id=current_user.id,
            api_key=config.api_key,
            api_secret=config.api_secret
        )
        db.add(new_config)
    
    db.commit()
    
    # Trigger Sync
    try:
        count = sync_binance_internal(current_user, config.api_key, config.api_secret, db)
        return {"status": "success", "message": f"Connected! Synced {count} positions."}
    except Exception as e:
        return {"status": "warning", "message": f"Keys saved, but sync failed: {str(e)}"}

@router.post("/api/crypto/binance/sync")
def trigger_sync(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    config = db.query(models.BinanceConfig).filter(models.BinanceConfig.user_id == current_user.id).first()
    if not config or not config.api_key:
        raise HTTPException(status_code=400, detail="Binance keys not configured")
        
    try:
        count = sync_binance_internal(current_user, config.api_key, config.api_secret, db)
        return {"status": "success", "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Helper for other modules (e.g. portfolio snapshots)
def get_portfolio_metrics(user_id: int, db: Session):
    # This logic mimics get_positions but server-side only for metrics
    positions = db.query(models.CryptoPosition).filter(models.CryptoPosition.user_id == user_id).all()
    # Simplified valuation (ignoring live price update for speed if needed, or fetch if critical)
    # For snapshot consistency, ideally we fetch live. 
    # But for now, we sum what's in DB (assuming sync ran recently or manual entry)
    
    invested = 0
    value = 0
    for p in positions:
        invested += p.amount * p.entry_price
        # Default to entry price if current not updated, or updated by previous sync
        # In a real production system, we'd have a background price updater independent of user requests.
        price = p.current_price or p.entry_price 
        value += p.amount * price
        
    return {
        "total_invested": invested,
        "total_value": value,
        "total_pnl": value - invested
    }

@router.get("/api/crypto/ai/portfolio-insight")
def api_ai_crypto_insight(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    import market_brain
    try:
        # Reuse get_positions logic to get enriched data
        # We can extract the logic to a helper function
        # But for now, calling the endpoint handler logic is messy.
        # Let's verify get_positions returns a dict (it does).
        data = get_positions(current_user, db)
        positions = data.get("positions", [])
        metrics = data.get("metrics", {})
        
        if not positions:
            return {"insight": "No hay posiciones crypto para analizar."}
            
        # ... (Same formatting logic as before) ...
        positions_list = []
        for p in positions:
            positions_list.append(f"{p['ticker']} ({p['amount']})")
            
        portfolio_data = {
            "positions": ", ".join(positions_list[:10]),
            "total_value": f"${metrics.get('total_value', 0):,.2f}",
            "unrealized_pnl": f"${metrics.get('total_pnl', 0):,.2f}",
            "sectors": "Cryptocurrency Market"
        }
        
        insight = market_brain.get_portfolio_insight(portfolio_data)
        return {"insight": insight}
        
    except Exception as e:
        return {"insight": f"Error: {e}"}


@router.post("/api/crypto/upload_csv")
async def upload_csv(file: UploadFile = File(...), current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """
    Import Crypto trades from CSV.
    Format: ticker, amount, entry_price, source
    """
    import csv
    import codecs
    import portfolio_snapshots
    
    try:
        csv_reader = csv.DictReader(codecs.iterdecode(file.file, 'utf-8'))
        count = 0
        
        for row in csv_reader:
            try:
                ticker = row.get("ticker", "").strip().upper()
                if not ticker: continue
                
                amount = float(row.get("amount", 0))
                entry_price = float(row.get("entry_price", 0))
                source = row.get("source", "MANUAL").upper()
                
                # Check for existing? Usually crypto positions are summed, but we'll add row for now or replace?
                # The model is "Position" but behaves like a row.
                # If we want a separate entry for each trade, the table structure supports it for Manual.
                
                pos = models.CryptoPosition(
                    user_id=current_user.id,
                    ticker=ticker,
                    amount=amount,
                    entry_price=entry_price,
                    current_price=entry_price, # Init with entry
                    source=source
                )
                db.add(pos)
                count += 1
            except Exception as r_err:
                print(f"Row error: {r_err}")
                continue
                
        db.commit()
        
        # Trigger Rebuild
        try:
             portfolio_snapshots.rebuild_history(current_user.id, db)
        except: pass
        
        return {"status": "success", "imported": count}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/crypto/template")
def download_template():
    """Download CSV template for Crypto Trades"""
    from fastapi.responses import StreamingResponse
    import io
    import csv
    
    headers = ["ticker", "amount", "entry_price", "source"]
    
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerow(["BTC", "0.5", "45000", "MANUAL"])
    
    stream.seek(0)
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=crypto_trades_template.csv"
    return response
