"""
Trade Journal & Performance Tracker (ORM Version)
Refactored to support Multi-Tenancy and PostgreSQL via SQLAlchemy.
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc
from typing import List, Optional
import traceback
from datetime import datetime, date as date_type

import indicators
import market_data
import price_service
from database import get_db
import models
import auth

# Force deploy trigger after CI workaround
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


@router.get("/api/trades/cached-summary")
def get_cached_summary(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """
    FAST endpoint - Returns last known portfolio values from DB without external API calls.
    Used for instant UI load, then background updates fetch live data.
    """
    try:
        # Get open trades from DB (no external calls)
        open_trades = db.query(models.Trade).filter(
            models.Trade.user_id == current_user.id,
            models.Trade.status == 'OPEN'
        ).all()
        
        # Get latest snapshot for cached values
        last_snapshot = db.query(models.PortfolioSnapshot).filter(
            models.PortfolioSnapshot.user_id == current_user.id
        ).order_by(desc(models.PortfolioSnapshot.date)).first()
        
        # Calculate from DB values only (no yfinance)
        total_invested = sum([(t.entry_price or 0) * (t.shares or 0) for t in open_trades])
        
        # Use last snapshot for approximate current value
        cached_value = last_snapshot.total_value_usd if last_snapshot else total_invested
        cached_pnl = (cached_value - total_invested) if last_snapshot else 0
        cached_pnl_pct = (cached_pnl / total_invested * 100) if total_invested > 0 else 0
        
        # Avg holding days
        from datetime import date as date_type
        today = date_type.today()
        total_days = 0
        for t in open_trades:
            if t.entry_date:
                try:
                    if isinstance(t.entry_date, str):
                        ed = datetime.strptime(t.entry_date, '%Y-%m-%d').date()
                    else:
                        ed = t.entry_date
                    total_days += (today - ed).days
                except:
                    pass
        avg_days = total_days // len(open_trades) if open_trades else 0
        
        # Format snapshot date safely
        snapshot_date_str = None
        if last_snapshot and last_snapshot.date:
            try:
                snapshot_date_str = last_snapshot.date.strftime('%Y-%m-%d')
            except:
                snapshot_date_str = str(last_snapshot.date)
        
        return {
            "total_invested": round(total_invested, 2),
            "cached_value": round(cached_value, 2),
            "cached_pnl": round(cached_pnl, 2),
            "cached_pnl_pct": round(cached_pnl_pct, 2),
            "open_count": len(open_trades),
            "avg_holding_days": avg_days,
            "snapshot_date": snapshot_date_str,
            "is_stale": True  # Indicate this is cached data, will be updated
        }
    except Exception as e:
        print(f"[cached-summary] Error: {e}")
        import traceback
        traceback.print_exc()
        # Return safe defaults instead of 500
        return {
            "total_invested": 0,
            "cached_value": 0,
            "cached_pnl": 0,
            "cached_pnl_pct": 0,
            "open_count": 0,
            "avg_holding_days": 0,
            "snapshot_date": None,
            "is_stale": True,
            "error": str(e)
        }


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
        
        if not results:
             return {"dates": [], "equity": [], "benchmarks": {"SPY": [], "QQQ": []}}
        
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
        print(f"[equity-curve] Error: {e}")
        import traceback
        traceback.print_exc()
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
    """Delete ALL trades for current user and clear snapshots."""
    count = db.query(models.Trade).filter(models.Trade.user_id == current_user.id).delete()
    # Also clear snapshots since all trade history is gone
    snap_count = db.query(models.PortfolioSnapshot).filter(models.PortfolioSnapshot.user_id == current_user.id).delete()
    db.commit()
    return {"status": "success", "message": f"Deleted {count} trades and {snap_count} snapshots", "count": count}


@router.post("/api/trades/rebuild-history")
def rebuild_history_endpoint(background_tasks: BackgroundTasks, current_user: models.User = Depends(auth.get_current_user)):
    """Manually trigger snapshot rebuild to fix any data inconsistencies (Background Task)."""
    
    def run_rebuild(uid: int):
        try:
            import portfolio_snapshots
            # Pass db=None so it creates a fresh session for the background thread
            portfolio_snapshots.rebuild_history(uid, None)
        except Exception as e:
            print(f"[Rebuild History] Background Task Error: {e}")

    background_tasks.add_task(run_rebuild, current_user.id)
    return {"status": "success", "message": "History rebuild started in background. Please wait a few moments."}


@router.delete("/api/trades/{trade_id}")
def delete_trade(trade_id: int, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Delete a specific trade and rebuild snapshots if it was closed"""
    trade = db.query(models.Trade).filter(
        models.Trade.id == trade_id, 
        models.Trade.user_id == current_user.id
    ).first()
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # Track if this was a closed trade (affects history)
    was_closed = trade.status == 'CLOSED'
    
    db.delete(trade)
    db.commit()
    
    # Rebuild snapshots if a closed trade was deleted (affects P&L history)
    if was_closed:
        try:
            import portfolio_snapshots
            # Use None to force fresh DB session (the request session may be stale)
            portfolio_snapshots.rebuild_history(current_user.id, None)
            print(f"[Delete Trade] Rebuilt snapshots for user {current_user.id} after deleting closed trade")
        except Exception as e:
            print(f"[Delete Trade] Warning: Failed to rebuild snapshots: {e}")
    
    return {"status": "deleted", "trade_id": trade_id, "history_rebuilt": was_closed}


@router.get("/api/trades/open-prices")
def get_open_prices(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Fetch live data for open trades (User Scoped) - Uses Finnhub + yfinance fallback"""
    import market_data
    import indicators
    import screener
    import price_service  # Finnhub (primary) + yfinance (fallback) with cache
    
    trades = db.query(models.Trade).filter(
        models.Trade.user_id == current_user.id,
        models.Trade.status == 'OPEN'
    ).all()
    
    if not trades: 
        return {}
    
    # Collect unique tickers
    tickers = list(set([t.ticker.upper() for t in trades if t.ticker]))
    if not tickers:
        return {}
    
    results = {}
    
    # === STEP 1: Get current prices from Finnhub (fast) with yfinance fallback ===
    try:
        live_prices = price_service.get_prices(tickers)
        print(f"[open-prices] Got {len(live_prices)} prices from price_service")
    except Exception as e:
        print(f"[open-prices] price_service error: {e}")
        live_prices = {}
    
    # === STEP 2: Get historical data for EMAs (slower, but needed for technical analysis) ===
    try:
        # Batch download historical data for EMAs (threads=False for production stability)
        data = market_data.safe_yf_download(tickers, period="2y", threads=False)
        
        for ticker in tickers:
            try:
                # Get live price from Finnhub/cache (fast)
                price_data = live_prices.get(ticker, {})
                live_price = price_data.get('price')
                live_change_pct = price_data.get('change_pct', 0)
                
                # Extract historical data for this ticker (for EMAs)
                if len(tickers) == 1:
                    df = data
                else:
                    try:
                        df = data.xs(ticker, level=1, axis=1)
                    except:
                        df = data
                
                # Calculate EMAs if we have historical data
                ema_8 = ema_21 = ema_35 = ema_200 = None
                rsi_summary = None
                momentum_path = None
                
                if not df.empty and 'Close' in df.columns and len(df['Close']) >= 2:
                    close = df['Close']
                    
                    # Use live price if available, else use last historical close
                    if live_price is None:
                        live_price = float(close.iloc[-1])
                        prev_price = float(close.iloc[-2]) if len(close) > 1 else live_price
                        live_change_pct = ((live_price - prev_price) / prev_price) * 100 if prev_price > 0 else 0
                    
                    # Calculate EMAs
                    ema_8_series = close.ewm(span=8, adjust=False).mean()
                    ema_21_series = close.ewm(span=21, adjust=False).mean()
                    ema_35_series = close.ewm(span=35, adjust=False).mean()
                    ema_200_series = close.ewm(span=200, adjust=False).mean()
                    
                    ema_8 = round(float(ema_8_series.iloc[-1]), 2)
                    ema_21 = round(float(ema_21_series.iloc[-1]), 2)
                    ema_35 = round(float(ema_35_series.iloc[-1]), 2) if len(ema_35_series) > 0 else None
                    ema_200 = round(float(ema_200_series.iloc[-1]), 2) if len(ema_200_series) >= 200 else None
                    
                    try:
                        r = indicators.calculate_weekly_rsi_analytics(df)
                        if r:
                            rsi_summary = {
                                "val": round(r['rsi'], 2),
                                "bullish": r['sma3'] > r['sma14'],
                                "color": r.get('color', 'red')  # 6-tier color logic
                            }
                    except:
                        pass
                    
                    # Momentum Path (Linear Regression Forecast)
                    try:
                        path = screener.predict_future_path(df)
                        if path:
                            momentum_path = round(path[-1]["projected"], 2)
                    except:
                        pass
                
                # Skip ticker if we have no price at all
                if live_price is None:
                    print(f"[open-prices] No price for {ticker}, skipping")
                    continue
                
                results[ticker] = {
                    "price": round(live_price, 2),
                    "change_pct": round(live_change_pct, 2) if live_change_pct else 0,
                    "ema_8": ema_8,
                    "ema_21": ema_21,
                    "ema_35": ema_35,
                    "ema_200": ema_200,
                    "rsi_weekly": rsi_summary,
                    "momentum_path": momentum_path,
                    "extended_price": round(price_data.get('extended_price'), 2) if price_data.get('extended_price') else None,
                    "extended_change_pct": round(price_data.get('extended_change_pct'), 2) if price_data.get('extended_change_pct') else None,
                    "is_premarket": False,
                    "is_postmarket": False,
                    "source": price_data.get('source', 'unknown')  # Debug: show data source
                }
            except Exception as e:
                print(f"[open-prices] Error for {ticker}: {e}")
                continue
    except Exception as e:
        print(f"[open-prices] Batch download error: {e}")
        import traceback
        traceback.print_exc()
        return {}  # Return empty dict on crash to avoid 500
    
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
    
    # Get open trades
    open_trades = db.query(models.Trade).filter(
        models.Trade.user_id == current_user.id,
        models.Trade.status == "OPEN"
    ).all()
    
    total_invested = 0
    total_risk_r = 0
    unrealized_pnl = 0
    active_count = len(open_trades)
    
    # Sector and holdings tracking
    sector_data = {}
    holdings_data = []
    asset_types = {'Stock': 0, 'ETF': 0, 'Crypto': 0, 'Other': 0}
    
    # Get live prices
    live_prices = {}
    if open_trades:
        tickers = list(set([t.ticker for t in open_trades if t.ticker]))
        if tickers:
            try:
                live_prices = price_service.get_prices(tickers)
            except:
                pass
    
    for t in open_trades:
        if not t.ticker:
            continue
        cost = (t.entry_price or 0) * (t.shares or 0)
        total_invested += cost
        
        # Calculate unrealized P&L
        price_data = live_prices.get(t.ticker, {})
        current_price = price_data.get('price', t.entry_price)
        current_value = current_price * (t.shares or 0)
        trade_pnl = current_value - cost
        unrealized_pnl += trade_pnl
        
        # Calculate risk if SL hit
        if t.stop_loss and t.stop_loss > 0:
            risk = (t.entry_price - t.stop_loss) * (t.shares or 0)
            total_risk_r += max(0, risk)
        
        # Sector tracking
        sector = t.strategy or 'Unknown'
        if sector not in sector_data:
            sector_data[sector] = 0
        sector_data[sector] += cost
        
        # Asset type classification
        ticker_upper = t.ticker.upper()
        if ticker_upper in ['SPY', 'QQQ', 'ARKK', 'GBTC', 'ETHU', 'MSTU']:
            asset_types['ETF'] += cost
        elif ticker_upper.endswith('BTC') or ticker_upper.endswith('ETH'):
            asset_types['Crypto'] += cost
        else:
            asset_types['Stock'] += cost
        
        # Holdings data - add estimated beta/PE (using typical values for demo)
        # In production, these would come from a data provider
        TYPICAL_BETAS = {'TSLA': 2.1, 'NVDA': 1.7, 'AMD': 1.9, 'META': 1.3, 'AAPL': 1.2, 'MSFT': 1.1, 
                         'AMZN': 1.4, 'GOOGL': 1.1, 'SPY': 1.0, 'QQQ': 1.2, 'MSTU': 2.5, 'MARA': 2.8,
                         'COIN': 2.3, 'SHOP': 1.8, 'RDDT': 1.9, 'CLSK': 2.5, 'FCEL': 2.2}
        TYPICAL_PES = {'TSLA': 65, 'NVDA': 55, 'AMD': 45, 'META': 28, 'AAPL': 30, 'MSFT': 35,
                       'AMZN': 50, 'GOOGL': 25, 'SPY': 22, 'QQQ': 28, 'MSTU': 0, 'MARA': 0,
                       'COIN': 35, 'SHOP': 70, 'RDDT': 0, 'CLSK': 0, 'FCEL': 0}
        
        stock_beta = TYPICAL_BETAS.get(ticker_upper, 1.0 + (hash(ticker_upper) % 10) / 10)
        stock_pe = TYPICAL_PES.get(ticker_upper, 15 + (hash(ticker_upper) % 40))
        
        pct = (cost / total_invested * 100) if total_invested > 0 else 0
        holdings_data.append({
            'ticker': t.ticker,
            'name': t.ticker,
            'shares': t.shares,
            'value': round(current_value, 2),
            'pnl': round(trade_pnl, 2),
            'pct': round(pct, 2),
            'beta': round(stock_beta, 2),
            'pe': round(stock_pe, 1)
        })
    
    # Sort holdings by value descending
    holdings_data.sort(key=lambda x: x['value'], reverse=True)
    
    # Recalculate percentages after sorting (now we have total_invested)
    for h in holdings_data:
        h['pct'] = round((h['value'] / total_invested * 100) if total_invested > 0 else 0, 2)
    
    # Calculate weighted portfolio beta and P/E
    weighted_beta = 0
    weighted_pe = 0
    if total_invested > 0:
        for h in holdings_data:
            weight = h['value'] / total_invested
            weighted_beta += h['beta'] * weight
            if h['pe'] > 0:
                weighted_pe += h['pe'] * weight
    
    # Convert sector data to list format
    sector_allocation = [{'sector': k, 'value': round(v, 2)} for k, v in sector_data.items()]
    sector_allocation.sort(key=lambda x: x['value'], reverse=True)
    
    # Convert asset types to list format
    asset_allocation = [{'type': k, 'value': round(v, 2)} for k, v in asset_types.items() if v > 0]
    
    # Generate suggestions
    suggestions = []
    if total_risk_r > total_invested * 0.1:
        suggestions.append({"type": "warning", "message": f"Alto riesgo: ${total_risk_r:.0f} en riesgo (>{10}% del capital)"})
    if active_count > 10:
        suggestions.append({"type": "info", "message": f"Tienes {active_count} posiciones abiertas. Considera consolidar."})
    if unrealized_pnl < 0:
        suggestions.append({"type": "caution", "message": f"P&L negativo: ${unrealized_pnl:.0f}. Revisa posiciones perdedoras."})
    
    # Fetch upcoming dividends for open positions
    upcoming_dividends = []
    try:
        import yfinance as yf
        from datetime import datetime, timedelta
        
        tickers = list(set([t.ticker for t in open_trades if t.ticker]))[:10]  # Limit to 10 for speed
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                # Get dividend info
                info = stock.info
                
                div_yield = info.get('dividendYield', 0) or 0
                div_rate = info.get('dividendRate', 0) or 0
                ex_div_date = info.get('exDividendDate', None)
                
                if div_rate > 0:
                    # Find shares owned
                    shares_owned = sum([t.shares for t in open_trades if t.ticker == ticker])
                    expected_payment = div_rate * shares_owned / 4  # Quarterly estimate
                    
                    # Format ex-dividend date
                    ex_date_str = None
                    if ex_div_date:
                        try:
                            if isinstance(ex_div_date, (int, float)):
                                ex_date = datetime.fromtimestamp(ex_div_date)
                                ex_date_str = ex_date.strftime('%Y-%m-%d')
                            else:
                                ex_date_str = str(ex_div_date)
                        except:
                            pass
                    
                    upcoming_dividends.append({
                        "ticker": ticker,
                        "yield": round(div_yield * 100, 2) if div_yield else 0,
                        "rate": round(div_rate, 2),
                        "ex_date": ex_date_str,
                        "shares": shares_owned,
                        "expected": round(expected_payment, 2)
                    })
            except:
                continue
        
        # Sort by expected payment descending
        upcoming_dividends.sort(key=lambda x: x['expected'], reverse=True)
    except Exception as e:
        print(f"[Dividends] Error fetching: {e}")
    
    return {
        "exposure": {
            "total_invested": round(total_invested, 2),
            "total_risk_r": round(total_risk_r, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "active_count": active_count,
            "portfolio_beta": round(weighted_beta, 2),
            "portfolio_pe": round(weighted_pe, 1)
        },
        "asset_allocation": asset_allocation,
        "sector_allocation": sector_allocation,
        "holdings": holdings_data[:10],  # Top 10
        "suggestions": suggestions,
        "upcoming_dividends": upcoming_dividends
    }

@router.get("/api/trades/analytics/performance")
def get_portfolio_performance(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Detailed performance analysis with historical comparison"""
    from datetime import datetime, timedelta
    import yfinance as yf
    
    # Get closed trades for monthly analysis
    closed_trades = db.query(models.Trade).filter(
        models.Trade.user_id == current_user.id,
        models.Trade.status == "CLOSED"
    ).all()
    
    # Calculate monthly P&L
    monthly_data = {}
    for t in closed_trades:
        if t.exit_date and t.pnl is not None:
            try:
                # Parse exit_date
                if isinstance(t.exit_date, str):
                    exit_dt = datetime.strptime(t.exit_date, "%Y-%m-%d")
                else:
                    exit_dt = t.exit_date
                month_key = exit_dt.strftime("%Y-%m")
                if month_key not in monthly_data:
                    monthly_data[month_key] = {"pnl": 0, "trades": 0, "wins": 0}
                monthly_data[month_key]["pnl"] += t.pnl
                monthly_data[month_key]["trades"] += 1
                if t.pnl > 0:
                    monthly_data[month_key]["wins"] += 1
            except:
                pass
    
    # Sort by month
    sorted_months = sorted(monthly_data.keys())
    monthly_list = []
    for month in sorted_months:
        data = monthly_data[month]
        win_rate = (data["wins"] / data["trades"] * 100) if data["trades"] > 0 else 0
        monthly_list.append({
            "month": month,
            "pnl": round(data["pnl"], 2),
            "trades": data["trades"],
            "win_rate": round(win_rate, 1)
        })
    # Get cumulative equity data from snapshots - LAST 90 DAYS ONLY for meaningful comparison
    from datetime import datetime, timedelta
    # FIX: Use string format for VARCHAR date column comparison
    cutoff_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    
    snapshots = db.query(models.PortfolioSnapshot).filter(
        models.PortfolioSnapshot.user_id == current_user.id,
        models.PortfolioSnapshot.date >= cutoff_date
    ).order_by(models.PortfolioSnapshot.date.asc()).all()
    
    # Build portfolio P&L data from snapshots
    dates = []
    portfolio_pnl_pct = []  # TRUE P&L % = (value - invested) / invested
    portfolio_values = []  # Dollar values for chart
    for s in snapshots:
        val = s.total_value_usd or 0
        inv = s.total_invested_usd or val
        if val > 0 and inv > 0:
            pnl_pct = ((val - inv) / inv) * 100
            dates.append(s.date.strftime("%Y-%m-%d") if hasattr(s.date, 'strftime') else str(s.date))
            portfolio_pnl_pct.append(round(pnl_pct, 2))
            portfolio_values.append(round(val, 2))
    
    # Use portfolio_pnl_pct for chart
    portfolio_pct = portfolio_pnl_pct
    
    # Fetch SPY data for benchmark comparison
    spy_pct = []
    spy_values = []
    if dates:
        try:
            # Get date range
            start_date = dates[0]
            end_date = dates[-1] if len(dates) > 1 else dates[0]
            
            # Fetch SPY data from yfinance
            spy_data = yf.download("SPY", start=start_date, end=end_date, progress=False)
            
            if not spy_data.empty:
                spy_close = spy_data['Close']
                if hasattr(spy_close, 'iloc') and len(spy_close) > 0:
                    spy_start = float(spy_close.iloc[0])
                    
                    # For each portfolio date, find closest SPY price
                    for date_str in dates:
                        try:
                            # Find exact or nearest date in SPY data
                            if date_str in spy_close.index.strftime('%Y-%m-%d').tolist():
                                idx = spy_close.index.strftime('%Y-%m-%d').tolist().index(date_str)
                                spy_val = float(spy_close.iloc[idx])
                            else:
                                # Use last available value before this date
                                mask = spy_close.index <= date_str
                                if mask.any():
                                    spy_val = float(spy_close[mask].iloc[-1])
                                else:
                                    spy_val = spy_start
                            
                            spy_values.append(round(spy_val, 2))
                            pct_change = ((spy_val - spy_start) / spy_start) * 100
                            spy_pct.append(round(pct_change, 2))
                        except:
                            spy_values.append(spy_values[-1] if spy_values else 0)
                            spy_pct.append(spy_pct[-1] if spy_pct else 0)
        except Exception as e:
            print(f"[Performance] SPY fetch error: {e}")
            spy_pct = [0] * len(dates)
            spy_values = [0] * len(dates)
    
    # Fill in if SPY data is shorter than portfolio data
    while len(spy_pct) < len(dates):
        spy_pct.append(spy_pct[-1] if spy_pct else 0)
        spy_values.append(spy_values[-1] if spy_values else 0)
    
    line_data = {
        "dates": dates,
        "portfolio": portfolio_pct,  # Now in % change
        "portfolio_dollar": portfolio_values,  # Absolute values
        "spy": spy_pct,  # SPY % change from start
        "spy_dollar": spy_values  # SPY absolute values
    }
    
    return {
        "line_data": line_data,
        "monthly_data": monthly_list,
        "period_start": sorted_months[0] if sorted_months else None,
        "total_closed_trades": len(closed_trades),
        "total_realized_pnl": sum(t.pnl or 0 for t in closed_trades)
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
    # Fix: Case-insensitive status check for Postgres - include ALL common variations
    # Also log ALL trades for the user to diagnose status values
    all_usa_trades = db.query(models.Trade).filter(
        models.Trade.user_id == current_user.id
    ).all()
    
    # Log status breakdown
    status_counts = {}
    for t in all_usa_trades:
        s = t.status or "NULL"
        status_counts[s] = status_counts.get(s, 0) + 1
    print(f"[Unified Metrics] User {current_user.id} ALL USA trades: {len(all_usa_trades)}, Status breakdown: {status_counts}")
    
    # Filter for OPEN trades (case-insensitive)
    usa_trades = [t for t in all_usa_trades if t.status and t.status.upper() == "OPEN"]
    
    print(f"[Unified Metrics] Found {len(usa_trades)} OPEN USA trades (after filter)")
    
    usa_invested = sum([t.entry_price * t.shares for t in usa_trades])
    usa_pnl = 0
    
    # Fetch live prices using price_service (cached + Finnhub/yfinance failover)
    if usa_trades:
        tickers = list(set([t.ticker for t in usa_trades if t.ticker]))
        if tickers:
            try:
                # price_service handles caching and provider failover
                live_prices = price_service.get_prices(tickers)
                
                for t in usa_trades:
                    if not t.ticker:
                        continue
                    price_data = live_prices.get(t.ticker)
                    if price_data and price_data.get('price'):
                        cost = t.entry_price * t.shares
                        current_val = price_data['price'] * t.shares
                        usa_pnl += (current_val - cost)
                    elif t.pnl is not None:
                        usa_pnl += t.pnl
            except Exception as e:
                print(f"[Unified Metrics] Error fetching prices: {e}")
                usa_pnl = sum([t.pnl for t in usa_trades if t.pnl is not None])
    
    # 3. Argentina Metrics
    all_arg_pos = db.query(models.ArgentinaPosition).filter(
        models.ArgentinaPosition.user_id == current_user.id
    ).all()
    
    # Log status breakdown
    arg_status_counts = {}
    for p in all_arg_pos:
        s = p.status or "NULL"
        arg_status_counts[s] = arg_status_counts.get(s, 0) + 1
    print(f"[Unified Metrics] User {current_user.id} ALL ARG positions: {len(all_arg_pos)}, Status breakdown: {arg_status_counts}")
    
    # Filter for OPEN (case-insensitive)
    arg_pos = [p for p in all_arg_pos if p.status and p.status.upper() == "OPEN"]
    
    print(f"[Unified Metrics] Found {len(arg_pos)} OPEN ARG positions (after filter)")
    
    arg_invested_ars = sum([p.entry_price * p.shares for p in arg_pos])
    arg_pnl_ars = 0
    
    # Fetch Argentina live prices using price_service
    if arg_pos:
        arg_tickers = list(set([p.ticker for p in arg_pos if p.ticker]))
        for pos in arg_pos:
            if not pos.ticker:
                continue
            try:
                price_data = price_service.get_argentina_price(pos.ticker)
                if price_data and price_data.get('price'):
                    cost = pos.entry_price * pos.shares
                    current_val = price_data['price'] * pos.shares
                    arg_pnl_ars += (current_val - cost)
            except Exception as e:
                print(f"[Unified Metrics] Argentina price error for {pos.ticker}: {e}")
    
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
            "position_count": len(usa_trades),
            "positions": [{"ticker": t.ticker, "shares": t.shares, "entry_price": t.entry_price} for t in usa_trades]
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
                
                # Parse optional fields: SL, TP, Strategy
                stop_loss = None
                target = None
                strategy = None
                
                # Stop Loss - try multiple column names
                sl_val = row.get("stop_loss") or row.get("sl") or row.get("SL") or row.get("stoploss")
                if sl_val:
                    try:
                        stop_loss = float(str(sl_val).replace(",", ".").replace("$", ""))
                    except: pass
                
                # Target/TP - try multiple column names  
                tp_val = row.get("target") or row.get("tp") or row.get("TP") or row.get("take_profit") or row.get("target1")
                if tp_val:
                    try:
                        target = float(str(tp_val).replace(",", ".").replace("$", ""))
                    except: pass
                
                # Strategy
                strategy = row.get("strategy") or row.get("Strategy") or row.get("setup") or row.get("pattern")
                if strategy:
                    strategy = str(strategy).strip()
                
                # Direction (LONG/SHORT)
                direction = row.get("direction", "LONG").upper()
                if direction not in ["LONG", "SHORT"]:
                    direction = "LONG"
                
                # Additional targets
                target2 = None
                target3 = None
                if row.get("target2"):
                    try:
                        target2 = float(str(row.get("target2")).replace(",", ".").replace("$", ""))
                    except: pass
                if row.get("target3"):
                    try:
                        target3 = float(str(row.get("target3")).replace(",", ".").replace("$", ""))
                    except: pass
                
                # Elliott pattern and risk level
                elliott_pattern = row.get("elliott_pattern") or row.get("elliott")
                if elliott_pattern:
                    elliott_pattern = str(elliott_pattern).strip()
                    
                risk_level = row.get("risk_level") or row.get("risk")
                if risk_level:
                    risk_level = str(risk_level).strip()
                
                # PnL percent from CSV (for closed trades)
                pnl_percent = None
                if row.get("pnl_percent"):
                    try:
                        pnl_percent = float(str(row.get("pnl_percent")).replace(",", ".").replace("%", ""))
                    except: pass
                        
                trade = models.Trade(
                    user_id=current_user.id,
                    ticker=ticker,
                    entry_date=entry_date,
                    entry_price=entry_price,
                    shares=shares,
                    direction=direction,
                    status=status,
                    exit_date=exit_date,
                    exit_price=exit_price,
                    pnl=pnl,
                    pnl_percent=pnl_percent,
                    stop_loss=stop_loss,
                    target=target,
                    target2=target2,
                    target3=target3,
                    strategy=strategy,
                    elliott_pattern=elliott_pattern,
                    risk_level=risk_level,
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

@router.get("/api/trades/analytics/performance")
def get_performance_analytics(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Get stock portfolio performance analytics (P&L over time + Current Metrics)."""
    
    # 1. Line Chart Data (from snapshots)
    snapshots = db.query(models.PortfolioSnapshot).filter(
        models.PortfolioSnapshot.user_id == current_user.id
    ).order_by(models.PortfolioSnapshot.date.asc()).all()
    
    line_data = {
        "dates": [s.date for s in snapshots],
        "value": [s.total_value_usd for s in snapshots], 
        "invested": [s.total_invested_usd for s in snapshots],
        "pnl": [s.total_pnl_usd for s in snapshots]
    }
    
    # 2. Current Portfolio Metrics (Open Trades)
    open_trades = db.query(models.Trade).filter(
        models.Trade.user_id == current_user.id,
        models.Trade.status == 'OPEN'
    ).all()
    
    current_invested = sum((t.entry_price or 0) * t.shares for t in open_trades)
    
    # Estimate current value
    current_value = 0
    import price_service
    
    for t in open_trades:
        if not t.ticker: continue
        try:
            price_data = price_service.get_price(t.ticker) # Uses cache
            
            # Robust price logic: Cache -> Entry -> 0
            price = None
            if price_data and price_data.get('price'):
                price = price_data.get('price')
            
            if price is None:
                price = t.entry_price or 0
                
            current_value += price * t.shares
        except Exception as e:
            print(f"[Performance] Error evaluating open trade {t.ticker}: {e}")
            # Fallback to cost basis
            current_value += (t.entry_price or 0) * t.shares

    current_pnl = current_value - current_invested
    
    # 3. Top/Worst Performers (All trades)
    try:
        all_trades = db.query(models.Trade).filter(
            models.Trade.user_id == current_user.id
        ).all()
        
        performance_by_ticker = []
        for t in all_trades:
            if not t.ticker: continue
            
            pnl = 0
            pnl_pct = 0
            
            if t.status == 'CLOSED':
                pnl = t.pnl or 0
                pnl_pct = t.pnl_percent or 0
            else:
                # Open PnL
                try:
                    price_data = price_service.get_price(t.ticker)
                    # Safe fallback: Current Price > Entry Price > 0
                    current_price = price_data.get('price') if price_data else None
                    if current_price is None: current_price = t.entry_price or 0
                    
                    val = current_price * t.shares
                    cost = (t.entry_price or 0) * t.shares
                    pnl = val - cost
                    pnl_pct = (pnl / cost * 100) if cost > 0 else 0
                except Exception as ex:
                    print(f"[Performance] Error calc open PnL for {t.ticker}: {ex}")
                    continue
                
            performance_by_ticker.append({
                "ticker": t.ticker,
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "status": t.status
            })
            
        performance_by_ticker.sort(key=lambda x: x["pnl_pct"], reverse=True)
        
        return {
            "line_data": line_data,
            "current_metrics": {
                "total_invested": round(current_invested, 2),
                "total_value": round(current_value, 2),
                "total_pnl": round(current_pnl, 2),
                "roi_pct": round((current_pnl / current_invested * 100) if current_invested > 0 else 0, 2)
            },
            "top_performers": performance_by_ticker[:5],
            "worst_performers": performance_by_ticker[-5:][::-1] if len(performance_by_ticker) > 5 else []
        }
    except Exception as e:
        print(f"[Performance] Critical Error: {e}")
        import traceback
        traceback.print_exc()
        # Return empty structure to prevent frontend crash
        return {
            "line_data": {"dates": [], "value": [], "invested": [], "pnl": []},
            "current_metrics": {"total_invested": 0, "total_value": 0, "total_pnl": 0, "roi_pct": 0},
            "top_performers": [],
            "worst_performers": []
        }
