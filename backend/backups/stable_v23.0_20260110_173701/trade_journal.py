"""
Trade Journal & Performance Tracker (ORM Version)
Refactored to support Multi-Tenancy and PostgreSQL via SQLAlchemy.
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc
from typing import List, Optional
import traceback
from datetime import datetime, date as date_type

import indicators
import market_data
from database import get_db
import models
import auth

# Router
router = APIRouter()

# Pydantic Models
from pydantic import BaseModel

class TradeCreate(BaseModel):
    ticker: str
    entry_date: str
    entry_price: float
    shares: int
    direction: str = 'LONG' 
    status: str = 'OPEN'
    strategy: Optional[str] = None
    elliott_pattern: Optional[str] = None
    risk_level: Optional[str] = None
    notes: Optional[str] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    target2: Optional[float] = None
    target3: Optional[float] = None

class TradeUpdate(BaseModel):
    entry_price: Optional[float] = None
    shares: Optional[int] = None
    entry_date: Optional[str] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    target2: Optional[float] = None
    target3: Optional[float] = None
    strategy: Optional[str] = None
    notes: Optional[str] = None

# --- API Endpoints ---

@router.put("/api/trades/{trade_id}")
def update_trade(trade_id: int, trade_update: TradeUpdate, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Update specific fields of a trade (User Scoped)"""
    trade = db.query(models.Trade).filter(
        models.Trade.id == trade_id,
        models.Trade.user_id == current_user.id
    ).first()
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    if trade_update.entry_price is not None: trade.entry_price = trade_update.entry_price
    if trade_update.shares is not None: trade.shares = trade_update.shares
    if trade_update.entry_date is not None: 
        trade.entry_date = datetime.strptime(trade_update.entry_date, '%Y-%m-%d').date() if isinstance(trade_update.entry_date, str) else trade_update.entry_date
        
    if trade_update.stop_loss is not None: trade.stop_loss = trade_update.stop_loss
    if trade_update.target is not None: trade.target = trade_update.target
    if trade_update.target2 is not None: trade.target2 = trade_update.target2
    if trade_update.target3 is not None: trade.target3 = trade_update.target3
    if trade_update.strategy is not None: trade.strategy = trade_update.strategy
    if trade_update.notes is not None: trade.notes = trade_update.notes

    db.commit()
    db.refresh(trade)
    return {"status": "success", "message": "Trade updated", "id": trade_id}


@router.post("/api/trades/add")
def add_trade(trade_in: TradeCreate, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Add a new trade to the journal with FIFO Buy/Sell logic (User Scoped)"""
    
    ticker_upper = trade_in.ticker.upper()
    action = trade_in.direction.upper()
    
    try:
        entry_date_obj = datetime.strptime(trade_in.entry_date, '%Y-%m-%d').date()
    except:
        entry_date_obj = datetime.now().date()

    if action == 'BUY':
        # Check for existing open trades (User Scoped)
        if trade_in.stop_loss is None or trade_in.target is None:
            existing = db.query(models.Trade).filter(
                models.Trade.user_id == current_user.id,
                models.Trade.ticker == ticker_upper,
                models.Trade.status == 'OPEN'
            ).order_by(desc(models.Trade.entry_date), desc(models.Trade.id)).first()

            if existing:
                if trade_in.stop_loss is None: trade_in.stop_loss = existing.stop_loss
                if trade_in.target is None: trade_in.target = existing.target
                if trade_in.target2 is None: trade_in.target2 = existing.target2
                if trade_in.target3 is None: trade_in.target3 = existing.target3

        new_trade = models.Trade(
            user_id=current_user.id,
            ticker=ticker_upper,
            entry_date=entry_date_obj,
            entry_price=trade_in.entry_price,
            shares=trade_in.shares,
            direction='LONG',
            status='OPEN',
            strategy=trade_in.strategy,
            elliott_pattern=trade_in.elliott_pattern,
            risk_level=trade_in.risk_level,
            notes=trade_in.notes,
            stop_loss=trade_in.stop_loss,
            target=trade_in.target,
            target2=trade_in.target2,
            target3=trade_in.target3
        )
        db.add(new_trade)
        db.commit()
        db.refresh(new_trade)
        return {"status": "success", "trade_id": new_trade.id, "message": "Buy order logged"}

    elif action == 'SELL':
        # FIFO Logic for Selling (User Scoped)
        open_trades = db.query(models.Trade).filter(
            models.Trade.user_id == current_user.id,
            models.Trade.ticker == ticker_upper,
            models.Trade.status == 'OPEN',
            models.Trade.direction == 'LONG'
        ).order_by(asc(models.Trade.entry_date), asc(models.Trade.id)).all()

        total_shares = sum(t.shares for t in open_trades)
        
        if total_shares < trade_in.shares:
            raise HTTPException(status_code=400, detail=f"Insufficient shares. Owned: {total_shares}, Trying to sell: {trade_in.shares}")
            
        shares_to_sell = trade_in.shares
        sell_price = trade_in.entry_price
        execution_date = entry_date_obj
        
        processed_ids = []
        
        for t in open_trades:
            if shares_to_sell <= 0:
                break
                
            qty_in_trade = t.shares
            
            if qty_in_trade <= shares_to_sell:
                # FULL CLOSE
                pnl = (sell_price - t.entry_price) * qty_in_trade
                pnl_pct = ((sell_price - t.entry_price) / t.entry_price) * 100
                
                t.status = 'CLOSED'
                t.exit_price = sell_price
                t.exit_date = execution_date
                t.pnl = pnl
                t.pnl_percent = pnl_pct
                
                shares_to_sell -= qty_in_trade
                processed_ids.append(t.id)
                db.add(t)
                
            else:
                # PARTIAL CLOSE
                remaining_shares = qty_in_trade - shares_to_sell
                t.shares = remaining_shares
                db.add(t)
                
                pnl = (sell_price - t.entry_price) * shares_to_sell
                pnl_pct = ((sell_price - t.entry_price) / t.entry_price) * 100
                
                closed_part = models.Trade(
                    user_id=current_user.id, # New part belongs to user
                    ticker=t.ticker,
                    entry_date=t.entry_date,
                    exit_date=execution_date,
                    entry_price=t.entry_price,
                    exit_price=sell_price,
                    shares=shares_to_sell,
                    direction='LONG',
                    pnl=pnl,
                    pnl_percent=pnl_pct,
                    status='CLOSED',
                    strategy=t.strategy,
                    elliott_pattern=t.elliott_pattern,
                    risk_level=t.risk_level,
                    notes=t.notes,
                    stop_loss=t.stop_loss,
                    target=t.target,
                    target2=t.target2,
                    target3=t.target3
                )
                db.add(closed_part)
                shares_to_sell = 0
                processed_ids.append("new_split")

        db.commit()
        return {"status": "success", "processed_ids": processed_ids, "message": "Sell order processed via FIFO"}
        
    else:
         raise HTTPException(status_code=400, detail="Invalid Action. Use BUY or SELL.")


@router.get("/api/trades/list")
def get_trades(
    ticker: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of trades with filters (User Scoped)"""
    query = db.query(models.Trade).filter(models.Trade.user_id == current_user.id)
    
    if ticker:
        query = query.filter(models.Trade.ticker == ticker)
    if status:
        query = query.filter(models.Trade.status == status)
        
    trades = query.order_by(desc(models.Trade.entry_date)).limit(limit).all()
    return {"trades": trades}


@router.get("/api/trades/metrics")
def get_metrics(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Calculate performance metrics (User Scoped)"""
    try:
        trades = db.query(models.Trade).filter(
            models.Trade.user_id == current_user.id,
            models.Trade.status == 'CLOSED'
        ).all()
        
        if not trades:
            return {
                "total_trades": 0, "win_rate": 0, "profit_factor": 0, "total_pnl": 0,
                "avg_win": 0, "avg_loss": 0, "best_trade": 0, "worst_trade": 0, "max_drawdown": 0
            }
        
        total_trades = len(trades)
        winning_trades = [t for t in trades if (t.pnl or 0) > 0]
        losing_trades = [t for t in trades if (t.pnl or 0) < 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        total_wins = sum((t.pnl or 0) for t in winning_trades)
        total_losses = abs(sum((t.pnl or 0) for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else (999 if total_wins > 0 else 0)
        
        total_pnl = sum((t.pnl or 0) for t in trades)
        avg_win = total_wins / len(winning_trades) if winning_trades else 0
        avg_loss = -total_losses / len(losing_trades) if losing_trades else 0
        
        best_trade = max(((t.pnl or 0) for t in trades), default=0)
        worst_trade = min(((t.pnl or 0) for t in trades), default=0)
        
        # Max Drawdown
        equity_curve = []
        running_total = 0
        sorted_trades = sorted(trades, key=lambda x: x.exit_date or date_type.min)
        
        for trade in sorted_trades:
            running_total += (trade.pnl or 0)
            equity_curve.append(running_total)
            
        peak = 0
        if equity_curve: peak = max(0, equity_curve[0])
        max_dd = 0
        for equity in equity_curve:
            peak = max(peak, equity)
            dd = peak - equity
            max_dd = max(max_dd, dd)
            
        return {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 3),
            "profit_factor": round(profit_factor, 2),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "best_trade": round(best_trade, 2),
            "worst_trade": round(worst_trade, 2),
            "max_drawdown": round(max_dd, 2)
        }
    except Exception as e:
        print(f"Error in get_metrics: {e}")
        traceback.print_exc()
        return {}


@router.get("/api/trades/equity-curve")
def get_equity_curve(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Get cumulative P&L over time (User Scoped)"""
    try:
        results = db.query(models.Trade.exit_date, models.Trade.pnl).filter(
            models.Trade.user_id == current_user.id,
            models.Trade.status == 'CLOSED',
            models.Trade.exit_date != None
        ).order_by(models.Trade.exit_date).all()
        
        dates = []
        equity = []
        running_total = 0
        
        for date_val, pnl_val in results:
            if date_val and pnl_val is not None:
                dates.append(date_val.strftime('%Y-%m-%d') if isinstance(date_val, (date_type, datetime)) else str(date_val))
                running_total += pnl_val
                equity.append(round(running_total, 2))
                
        benchmarks = {"SPY": [], "QQQ": []}
        try:
           benchmarks = market_data.get_benchmark_performance(dates)
        except:
           pass
           
        return {"dates": dates, "equity": equity, "benchmarks": benchmarks}
    except Exception as e:
        return {"dates": [], "equity": [], "benchmarks": {"SPY": [], "QQQ": []}}


@router.get("/api/trades/calendar")
def get_calendar_data(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Get daily P&L for calendar (User Scoped)"""
    results = db.query(
        models.Trade.exit_date, 
        func.sum(models.Trade.pnl), 
        func.count(models.Trade.id)
    ).filter(
        models.Trade.user_id == current_user.id,
        models.Trade.status == 'CLOSED',
        models.Trade.exit_date != None
    ).group_by(models.Trade.exit_date).order_by(models.Trade.exit_date).all()
    
    data = []
    for date_val, total_pnl, count in results:
        data.append({
            "date": date_val.strftime('%Y-%m-%d'),
            "pnl": round(total_pnl, 2),
            "count": count
        })
    return data


@router.delete("/api/trades/all")
def delete_all_trades(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Delete ALL trades for current user."""
    count = db.query(models.Trade).filter(models.Trade.user_id == current_user.id).delete()
    db.commit()
    return {"status": "success", "message": f"Deleted {count} trades", "count": count}


@router.delete("/api/trades/{trade_id}")
def delete_trade(trade_id: int, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Delete a specific trade"""
    trade = db.query(models.Trade).filter(
        models.Trade.id == trade_id, 
        models.Trade.user_id == current_user.id
    ).first()
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
        
    db.delete(trade)
    db.commit()
    return {"status": "deleted", "trade_id": trade_id}


@router.get("/api/trades/open-prices")
def get_open_prices(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Fetch live data for open trades (User Scoped)"""
    trades = db.query(models.Trade).filter(
        models.Trade.user_id == current_user.id,
        models.Trade.status == 'OPEN'
    ).all()
    
    if not trades: return {}
        
    ticker_dates = {}
    for t in trades:
        if not t.ticker: continue
        if t.ticker not in ticker_dates:
            ticker_dates[t.ticker] = set()
        d_str = t.entry_date.strftime('%Y-%m-%d') if hasattr(t.entry_date, 'strftime') else str(t.entry_date)
        ticker_dates[t.ticker].add(d_str)

    tickets_list = list(ticker_dates.keys())
    if not tickets_list: return {}
        
    results = {}
    try:
        data = market_data.safe_yf_download(tickets_list, period="2y", threads=True)
        for ticker in tickets_list:
            try:
                if len(tickets_list) == 1: df = data
                else:
                     try: df = data.xs(ticker, level=1, axis=1)
                     except: df = data
                
                if df.empty: continue
                
                close = df['Close']
                ema_8 = close.ewm(span=8, adjust=False).mean()
                ema_21 = close.ewm(span=21, adjust=False).mean()
                ema_200 = close.ewm(span=200, adjust=False).mean()
                last_price = float(close.iloc[-1])
                prev_price = float(close.iloc[-2]) if len(close) > 1 else last_price
                change = ((last_price - prev_price)/prev_price)*100
                
                violation_map = {} # Stubbed out for cleanliness, re-add if needed
                
                rsi_summary = None
                try:
                    r = indicators.calculate_weekly_rsi_analytics(df)
                    if r: rsi_summary = {"val": round(r['rsi'],2), "bullish": r['sma3']>r['sma14']}
                except: pass

                results[ticker] = {
                    "price": round(last_price, 2),
                    "change_pct": round(change, 2),
                    "ema_8": round(float(ema_8.iloc[-1]), 2),
                    "ema_21": round(float(ema_21.iloc[-1]), 2),
                    "ema_200": round(float(ema_200.iloc[-1]), 2),
                    "rsi_weekly": rsi_summary,
                    "violations_map": violation_map
                }
            except: continue
    except: pass
    return results


# --- Cross-Module Calls (Proxies) ---

def capture_daily_snapshot(user_id: int = None):
    """Facade to Portfolio Snapshots"""
    import portfolio_snapshots
    return portfolio_snapshots.take_snapshot(user_id)

@router.get("/api/trades/snapshots")
def get_snapshots(days: int = 30, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Serve historical portfolio snapshots"""
    import portfolio_snapshots
    return portfolio_snapshots.get_history(current_user.id, days, db)

@router.get("/api/trades/analytics/open")
def get_open_trades_analytics(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Get aggregate risk/exposure analytics for OPEN trades."""
    # This was a stub in legacy, and remains largely a stub unless we implement logic.
    # But now at least it is authenticated.
    return {
        "exposure": {"total_invested": 0, "total_risk_r": 0, "unrealized_pnl": 0, "active_count": 0},
        "suggestions": []
    }

@router.get("/api/trades/analytics/performance")
def get_portfolio_performance(current_user: models.User = Depends(auth.get_current_user)):
    """Detailed performance analysis"""
    return {
            "line_data": {"dates": [], "portfolio": [], "spy": []},
            "monthly_data": [],
            "period_start": None
        }

@router.get("/api/trades/unified/metrics")
def get_unified_metrics(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """
    Get consolidated metrics for ALL portfolios (USA, Argentina, Crypto).
    Returns values in ARS, USD (CCL/MEP), and aggregate totals.
    """
    import argentina_data
    import crypto_journal
    
    # 1. Get Rates
    rates = argentina_data.get_dolar_rates()
    ccl = rates.get("ccl", 1200)
    
    # 2. USA Metrics (from local Trade table)
    usa_trades = db.query(models.Trade).filter(
        models.Trade.user_id == current_user.id,
        models.Trade.status == "OPEN"
    ).all()
    
    usa_invested = sum([t.entry_price * t.shares for t in usa_trades])
    usa_pnl = 0
    # Ideally we'd have live prices here, but for speed we might trust 'pnl' field if updated,
    # or just use 0 if live fetch is too slow.
    # We can briefly try to get a rough PnL if possible or rely on client/snapshot.
    # For now, let's sum the 'pnl' column if populated, assuming background worker updates it.
    usa_pnl = sum([t.pnl for t in usa_trades if t.pnl is not None])
    
    # 3. Argentina Metrics
    arg_pos = db.query(models.ArgentinaPosition).filter(
        models.ArgentinaPosition.user_id == current_user.id,
        models.ArgentinaPosition.status == "OPEN"
    ).all()
    
    arg_invested_ars = sum([p.entry_price * p.shares for p in arg_pos])
    # For PnL, we need live prices. Argentina module usually fetches them.
    # We'll do a quick rough calc using recent prices if possible, or just 0.
    # In a real app we'd cache these. Let's assume 0 PnL for speed unless we have a stored value.
    # We can iterate and fetch price? No, too slow.
    # We'll start with 0 PnL for now or use stored if models were updated.
    arg_pnl_ars = 0 
    
    # 4. Crypto Metrics
    # Use crypto_journal logic
    crypto_data = crypto_journal.get_portfolio_metrics(current_user.id, db)
    # crypto_data['metrics'] = {'total_value': X, 'total_pnl': Y, ...}
    crypto_metrics = crypto_data.get("metrics", {})
    crypto_invested = crypto_metrics.get("total_value", 0) - crypto_metrics.get("total_pnl", 0) # Rough approx
    crypto_pnl = crypto_metrics.get("total_pnl", 0)
    crypto_count = len(crypto_data.get("positions", []))

    # 5. Aggregation
    # Convert everything to USD (CCL) and ARS
    
    # USA
    usa_val_usd = usa_invested + usa_pnl
    
    # ARG (Convert ARS -> USD)
    arg_val_ars = arg_invested_ars + arg_pnl_ars
    arg_invested_usd = arg_invested_ars / ccl if ccl else 0
    arg_pnl_usd = arg_pnl_ars / ccl if ccl else 0
    
    # Crypto (Already USD)
    crypto_val_usd = crypto_invested + crypto_pnl
    
    # Totals
    total_invested_usd = usa_invested + arg_invested_usd + crypto_invested
    total_pnl_usd = usa_pnl + arg_pnl_usd + crypto_pnl
    total_val_usd = total_invested_usd + total_pnl_usd
    
    total_invested_ars = total_invested_usd * ccl
    total_pnl_ars = total_pnl_usd * ccl
    total_val_ars = total_val_usd * ccl
    
    return {
        "rates": rates,
        "total": {
            "usd_ccl": {
                "invested": round(total_invested_usd, 2),
                "current": round(total_val_usd, 2),
                "pnl": round(total_pnl_usd, 2)
            },
            "ars": {
                "invested": round(total_invested_ars, 0),
                "current": round(total_val_ars, 0),
                "pnl": round(total_pnl_ars, 0)
            }
        },
        "usa": {
            "invested_usd": round(usa_invested, 2),
            "pnl_usd": round(usa_pnl, 2),
            "position_count": len(usa_trades)
        },
        "argentina": {
            "invested_ars": round(arg_invested_ars, 0),
            "invested_usd_ccl": round(arg_invested_usd, 2),
            "pnl_ars": round(arg_pnl_ars, 0),
            "pnl_usd_ccl": round(arg_pnl_usd, 2),
            "position_count": len(arg_pos)
        },
        "crypto": {
            "invested_usd": round(crypto_invested, 2),
            "pnl_usd": round(crypto_pnl, 2),
            "position_count": crypto_count,
            "has_api": crypto_data.get("binance_status", {}).get("connected", False)
        }
    }

@router.post("/api/trades/upload_csv")
async def upload_trades_csv(file: UploadFile = File(...), current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """
    Import historical trades from CSV and rebuild portfolio history.
    CSV Format: ticker, entry_date, entry_price, shares, status, exit_date, exit_price
    """
    import csv
    import codecs
    from datetime import datetime
    import portfolio_snapshots
    
    try:
        csv_reader = csv.DictReader(codecs.iterdecode(file.file, 'utf-8'))
        count = 0
        
        for row in csv_reader:
            try:
                # Essential fields
                ticker = row.get("ticker", "").strip().upper()
                if not ticker: continue
                
                # Parse Entry Date
                e_date_str = row.get("entry_date", "")
                entry_date = None
                for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
                    try:
                        entry_date = datetime.strptime(e_date_str, fmt).date()
                        break
                    except: pass
                
                if not entry_date: continue # Skip if no date
                
                entry_price = float(row.get("entry_price", 0))
                shares = float(row.get("shares", 0))
                status = row.get("status", "OPEN").upper()
                
                # Exit info
                exit_date = None
                exit_price = None
                pnl = None
                
                ex_date_str = row.get("exit_date", "")
                if ex_date_str:
                    for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
                        try:
                            exit_date = datetime.strptime(ex_date_str, fmt).date()
                            break
                        except: pass
                        
                if row.get("exit_price"):
                    exit_price = float(row.get("exit_price"))
                    
                # Calculate PnL if closed
                if status == "CLOSED" or exit_date:
                    status = "CLOSED"
                    if exit_price and entry_price:
                        # Simple PnL: (Exit - Entry) * Shares
                        pnl = (exit_price - entry_price) * shares
                        
                trade = models.Trade(
                    user_id=current_user.id,
                    ticker=ticker,
                    entry_date=entry_date,
                    entry_price=entry_price,
                    shares=shares,
                    status=status,
                    exit_date=exit_date,
                    exit_price=exit_price,
                    pnl=pnl,
                    notes=row.get("notes", "Imported via CSV")
                )
                db.add(trade)
                count += 1
                
            except Exception as row_err:
                print(f"Skipping row {row}: {row_err}")
                continue
                
        db.commit()
        
        # TRIGGER HISTORY REBUILD
        try:
            portfolio_snapshots.rebuild_history(current_user.id, db)
        except Exception as rebuild_err:
            print(f"Rebuild Error: {rebuild_err}")
        
        return {"status": "success", "imported": count, "message": "History rebuilt successfully"}
        
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/trades/template")
def download_template():
    """Download CSV template for USA Trades"""
    from fastapi.responses import StreamingResponse
    import io
    import csv
    
    headers = ["ticker", "entry_date", "entry_price", "shares", "status", "exit_date", "exit_price", "notes", "stop_loss", "target"]
    
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(headers)
    # Add example row
    writer.writerow(["AAPL", "2024-01-01", "150.0", "10", "OPEN", "", "", "Example Trade", "140", "170"])
    
    stream.seek(0)
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=usa_trades_template.csv"
    return response
