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
    entry_date: Optional[str] = None
    strategy: Optional[str] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    notes: Optional[str] = None
    source: str = "MANUAL"

class CryptoClose(BaseModel):
    exit_price: float
    exit_date: Optional[str] = None
    notes: Optional[str] = None





# --- Endpoints ---

@router.get("/api/crypto/positions")
def get_positions(status: str = "OPEN", current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    # 1. Get positions from DB
    positions = db.query(models.CryptoPosition).filter(
        models.CryptoPosition.user_id == current_user.id,
        models.CryptoPosition.status == status
    ).all()
    
    # 2. Map to list and collect tickers
    pos_list = []
    tickers_to_fetch = set()
    for p in positions:
        pos_list.append(p)
        tickers_to_fetch.add(p.ticker)
    
    # 3. Live Prices from price_service cache (fast)
    import price_service
    live_prices = {}
    
    for ticker in tickers_to_fetch:
        price_data = price_service.get_crypto_price(ticker.upper())
        if price_data and price_data.get('price'):
            live_prices[ticker] = price_data['price']
    
    # Stablecoins always = 1.0
    for stable in ['USDT', 'USDC', 'DAI', 'FDUSD']: 
        live_prices[stable] = 1.0
    
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
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "entry_date": p.entry_date,
            "strategy": p.strategy,
            "stop_loss": p.stop_loss,
            "target": p.target,
            "notes": p.notes,
            "status": p.status
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
        source=pos.source,
        entry_date=pos.entry_date or datetime.now().strftime("%Y-%m-%d"),
        strategy=pos.strategy,
        stop_loss=pos.stop_loss,
        target=pos.target,
        notes=pos.notes,
        status="OPEN"
    )
    db.add(new_pos)
    db.commit()
    return {"status": "success", "message": "Position added"}

@router.post("/api/crypto/positions/{position_id}/close")
def close_position(position_id: int, close_data: CryptoClose, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    pos = db.query(models.CryptoPosition).filter(
        models.CryptoPosition.id == position_id,
        models.CryptoPosition.user_id == current_user.id
    ).first()
    
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
        
    pos.status = "CLOSED"
    pos.exit_price = close_data.exit_price
    pos.exit_date = close_data.exit_date or datetime.now().strftime("%Y-%m-%d")
    pos.current_price = close_data.exit_price # Freeze price
    if close_data.notes:
        pos.notes = (pos.notes or "") + f" | Closed: {close_data.notes}"
        
    db.commit()
    return {"status": "success", "message": "Position closed"}

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

@router.get("/api/crypto/trades/history")
def get_trade_history(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Get history of CLOSED crypto trades."""
    trades = db.query(models.CryptoPosition).filter(
        models.CryptoPosition.user_id == current_user.id,
        models.CryptoPosition.status == "CLOSED"
    ).order_by(models.CryptoPosition.exit_date.desc()).all()
    
    formatted = []
    for t in trades:
        invested = t.amount * t.entry_price
        exit_val = t.amount * (t.exit_price or 0)
        pnl = exit_val - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0
        
        formatted.append({
            "id": t.id,
            "ticker": t.ticker,
            "entry_date": t.entry_date,
            "exit_date": t.exit_date,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "shares": t.amount, # Frontend expects 'shares'
            "pnl": round(pnl, 2),
            "pnl_percent": round(pnl_pct, 2), # Frontend expects 'pnl_percent'
            "strategy": t.strategy,
            "notes": t.notes,
            "status": "CLOSED"
        })
        
    return formatted

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


# --- ANALYTICS ENDPOINTS ---

@router.get("/api/crypto/trades/analytics/open")
def get_crypto_open_analytics(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Get open positions analytics for Crypto portfolio."""
    
    # Get positions
    positions = db.query(models.CryptoPosition).filter(
        models.CryptoPosition.user_id == current_user.id
    ).all()
    
    total_invested = 0
    total_value = 0
    active_count = len(positions)
    
    # Holdings and distributions
    holdings_data = []
    sector_data = {}  # Category: Layer1, DeFi, Stablecoin, etc
    asset_types = {'Layer1': 0, 'DeFi': 0, 'Stablecoin': 0, 'Other': 0}
    
    # Crypto categories
    CRYPTO_CATEGORIES = {
        'BTC': 'Layer1', 'ETH': 'Layer1', 'SOL': 'Layer1', 'ADA': 'Layer1', 'DOT': 'Layer1',
        'LINK': 'DeFi', 'UNI': 'DeFi', 'AAVE': 'DeFi', 'CAKE': 'DeFi', 'SUSHI': 'DeFi',
        'USDT': 'Stablecoin', 'USDC': 'Stablecoin', 'DAI': 'Stablecoin', 'FDUSD': 'Stablecoin'
    }
    
    # Get live prices from price_service cache (fast)
    import price_service
    live_prices = {}
    
    for pos in positions:
        price_data = price_service.get_crypto_price(pos.ticker.upper())
        if price_data and price_data.get('price'):
            live_prices[pos.ticker] = price_data['price']
    
    # Stablecoins always = 1.0
    for stable in ['USDT', 'USDC', 'DAI', 'FDUSD']: 
        live_prices[stable] = 1.0
    
    for pos in positions:
        invested = pos.amount * pos.entry_price
        price = live_prices.get(pos.ticker, pos.current_price or pos.entry_price)
        value = pos.amount * price
        pnl = value - invested
        
        total_invested += invested
        total_value += value
        
        # Asset type and sector tracking
        category = CRYPTO_CATEGORIES.get(pos.ticker.upper(), 'Other')
        if category in asset_types:
            asset_types[category] += value
        else:
            asset_types['Other'] += value
            
        if category not in sector_data:
            sector_data[category] = 0
        sector_data[category] += value
        
        # Holdings data
        pct = (value / total_value * 100) if total_value > 0 else 0
        holdings_data.append({
            'ticker': pos.ticker,
            'name': pos.ticker,
            'shares': pos.amount,
            'value': round(value, 2),
            'pnl': round(pnl, 2),
            'pct': round(pct, 2),
            'beta': 1.5,  # Crypto is generally high beta
            'pe': 0  # N/A for crypto
        })
    
    # Sort holdings by value
    holdings_data.sort(key=lambda x: x['value'], reverse=True)
    
    # Recalculate percentages
    for h in holdings_data:
        h['pct'] = round((h['value'] / total_value * 100) if total_value > 0 else 0, 2)
    
    unrealized_pnl = total_value - total_invested
    
    # Convert to list formats
    sector_allocation = [{'sector': k, 'value': round(v, 2)} for k, v in sector_data.items()]
    sector_allocation.sort(key=lambda x: x['value'], reverse=True)
    asset_allocation = [{'type': k, 'value': round(v, 2)} for k, v in asset_types.items() if v > 0]
    
    # Suggestions
    suggestions = []
    if total_invested > 0:
        pnl_pct = (unrealized_pnl / total_invested) * 100
        if pnl_pct < -20:
            suggestions.append({"type": "warning", "message": f"Portfolio down {pnl_pct:.1f}%. Consider DCA or rebalancing."})
        elif pnl_pct > 50:
            suggestions.append({"type": "info", "message": f"Excellent gains! +{pnl_pct:.1f}%. Consider taking profits."})
    
    if len(holdings_data) < 3:
        suggestions.append({"type": "info", "message": "Low diversification. Consider adding more assets."})
    
    return {
        "exposure": {
            "total_invested": round(total_invested, 2),
            "total_value": round(total_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "active_count": active_count,
            "portfolio_beta": 1.5,
            "portfolio_pe": 0
        },
        "asset_allocation": asset_allocation,
        "sector_allocation": sector_allocation,
        "holdings": holdings_data[:10],
        "suggestions": suggestions,
        "upcoming_dividends": []
    }


@router.get("/api/crypto/trades/analytics/performance")
def get_crypto_performance(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Get crypto performance analytics (P&L over time)."""
    
    # Get snapshots for crypto data
    snapshots = db.query(models.PortfolioSnapshot).filter(
        models.PortfolioSnapshot.user_id == current_user.id
    ).order_by(models.PortfolioSnapshot.date.asc()).all()
    
    line_data = {
        "dates": [s.date for s in snapshots],
        "crypto_value": [s.crypto_value_usd or 0 for s in snapshots],
        "crypto_invested": [s.crypto_invested_usd or 0 for s in snapshots],
        "crypto_pnl": [s.crypto_pnl_usd or 0 for s in snapshots]
    }
    
    # Current portfolio metrics
    positions = db.query(models.CryptoPosition).filter(
        models.CryptoPosition.user_id == current_user.id
    ).all()
    
    current_invested = sum(p.amount * p.entry_price for p in positions)
    current_value = sum(p.amount * (p.current_price or p.entry_price) for p in positions)
    current_pnl = current_value - current_invested
    
    # Top gainers/losers
    performance_by_coin = []
    for pos in positions:
        invested = pos.amount * pos.entry_price
        value = pos.amount * (pos.current_price or pos.entry_price)
        pnl = value - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0
        performance_by_coin.append({
            "ticker": pos.ticker,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2)
        })
    
    # Sort by P&L%
    performance_by_coin.sort(key=lambda x: x["pnl_pct"], reverse=True)
    
    return {
        "line_data": line_data,
        "current_metrics": {
            "total_invested": round(current_invested, 2),
            "total_value": round(current_value, 2),
            "total_pnl": round(current_pnl, 2),
            "roi_pct": round((current_pnl / current_invested * 100) if current_invested > 0 else 0, 2)
        },
        "top_performers": performance_by_coin[:5],
        "worst_performers": performance_by_coin[-5:][::-1] if len(performance_by_coin) > 5 else []
    }


@router.get("/api/crypto/trades/snapshots")
def get_crypto_snapshots(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Get crypto portfolio snapshots."""
    snapshots = db.query(models.PortfolioSnapshot).filter(
        models.PortfolioSnapshot.user_id == current_user.id
    ).order_by(models.PortfolioSnapshot.date.desc()).limit(30).all()
    
    return [{
        "date": s.date,
        "crypto_invested_usd": s.crypto_invested_usd or 0,
        "crypto_value_usd": s.crypto_value_usd or 0,
        "crypto_pnl_usd": s.crypto_pnl_usd or 0
    } for s in snapshots]
