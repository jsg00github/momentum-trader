"""
Watchlist Module (ORM Version)
Refactored to support Multi-Tenancy and PostgreSQL via SQLAlchemy.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from typing import List, Optional
import models
from database import get_db
import auth
import market_data
from datetime import datetime

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

# Pydantic Model
class WatchlistItem(BaseModel):
    ticker: str
    entry_price: Optional[float] = None
    alert_price: Optional[float] = None 
    stop_alert: Optional[float] = None
    strategy: Optional[str] = None
    notes: Optional[str] = None
    hypothesis: Optional[str] = None

@router.get("")
def get_watchlist(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Get all watchlist items for the current user."""
    items = db.query(models.Watchlist).filter(
        models.Watchlist.user_id == current_user.id
    ).order_by(desc(models.Watchlist.created_at)).all()
    
    if not items:
        return []
        
    tickers = [i.ticker for i in items]
    
    # Get batch prices
    try:
        prices_map = market_data.get_batch_latest_prices(tickers)
    except:
        prices_map = {}
        
    result = []
    for i in items:
        current_price = prices_map.get(i.ticker, 0.0)
        
        # Calculate metrics
        change_pct = ((current_price - i.entry_price) / i.entry_price * 100) if i.entry_price and i.entry_price > 0 else 0
        pl = current_price - (i.entry_price or 0)
        
        # Check assertions
        is_triggered = False
        if i.stop_alert and current_price > 0 and current_price <= i.stop_alert:
            is_triggered = True
            
        result.append({
            'ticker': i.ticker,
            'entry_price': i.entry_price,
            'current_price': round(current_price, 2),
            'change_pct': round(change_pct, 2),
            'pl': round(pl, 2),
            'alert_price': i.alert_price,
            'stop_alert': i.stop_alert,
            'is_triggered': is_triggered,
            'strategy': i.strategy,
            'notes': i.notes,
            'hypothesis': i.hypothesis,
            'added_date': i.created_at # Timestamps should be serialized automatically by FastAPI/Pydantic or manual
        })
    return result

@router.post("")
def add_watchlist_item(item: WatchlistItem, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Add a new item to watchlist."""
    # Check if exists
    existing = db.query(models.Watchlist).filter(
        models.Watchlist.user_id == current_user.id,
        models.Watchlist.ticker == item.ticker.upper()
    ).first()
    
    if existing:
         raise HTTPException(status_code=400, detail=f"Ticker {item.ticker} already in watchlist")
    
    # Get Price if missing
    added_price = item.entry_price
    if not added_price or added_price <= 0:
        # Quick fetch
        import yfinance as yf
        try:
            added_price = yf.Ticker(item.ticker).fast_info.last_price
        except:
            added_price = 0.0
            
    new_item = models.Watchlist(
        user_id=current_user.id,
        ticker=item.ticker.upper(),
        entry_price=added_price,
        alert_price=item.alert_price,
        stop_alert=item.stop_alert,
        strategy=item.strategy,
        notes=item.notes,
        hypothesis=item.hypothesis
    )
    db.add(new_item)
    db.commit()
    
    return {"success": True, "ticker": item.ticker.upper()}

@router.put("/{ticker}")
def update_watchlist_item(ticker: str, item: WatchlistItem, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Update an existing watchlist item."""
    db_item = db.query(models.Watchlist).filter(
        models.Watchlist.user_id == current_user.id,
        models.Watchlist.ticker == ticker.upper()
    ).first()
    
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
        
    db_item.entry_price = item.entry_price
    db_item.alert_price = item.alert_price
    db_item.stop_alert = item.stop_alert
    db_item.strategy = item.strategy
    db_item.notes = item.notes
    db_item.hypothesis = item.hypothesis
    
    db.commit()
    return {"success": True}

@router.delete("/{ticker}")
def remove_watchlist_item(ticker: str, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Remove item from watchlist."""
    db_item = db.query(models.Watchlist).filter(
        models.Watchlist.user_id == current_user.id,
        models.Watchlist.ticker == ticker.upper()
    ).first()
    
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
        
    db.delete(db_item)
    db.commit()
    return {"success": True}
