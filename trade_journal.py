"""
Trade Journal & Performance Tracker
Tracks trading performance and analyzes which scanner signals work best
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
import sqlite3
from datetime import datetime
from typing import List, Optional
import os
import yfinance as yf
import pandas as pd
import io
import traceback
import indicators
import market_data

router = APIRouter()

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), "trades.db")


def init_db():
    """Initialize database with trades table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            entry_date DATE NOT NULL,
            exit_date DATE,
            entry_price REAL NOT NULL,
            exit_price REAL,
            shares INTEGER NOT NULL,
            direction TEXT CHECK(direction IN ('LONG', 'SHORT')) NOT NULL,
            
            -- Performance
            pnl REAL,
            pnl_percent REAL,
            status TEXT CHECK(status IN ('OPEN', 'CLOSED')) DEFAULT 'OPEN',
            
            -- Context from scanner
            strategy TEXT,
            elliott_pattern TEXT,
            risk_level TEXT,
            notes TEXT,
            
            -- Risk management
            stop_loss REAL,
            target REAL,
            
            -- Metadata
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            snapshot_date DATE PRIMARY KEY,
            total_invested REAL,
            unrealized_pnl REAL,
            realized_pnl REAL,
            total_equity REAL,
            active_positions INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Cache for fundamental data (Beta, P/E, etc.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fundamentals_cache (
            ticker TEXT PRIMARY KEY,
            beta REAL,
            pe_ratio REAL,
            dividend_yield REAL,
            dividend_rate REAL,
            ex_dividend_date INTEGER,
            asset_type TEXT,
            short_name TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    print("[Trade Journal] Database initialized")
    
    # Simple migration for new columns
    # Simple migration for new columns
    try:
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE trades ADD COLUMN target2 REAL")
        conn.commit()
    except:
        pass 

    try:
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE trades ADD COLUMN target3 REAL")
        conn.commit()
    except:
        pass

    try:
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE trades ADD COLUMN external_id TEXT UNIQUE")
        conn.commit()
    except:
        pass


# Initialize DB on module load
init_db()


class Trade(BaseModel):
    ticker: str
    entry_date: str
    exit_date: Optional[str] = None
    entry_price: float
    exit_price: Optional[float] = None
    shares: int
    direction: str  # LONG or SHORT
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    target2: Optional[float] = None
    target3: Optional[float] = None
    strategy: Optional[str] = None
    elliott_pattern: Optional[str] = None
    risk_level: Optional[str] = None
    notes: Optional[str] = None

class TradeCreate(BaseModel):
    ticker: str
    entry_date: str
    entry_price: float
    shares: float
    action: str = 'BUY'
    strategy: Optional[str] = 'Imported'
    notes: Optional[str] = None

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

@router.put("/api/trades/{trade_id}")
def update_trade(trade_id: int, trade: TradeUpdate):
    """Update specific fields of a trade"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if trade exists
    cursor.execute("SELECT id FROM trades WHERE id = ?", (trade_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Trade not found")

    # Build update query dynamically
    fields = []
    values = []
    
    # Only update provided fields
    if trade.entry_price is not None:
        fields.append("entry_price = ?")
        values.append(trade.entry_price)
    
    if trade.shares is not None:
        fields.append("shares = ?")
        values.append(trade.shares)
    
    if trade.entry_date is not None:
        fields.append("entry_date = ?")
        values.append(trade.entry_date)
    
    if trade.stop_loss is not None:
        fields.append("stop_loss = ?")
        values.append(trade.stop_loss)
        
    if trade.target is not None:
        fields.append("target = ?")
        values.append(trade.target)
        
    if trade.target2 is not None:
        fields.append("target2 = ?")
        values.append(trade.target2)
        
    if trade.target3 is not None:
        fields.append("target3 = ?")
        values.append(trade.target3)

    if trade.strategy is not None:
        fields.append("strategy = ?")
        values.append(trade.strategy)
        
    if trade.notes is not None:
        fields.append("notes = ?")
        values.append(trade.notes)

    if not fields:
        conn.close()
        return {"status": "ignored", "message": "No fields to update"}

    # Add updated_at
    fields.append("updated_at = CURRENT_TIMESTAMP")
    
    query = f"UPDATE trades SET {', '.join(fields)} WHERE id = ?"
    values.append(trade_id)
    
    cursor.execute(query, values)
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": "Trade updated", "id": trade_id}


@router.post("/api/trades/add")
def add_trade(trade: Trade):
    """Add a new trade to the journal with FIFO Buy/Sell logic"""
    
    # Ensure schema is up to date (in case server wasn't restarted)
    # MUST be done before opening the main connection to avoid lock
    init_db() 
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # "Action" logic using the 'direction' field or a new paradigm?
    # The frontend will send 'direction' as "BUY" or "SELL" now to match the new UI.
    # We map "BUY" -> "LONG" entry. "SELL" -> "LONG" exit (FIFO).
    
    trade.ticker = trade.ticker.upper()
    action = trade.direction.upper()
    
    try: 
        
        if action == 'BUY':
            # Check for existing open trades to inherit SL/TP if not provided
            if trade.stop_loss is None or trade.target is None:
                cursor.execute("""
                    SELECT stop_loss, target, target2, target3 
                    FROM trades 
                    WHERE ticker = ? AND status = 'OPEN' 
                    ORDER BY entry_date DESC, id DESC LIMIT 1
                """, (trade.ticker,))
                existing = cursor.fetchone()
                
                if existing:
                    # Inherit values if currently missing
                    if trade.stop_loss is None: trade.stop_loss = existing['stop_loss']
                    if trade.target is None: trade.target = existing['target']
                    if trade.target2 is None: trade.target2 = existing['target2']
                    if trade.target3 is None: trade.target3 = existing['target3']

            # Create standard OPEN trade (Long)
            cursor.execute("""
                INSERT INTO trades (
                    ticker, entry_date, entry_price, shares, direction,
                    status, strategy, elliott_pattern, risk_level, notes,
                    stop_loss, target, target2, target3
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.ticker, trade.entry_date, trade.entry_price, trade.shares, 'LONG',
                'OPEN', trade.strategy, trade.elliott_pattern, trade.risk_level, trade.notes,
                trade.stop_loss, trade.target, trade.target2, trade.target3
            ))
            new_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return {"status": "success", "trade_id": new_id, "message": "Buy order logged"}

        elif action == 'SELL':
            # FIFO Logic for Selling
            # 1. Validation: Do we have enough shares?
            cursor.execute("""
                SELECT * FROM trades 
                WHERE ticker = ? AND status = 'OPEN' AND direction = 'LONG' 
                ORDER BY entry_date ASC, id ASC
            """, (trade.ticker,))
            
            open_trades = [dict(row) for row in cursor.fetchall()]
            total_shares = sum(t['shares'] for t in open_trades)
            
            if total_shares < trade.shares:
                conn.close()
                raise HTTPException(status_code=400, detail=f"Insufficient shares. Owned: {total_shares}, Trying to sell: {trade.shares}")
                
            shares_to_sell = trade.shares
            sell_price = trade.entry_price # For a SELL, the form sends price as entry_price field or we need to align fields
            # Note: Frontend should ideally map "Price" to entry_price for simplicity in payload, 
            # but semantically it's the execution price.
             
            # We will use 'trade.entry_price' as the execution price for the SELL based on the unified form
            execution_date = trade.entry_date
            
            processed_ids = []
            
            for t in open_trades:
                if shares_to_sell <= 0:
                    break
                    
                qty_in_trade = t['shares']
                
                if qty_in_trade <= shares_to_sell:
                    # FULL CLOSE of this trade
                    pnl = (sell_price - t['entry_price']) * qty_in_trade
                    pnl_pct = ((sell_price - t['entry_price']) / t['entry_price']) * 100
                    
                    cursor.execute("""
                        UPDATE trades 
                        SET status = 'CLOSED', exit_price = ?, exit_date = ?, pnl = ?, pnl_percent = ?
                        WHERE id = ?
                    """, (sell_price, execution_date, pnl, pnl_pct, t['id']))
                    
                    shares_to_sell -= qty_in_trade
                    processed_ids.append(t['id'])
                    
                else:
                    # PARTIAL CLOSE - Split Logic
                    # 1. Reduce shares of existing open trade
                    remaining_shares = qty_in_trade - shares_to_sell
                    cursor.execute("UPDATE trades SET shares = ? WHERE id = ?", (remaining_shares, t['id']))
                    
                    # 2. Create NEW Closed trade for the sold portion
                    pnl = (sell_price - t['entry_price']) * shares_to_sell
                    pnl_pct = ((sell_price - t['entry_price']) / t['entry_price']) * 100
                    
                    cursor.execute("""
                        INSERT INTO trades (
                            ticker, entry_date, exit_date, entry_price, exit_price, shares, direction,
                            pnl, pnl_percent, status, strategy, elliott_pattern, risk_level, notes,
                            stop_loss, target, target2, target3
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        t['ticker'], t['entry_date'], execution_date, t['entry_price'], 
                        sell_price, shares_to_sell, 'LONG',
                        pnl, pnl_pct, 'CLOSED', t.get('strategy'), t.get('elliott_pattern'), t.get('risk_level'), t.get('notes'),
                        t.get('stop_loss'), t.get('target'), t.get('target2'), t.get('target3')
                    ))
                    
                    shares_to_sell = 0
                    processed_ids.append(cursor.lastrowid)

            conn.commit()
            conn.close()
            return {"status": "success", "processed_ids": processed_ids, "message": "Sell order processed via FIFO"}
            
        else:
            conn.close()
            raise HTTPException(status_code=400, detail="Invalid Action. Use BUY or SELL.")

    except HTTPException:
        # Re-raise standard HTTP exceptions (like 400s) directly
        conn.close()
        raise
    except Exception as e:
        print(f"Error adding trade: {e}")
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/trades/list")
def get_trades(
    ticker: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
):
    """Get list of trades with optional filters"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = "SELECT * FROM trades WHERE 1=1"
    params = []
    
    if ticker:
        query += " AND ticker = ?"
        params.append(ticker)
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    query += " ORDER BY entry_date DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    
    columns = [desc[0] for desc in cursor.description]
    trades = []
    for row in cursor.fetchall():
        trades.append(dict(zip(columns, row)))
    
    conn.close()
    return {"trades": trades}


@router.get("/api/trades/metrics")
def get_metrics():
    """Calculate performance metrics"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all closed trades
        cursor.execute("SELECT * FROM trades WHERE status = 'CLOSED'")
        columns = [desc[0] for desc in cursor.description]
        trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        if not trades:
            return {
                "total_trades": 0, "win_rate": 0, "profit_factor": 0, "total_pnl": 0,
                "avg_win": 0, "avg_loss": 0, "best_trade": 0, "worst_trade": 0, "max_drawdown": 0
            }
        
        # Calculate metrics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] < 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        total_wins = sum(t['pnl'] for t in winning_trades)
        total_losses = abs(sum(t['pnl'] for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else (999 if total_wins > 0 else 0)
        
        total_pnl = sum(t['pnl'] for t in trades)
        avg_win = total_wins / len(winning_trades) if winning_trades else 0
        avg_loss = -total_losses / len(losing_trades) if losing_trades else 0
        
        best_trade = max((t['pnl'] for t in trades), default=0)
        worst_trade = min((t['pnl'] for t in trades), default=0)
        
        # Calculate max drawdown
        equity_curve = []
        running_total = 0
        for trade in sorted(trades, key=lambda x: x.get('exit_date') or ''):
            running_total += (trade.get('pnl') or 0)
            equity_curve.append(running_total)
        
        peak = equity_curve[0] if equity_curve else 0
        max_dd = 0
        for equity in equity_curve:
            peak = max(peak, equity)
            dd = peak - equity
            max_dd = max(max_dd, dd)
        
        conn.close()
        
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
        return {
            "total_trades": 0, "win_rate": 0, "profit_factor": 0, "total_pnl": 0,
            "avg_win": 0, "avg_loss": 0, "best_trade": 0, "worst_trade": 0, "max_drawdown": 0
        }


@router.get("/api/trades/equity-curve")
def get_equity_curve():
    """Get cumulative P&L over time for equity curve chart"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT exit_date, pnl 
            FROM trades 
            WHERE status = 'CLOSED' AND exit_date IS NOT NULL
            ORDER BY exit_date ASC
        """)
        
        dates = []
        equity = []
        running_total = 0
        
        for row in cursor.fetchall():
            if row[0] and row[1] is not None:
                dates.append(row[0])
                running_total += row[1]
                equity.append(round(running_total, 2))
        
        conn.close()
        
        # Fetch Benchmarks
        benchmarks = {"SPY": [], "QQQ": []}
        try:
            benchmarks = market_data.get_benchmark_performance(dates)
        except Exception as be:
            print(f"Benchmark error: {be}")
            
        return {
            "dates": dates, 
            "equity": equity,
            "benchmarks": benchmarks
        }
    except Exception as e:
        print(f"Error fetching equity curve: {e}")
        traceback.print_exc()
        return {"dates": [], "equity": [], "benchmarks": {"SPY": [], "QQQ": []}}


@router.get("/api/trades/calendar")
def get_calendar_data():
    """Get daily P&L for calendar visualization"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Group by exit_date for P&L
    cursor.execute("""
        SELECT exit_date, SUM(pnl) as total_pnl, COUNT(*) as trade_count
        FROM trades 
        WHERE status = 'CLOSED' AND exit_date IS NOT NULL
        GROUP BY exit_date
        ORDER BY exit_date ASC
    """)
    
    data = []
    for row in cursor.fetchall():
        data.append({
            "date": row[0],
            "pnl": round(row[1], 2),
            "count": row[2]
        })
        
    conn.close()
    return data


@router.delete("/api/trades/all")
def delete_all_trades():
    """Delete ALL trades - Dangerous operation!"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM trades")
    count = cursor.rowcount
    
    # Reset Auto Increment (optional but good for clean slate)
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='trades'")
    
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": f"Deleted {count} trades", "count": count}


@router.delete("/api/trades/{trade_id}")
def delete_trade(trade_id: int):
    """Delete a trade"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Trade not found")
    
    conn.commit()
    conn.close()
    
    return {"status": "deleted", "trade_id": trade_id}


@router.get("/api/trades/open-prices")
def get_open_prices():
    """Fetch current prices and EMAs for open trades, calculating violations per entry date"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all open trades: ticker -> list of entry dates
    cursor.execute("SELECT ticker, entry_date FROM trades WHERE status = 'OPEN'")
    
    ticker_dates = {}
    for row in cursor.fetchall():
        ticker, date_str = row
        if not ticker or ticker == 'DEBUG': continue
        if ticker not in ticker_dates:
            ticker_dates[ticker] = set()
        ticker_dates[ticker].add(date_str)
        
    conn.close()
    
    tickets_list = list(ticker_dates.keys())
    
    if not tickets_list:
        return {}
        
    print(f"Fetching live data for: {tickets_list}")
    results = {}
    
    try:
        # Fetch data (2y for ample history)
        # Use safe_yf_download with threads=True for batch performance
        data = market_data.safe_yf_download(tickets_list, period="2y", threads=True)
        
        for ticker in tickets_list:
            try:
                # Handle different dataframe structures
                if len(tickets_list) == 1:
                    df = data
                else:
                    if isinstance(data.columns, pd.MultiIndex):
                        try:
                            if ticker in data.columns.get_level_values(1):
                                df = data.xs(ticker, axis=1, level=1)
                            else:
                                df = data.xs(ticker, axis=1, level=0)
                        except KeyError:
                            # Fallback if xs fails
                            df = data.loc[:, (slice(None), ticker)]
                            if not df.empty:
                                df.columns = df.columns.get_level_values(0)
                            else:
                                df = data
                    else:
                        df = data
                
                if df.empty:
                    continue
                    
                # Calculate EMAs and Stats
                close = df['Close']
                low = df['Low']
                
                ema_8_series = close.ewm(span=8, adjust=False).mean()
                ema_21_series = close.ewm(span=21, adjust=False).mean()
                ema_35_series = close.ewm(span=35, adjust=False).mean()
                ema_200_series = close.ewm(span=200, adjust=False).mean()

                if pd.isna(close.iloc[-1]):
                    # Skip descriptors with no recent data (e.g. delisted)
                    continue

                last_price = float(close.iloc[-1])
                prev_price = float(close.iloc[-2]) if len(close) > 1 else last_price
                day_change_pct = ((last_price - prev_price) / prev_price) * 100
                
                # Calculate Violation Counts for EACH unique entry date
                violation_map = {}
                
                for date_str in ticker_dates[ticker]:
                    if not date_str: continue
                    
                    try:
                        entry_ts = pd.Timestamp(date_str)
                        mask = df.index >= entry_ts
                        df_slice = df[mask]
                        
                        if not df_slice.empty:
                            # Calculate Crossunders (Price crosses BELOW EMA)
                            # Current Close < EMA AND Previous Close >= EMA
                            # We need previous day's data, so we use the aligned series
                            # To do this vectorised:
                            # 1. Get boolean series: Below = Close < EMA
                            # 2. Shift it: Prev_Below = Below.shift(1)
                            # 3. Crossunder = Below & (~Prev_Below)
                            
                            # Note: df_slice might start mid-trend. 
                            # If the first day is below, we count it as 1 violation? 
                            # Or strictly crosses? User said "perdió", implies the event. 
                            # Let's count strictly crosses + if first day is already below?
                            # Safest is strictly crosses. If entered and immediately below, it's 1.
                            
                            # We need the series matching df_slice
                            c_slice = close[mask]
                            
                            def count_crossunders(price_s, ema_s):
                                is_below = price_s < ema_s
                                # Shift filled with False (assume started above) or use actual history?
                                # Using actual history (df) is better, but mask slices it.
                                # Better to calc on FULL df then slice.
                                
                                # Calc full boolean series
                                full_below = close < ema_s
                                # Shift
                                full_prev_below = full_below.shift(1).fillna(False) # Assume start is not below
                                # Crossunder
                                full_cross = full_below & (~full_prev_below)
                                # Slice by date
                                return full_cross[mask].sum()

                            v8 = count_crossunders(close, ema_8_series)
                            v21 = count_crossunders(close, ema_21_series)
                            v35 = count_crossunders(close, ema_35_series)
                            v200 = count_crossunders(close, ema_200_series)

                            violation_map[date_str] = {
                                'ema_8': int(v8),
                                'ema_21': int(v21),
                                'ema_35': int(v35),
                                'ema_200': int(v200)
                            }
                        else:
                            violation_map[date_str] = {}
                    
                    except Exception as e:
                        # print(f"Error processing date {date_str} for {ticker}: {e}")
                        violation_map[date_str] = {}

                # Weekly RSI
                rsi_summary = None
                try:
                    rsi_data = indicators.calculate_weekly_rsi_analytics(df)
                    if rsi_data:
                        rsi_summary = {
                            "val": round(rsi_data['rsi'], 2),
                            "sma3": round(rsi_data['sma3'], 2),
                            "sma14": round(rsi_data['sma14'], 2),
                            "bullish": rsi_data['sma3'] > rsi_data['sma14']
                        }
                except Exception as e:
                    print(f"Error calc RSI for {ticker}: {e}")

                results[ticker] = {
                    'price': round(last_price, 2),
                    'change_pct': round(day_change_pct, 2),
                    'ema_8': round(float(ema_8_series.iloc[-1]), 2),
                    'ema_21': round(float(ema_21_series.iloc[-1]), 2),
                    'ema_35': round(float(ema_35_series.iloc[-1]), 2),
                    'ema_200': round(float(ema_200_series.iloc[-1]), 2),
                    'violations_map': violation_map,
                    'rsi_weekly': rsi_summary
                }
                
            except Exception as e:
                print(f"Error processing {ticker}: {e}")
                continue
                
    except Exception as e:
        print(f"Error downloading data: {e}")
        
    # Helper to clean NaNs for JSON
    import math
    def clean_nan(obj):
        if isinstance(obj, float):
            return None if math.isnan(obj) or math.isinf(obj) else obj
        if isinstance(obj, dict):
            return {k: clean_nan(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [clean_nan(i) for i in obj]
        return obj
        
    return clean_nan(results)

@router.get("/api/trades/analytics/open")
def get_open_trades_analytics():
    """
    Get aggregate risk/exposure analytics for OPEN trades and generate Actionable Insights.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Fetch all open trades
        cursor.execute("SELECT * FROM trades WHERE status = 'OPEN'")
        rows = cursor.fetchall()
        # Note: conn stays open for later queries
        
        if not rows:
            return {
                "exposure": {"total_invested": 0, "total_risk_r": 0, "unrealized_pnl": 0, "active_count": 0},
                "suggestions": []
            }
            
        trades = [dict(row) for row in rows]
        tickers = list(set(t['ticker'] for t in trades if t['ticker']))
        
        # 1. Fetch Fundamental Data (CACHE-FIRST STRATEGY)
        fundamental_data = {}
        fetched_market_data = {}
        today = datetime.now().strftime('%Y-%m-%d')
        
        if tickers:
            # 1a. Load from cache first (INSTANT!)
            conn_cache = sqlite3.connect(DB_PATH)
            conn_cache.row_factory = sqlite3.Row
            cursor_cache = conn_cache.cursor()
            
            placeholders = ','.join('?' * len(tickers))
            cursor_cache.execute(f"""
                SELECT * FROM fundamentals_cache 
                WHERE ticker IN ({placeholders})
                AND datetime(last_updated) > datetime('now', '-1 hour')
            """, tickers)
            
            cached_rows = cursor_cache.fetchall()
            for row in cached_rows:
                fundamental_data[row['ticker']] = {
                    "beta": row['beta'],
                    "pe_ratio": row['pe_ratio'],
                    "dividend_yield": row['dividend_yield'],
                    "dividend_rate": row['dividend_rate'],
                    "ex_dividend_date": row['ex_dividend_date'],
                    "asset_type": row['asset_type'] or 'EQUITY',
                    "short_name": row['short_name'] or row['ticker']
                }
            
            conn_cache.close()
            
            # 1b. Identify missing/stale tickers
            cached_tickers = set(fundamental_data.keys())
            missing_tickers = [t for t in tickers if t not in cached_tickers]
            
            # 1c. Fetch missing tickers SYNCHRONOUSLY (with timeout) so data appears on first load
            if missing_tickers:
                from concurrent.futures import ThreadPoolExecutor, TimeoutError
                
                def fetch_ticker_info(ticker):
                    try:
                        info = yf.Ticker(ticker).info
                        return ticker, {
                            "beta": info.get('beta'),
                            "pe_ratio": info.get('trailingPE') or info.get('forwardPE'),
                            "dividend_yield": info.get('trailingAnnualDividendYield'),
                            "dividend_rate": info.get('trailingAnnualDividendRate'),
                            "ex_dividend_date": info.get('exDividendDate'),
                            "asset_type": info.get('quoteType', 'EQUITY'),
                            "short_name": info.get('shortName', ticker)
                        }
                    except:
                        return ticker, {"asset_type": "EQUITY", "short_name": ticker}
                
                # Fetch up to 10 tickers synchronously (with 5s timeout each)
                tickers_to_fetch_sync = missing_tickers[:10]
                print(f"[Analytics] Fetching fundamentals for {len(tickers_to_fetch_sync)} tickers...")
                
                try:
                    with ThreadPoolExecutor(max_workers=5) as executor:
                        futures = {executor.submit(fetch_ticker_info, t): t for t in tickers_to_fetch_sync}
                        
                        conn_fund = sqlite3.connect(DB_PATH)
                        cursor_fund = conn_fund.cursor()
                        
                        for future in futures:
                            try:
                                ticker, data = future.result(timeout=5)
                                fundamental_data[ticker] = data  # USE IT IN THIS REQUEST!
                                
                                # Also cache for future requests
                                cursor_fund.execute("""
                                    INSERT OR REPLACE INTO fundamentals_cache 
                                    (ticker, beta, pe_ratio, dividend_yield, dividend_rate, ex_dividend_date, asset_type, short_name, last_updated)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                                """, (
                                    ticker,
                                    data.get('beta'),
                                    data.get('pe_ratio'),
                                    data.get('dividend_yield'),
                                    data.get('dividend_rate'),
                                    data.get('ex_dividend_date'),
                                    data.get('asset_type'),
                                    data.get('short_name')
                                ))
                            except TimeoutError:
                                fundamental_data[ticker] = {"asset_type": "EQUITY", "short_name": ticker}
                            except:
                                pass
                        
                        conn_fund.commit()
                        conn_fund.close()
                        print(f"[Analytics] Fundamentals loaded for {len([f for f in fundamental_data.values() if f.get('beta')])} tickers with beta")
                except Exception as e:
                    print(f"[Analytics] Fundamentals fetch error: {e}")
                    for t in missing_tickers:
                        fundamental_data[t] = {"asset_type": "EQUITY", "short_name": t}
            
            # 1d. Price Data - SYNC FETCH for immediate suggestions display
            print(f"[Analytics] Fetching price data for {len(tickers)} tickers...")
            try:
                data = market_data.safe_yf_download(tickers, period="3mo", interval="1d", threads=True)
                
                for t in tickers:
                    try:
                        if isinstance(data.columns, pd.MultiIndex):
                            try: df = data.xs(t, axis=1, level=1)
                            except: df = data.xs(t, axis=1, level=0)
                        else:
                            df = data if len(tickers) == 1 else pd.DataFrame()
                        if not df.empty and 'Close' in df.columns:
                            fetched_market_data[t] = df
                    except: pass
                        
                print(f"[Analytics] Price data loaded for {len(fetched_market_data)} tickers")
            except Exception as e:
                print(f"[Analytics] Price fetch error: {e}")

        # Metrics
        total_invested = 0.0
        total_risk_amt = 0.0 # Dollar risk
        unrealized_pnl = 0.0
        suggestions = []
        
        # Aggregates for new dashboard
        weighted_beta_sum = 0.0
        weighted_pe_sum = 0.0
        pe_weight_total = 0.0
        total_div_payment = 0.0
        
        asset_allocation_map = {
            "Stocks": 0.0,
            "Cryptocurrency": 0.0,
            "ETFs": 0.0,
            "Cash/Other": 0.0
        }
        
        holdings_list = [] # For Major Holdings table
        upcoming_dividends = []
        
        for trade in trades:
            t = trade['ticker']
            qty = trade['shares'] or 0
            entry = trade['entry_price'] or 0
            stop = trade['stop_loss'] or 0
            
            # 1. Exposure
            trade_value = (entry * qty)
            total_invested += trade_value
            
            # Fundamentals
            fund = fundamental_data.get(t, {})
            beta = fund.get('beta')
            pe = fund.get('pe_ratio')
            div_yield = fund.get('dividend_yield')
            div_rate = fund.get('dividend_rate')
            asset_type = fund.get('asset_type', 'EQUITY')
            
            # Weighted Beta
            if beta:
                weighted_beta_sum += (beta * trade_value)
                
            # Weighted PE (only if positive)
            if pe and pe > 0:
                weighted_pe_sum += (pe * trade_value)
                pe_weight_total += trade_value
                
            # Dividends
            if div_rate:
                total_div_payment += (div_rate * qty)
            if fund.get('ex_dividend_date'):
                try:
                    ex_date = datetime.fromtimestamp(fund['ex_dividend_date']).strftime('%Y-%m-%d')
                    if ex_date >= today:
                        upcoming_dividends.append({
                            "ticker": t,
                            "name": fund.get('short_name', t),
                            "ex_date": ex_date
                        })
                except: pass

            # Asset Allocation Mapping
            if asset_type == 'EQUITY':
                asset_allocation_map["Stocks"] += trade_value
            elif asset_type == 'CRYPTO':
                asset_allocation_map["Cryptocurrency"] += trade_value
            elif asset_type == 'ETF':
                asset_allocation_map["ETFs"] += trade_value
            else:
                asset_allocation_map["Cash/Other"] += trade_value

            # 2. Risk (Entry - Stop) * Qty
            risk_per_share = entry - stop
            if risk_per_share > 0:
                total_risk_amt += (risk_per_share * qty)
                
            # 3. Unrealized PnL & Insights
            current_price = entry # Default
            if t in fetched_market_data:
                df = fetched_market_data[t]
                close_series = df['Close']
                
                if not pd.isna(close_series.iloc[-1]):
                    current_price = float(close_series.iloc[-1])
                    unrealized_pnl += (current_price - entry) * qty
                    
                    # --- ACTIONABLE INSIGHTS ---
                    ema8 = float(close_series.ewm(span=8, adjust=False).mean().iloc[-1])
                    ema21 = float(close_series.ewm(span=21, adjust=False).mean().iloc[-1])
                    
                    if 'Volume' in df.columns:
                        vol_series = df['Volume']
                        curr_vol = float(vol_series.iloc[-1])
                        avg_vol = float(vol_series.rolling(window=20).mean().iloc[-1])
                        r_vol = curr_vol / avg_vol if avg_vol > 0 else 0
                    else:
                        r_vol = 0
                    
                    weekly_rsi_data = indicators.calculate_weekly_rsi_analytics(df)
                    current_r = (current_price - entry) / risk_per_share if risk_per_share > 0 else 0
                    
                    if current_price > ema8 and current_r > 1.0 and r_vol > 1.2:
                        suggestions.append({
                            "ticker": t, "action": "ADD", "type": "bullish",
                            "reason": f"High Appetite (RVol {r_vol:.1f}x) + Trend Strength",
                            "date": today
                        })
                    if current_price < ema21:
                        suggestions.append({
                            "ticker": t, "action": "TRIM", "type": "bearish",
                            "reason": "Lost EMA21 Trend Support",
                            "date": today
                        })
                    elif weekly_rsi_data and weekly_rsi_data['signal_sell']:
                         suggestions.append({
                            "ticker": t, "action": "TRIM", "type": "bearish",
                            "reason": "Weekly RSI Trend Lost (SMA3 < SMA14)",
                            "date": today
                        })

            # Major Holdings Entry
            holdings_list.append({
                "ticker": t,
                "name": fund.get('short_name', t),
                "value": round(current_price * qty, 2),
                "pct": 0, # Calc later
                "beta": beta,
                "pe": pe,
                "yield": round((div_yield or 0) * 100, 2) if div_yield else 0
            })
                
        # Finalized Metrics
        portfolio_beta = weighted_beta_sum / total_invested if total_invested > 0 else 0
        portfolio_pe = weighted_pe_sum / pe_weight_total if pe_weight_total > 0 else 0
        portfolio_div_yield = (total_div_payment / total_invested) * 100 if total_invested > 0 else 0

        # Calculate PCT for holdings
        current_total_value = sum(h['value'] for h in holdings_list)
        for h in holdings_list:
            if current_total_value > 0:
                h['pct'] = round((h['value'] / current_total_value) * 100, 2)
        
        holdings_list.sort(key=lambda x: x['value'], reverse=True)

        # 4. Period P&L (Realized)
        today_str = datetime.now().strftime('%Y-%m-%d')
        this_week = datetime.now().isocalendar()[1]
        this_year = datetime.now().year
        
        cursor.execute("SELECT pnl, exit_date FROM trades WHERE status = 'CLOSED'")
        closed_trades = cursor.fetchall()
        
        daily_pnl = 0.0
        weekly_pnl = 0.0
        yearly_pnl = 0.0
        all_time_pnl = 0.0
        
        for pnl, exit_date in closed_trades:
            all_time_pnl += (pnl or 0.0)
            if not exit_date: continue
            try:
                dt = datetime.strptime(exit_date, '%Y-%m-%d')
                if exit_date == today_str: daily_pnl += pnl
                if dt.year == this_year and dt.isocalendar()[1] == this_week: weekly_pnl += pnl
                if dt.year == this_year: yearly_pnl += pnl
            except: pass

        # 5. Sector Allocation
        sector_map = {}
        for trade in trades:
            ticker = trade['ticker']
            qty = trade['shares'] or 0
            price = fundamental_data.get(ticker, {}).get('price', (trade['entry_price'] or 0)) # Try use live if we had it easily
            # Just use entry for weight in allocation to be stable
            amt = (trade['entry_price'] or 0) * qty
            sector = market_data.get_ticker_sector(ticker)
            sector_map[sector] = sector_map.get(sector, 0) + amt
            
        sector_allocation = [{"sector": k, "value": round(v, 2)} for k, v in sector_map.items()]
        sector_allocation.sort(key=lambda x: x['value'], reverse=True)

        return {
            "exposure": {
                "total_invested": round(total_invested, 2),
                "total_risk_dollars": round(total_risk_amt, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "active_count": len(trades),
                "realized_pnl_daily": round(daily_pnl, 2),
                "realized_pnl_weekly": round(weekly_pnl, 2),
                "realized_pnl_yearly": round(yearly_pnl, 2),
                "realized_pnl_all_time": round(all_time_pnl, 2),
                
                # New Advanced Metrics
                "portfolio_beta": round(portfolio_beta, 2),
                "portfolio_pe": round(portfolio_pe, 1),
                "portfolio_div_yield": round(portfolio_div_yield, 2),
                "total_div_payment": round(total_div_payment, 2)
            },
            "asset_allocation": [{"type": k, "value": round(v, 2)} for k, v in asset_allocation_map.items() if v > 0],
            "sector_allocation": sector_allocation,
            "holdings": holdings_list[:10], # Top 10
            "upcoming_dividends": sorted(upcoming_dividends, key=lambda x: x['ex_date'])[:5],
            "suggestions": suggestions
        }
        
        conn.close()  # Close connection before returning
        return result
    except Exception as e:
        print(f"CRITICAL ERROR in analytics: {e}")
        import traceback
        traceback.print_exc()
        # Return empty safe response
        return {
            "exposure": {"total_invested": 0, "total_risk_dollars": 0, "unrealized_pnl": 0, "active_count": 0},
            "suggestions": []
        }


@router.get("/api/trades/template")
async def get_template():
    """Download a CSV template for importing trades"""
    csv_content = "Ticker,Fecha compra,PPC,Cantidad Compra\nAAPL,2023-01-15,150.00,10"
    return Response(content=csv_content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=trade_template.csv"})

@router.post("/api/trades/import")
async def import_trades(file: UploadFile = File(...)):
    """Import trades from CSV (Active Positions format)"""
    try:
        content = await file.read()
        # Try reading with comma first
        try:
            df = pd.read_csv(io.BytesIO(content))
        except:
             # Fallback just in case
             df = pd.DataFrame()

        required_cols = ['Ticker', 'Fecha compra', 'PPC', 'Cantidad Compra']
        
        # Smart Check: If required cols missing, try semicolon
        if not all(col in df.columns for col in required_cols):
             # Rewind and try semicolon
             df = pd.read_csv(io.BytesIO(content), sep=';')
             
        if not all(col in df.columns for col in required_cols):
             return JSONResponse(status_code=400, content={
                 "error": f"Missing columns.\nExpected: {required_cols}\nFound: {list(df.columns)}\n\nTip: Use the 'Download Template' button."
             })

        success_count = 0
        errors = []

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        for index, row in df.iterrows():
            try:
                # Parse Date
                raw_date = str(row['Fecha compra'])
                # Try specific formats or let pandas infer, but we need YYYY-MM-DD
                try:
                    ts = pd.to_datetime(raw_date)
                    date_str = ts.strftime('%Y-%m-%d')
                except:
                    date_str = raw_date # Fallback

                # Helper to sanitize currency strings (e.g. "$10,35" -> 10.35)
                def clean_float(val):
                    if pd.isna(val): return 0.0
                    s = str(val).replace('$', '').replace(' ', '')
                    # If common European format like 1.000,00 -> remove dot, replace comma
                    # But if simple 10,35 -> just replace comma
                    if ',' in s and '.' in s:
                        # Ambiguous or thousands separator. Assumption: dot is thousands, comma is decimal if both present
                        s = s.replace('.', '').replace(',', '.')
                    elif ',' in s:
                        s = s.replace(',', '.')
                    return float(s)

                trade_data = TradeCreate(
                    ticker=str(row['Ticker']).upper().strip(),
                    entry_date=date_str,
                    entry_price=clean_float(row['PPC']),
                    shares=clean_float(row['Cantidad Compra']),
                    action='BUY', # Default to BUY for this format
                    strategy='Imported',
                    notes=f"Imported from CSV row {index+1}"
                )
                
                # Re-use the logic from add_trade directly to ensure safety
                # But since add_trade function is not isolated from the route, we'll reimplement the DB insert logic strictly for BUYS here
                # Or refactor? Re-implementing insert for BUY is simple enough and avoids dependency mess
                
                # Basic Validation
                if trade_data.shares <= 0 or trade_data.entry_price < 0:
                   raise ValueError("Shares/Price must be positive")

                cursor.execute("""
                    INSERT INTO trades (
                        created_at, ticker, entry_price, shares, status, 
                        stop_loss, target, target2, target3, 
                        strategy, notes, direction, entry_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # Created At
                    trade_data.ticker,
                    trade_data.entry_price,
                    trade_data.shares,
                    'OPEN', # Always OPEN for new imports
                    0, 0, 0, 0, # Defaults
                    trade_data.strategy,
                    trade_data.notes,
                    'LONG', # Assume Long
                    trade_data.entry_date
                ))
                success_count += 1

            except Exception as e:
                errors.append(f"Row {index+1}: {str(e)}")
        
        conn.commit()
        conn.close()
        
        return {
            "message": f"Successfully imported {success_count} trades.",
            "errors": errors
        }


    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})


class SplitAdjustment(BaseModel):
    ticker: str
    split_ratio: float  # For 1:10 reverse split use 0.1, for 10:1 forward use 10
    apply_to_date: Optional[str] = None  # Only adjust trades before this date


@router.post("/api/trades/apply-split")
def apply_split(req: SplitAdjustment):
    """
    Apply stock split adjustment to all positions of a ticker.
    
    For reverse split 1:10 (ratio=0.1):
      - shares *= 0.1 (100 → 10)
      - prices /= 0.1 (prices *= 10, so $5 → $50)
    
    For forward split 10:1 (ratio=10):
      - shares *= 10 (10 → 100)
      - prices /= 10 ($50 → $5)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Build query with optional date filter
        query = "SELECT id, shares, entry_price, exit_price, stop_loss, target, target2, target3 FROM trades WHERE ticker = ?"
        params = [req.ticker]
        
        if req.apply_to_date:
            query += " AND entry_date < ?"
            params.append(req.apply_to_date)
        
        cursor.execute(query, params)
        trades = cursor.fetchall()
        
        if not trades:
            return {"message": f"No trades found for {req.ticker}", "adjusted_count": 0}
        
        adjusted_count = 0
        for trade in trades:
            trade_id, shares, entry_price, exit_price, stop_loss, target, target2, target3 = trade
            
            # Apply split ratio
            new_shares = int(shares * req.split_ratio)
            new_entry = entry_price / req.split_ratio if entry_price else None
            new_exit = exit_price / req.split_ratio if exit_price else None
            new_sl = stop_loss / req.split_ratio if stop_loss else None
            new_t1 = target / req.split_ratio if target else None
            new_t2 = target2 / req.split_ratio if target2 else None
            new_t3 = target3 / req.split_ratio if target3 else None
            
            # Update trade
            cursor.execute("""
                UPDATE trades 
                SET shares = ?, entry_price = ?, exit_price = ?, 
                    stop_loss = ?, target = ?, target2 = ?, target3 = ?
                WHERE id = ?
            """, (new_shares, new_entry, new_exit, new_sl, new_t1, new_t2, new_t3, trade_id))
            
            adjusted_count += 1
        
        conn.commit()
        conn.close()
        
        return {
            "message": f"Successfully adjusted {adjusted_count} trades for {req.ticker}",
            "adjusted_count": adjusted_count,
            "split_ratio": req.split_ratio
        }
    
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- DAILY SNAPSHOT SYSTEM ---

def capture_daily_snapshot():
    """
    Capture a snapshot of the current portfolio state.
    Calculates Unrealized PnL and Cumulative Realized PnL.
    Only records on market days.
    """
    try:
        import market_data
        session = market_data.get_market_session()
        
        # Skip weekend recordings
        if session == "WEEKEND":
            # print("[Snapshot] Skipping - Market is closed (Weekend)")
            return False

        # 1. Get Analytics (Open Positions)
        # We reuse the logic but call it programmatically
        analytics = get_open_trades_analytics()
        
        # 2. Get Realized PnL (Closed Trades)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(pnl) FROM trades WHERE status = 'CLOSED'")
        realized_pnl = cursor.fetchone()[0] or 0.0
        
        exposure = analytics.get('exposure', {})
        total_invested = exposure.get('total_invested', 0.0)
        unrealized_pnl = exposure.get('unrealized_pnl', 0.0)
        active_count = exposure.get('active_count', 0)
        
        # Total Equity = Basis (Total Invested) + Total PnL (Realized + Unrealized)
        # Note: If we don't track cash, we track Relative Equity (PnL relative to entry cost)
        total_equity = total_invested + unrealized_pnl + realized_pnl
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute("""
            INSERT OR REPLACE INTO portfolio_snapshots 
            (snapshot_date, total_invested, unrealized_pnl, realized_pnl, total_equity, active_positions)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (today, total_invested, unrealized_pnl, realized_pnl, total_equity, active_count))
        
        conn.commit()
        conn.close()
        print(f"[Snapshot] Recorded for {today}: Equity ${total_equity:.2f}")
        return True
    except Exception as e:
        print(f"Error capturing snapshot: {e}")
        traceback.print_exc()
        return False

@router.get("/api/trades/analytics/performance")
def get_portfolio_performance():
    """
    Detailed performance analysis vs SPY benchmark.
    Returns data for both Line (daily) and Bar (monthly) comparison.
    """
    try:
        # 1. Get earliest trade date
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT MIN(entry_date) FROM trades")
        start_date = cursor.fetchone()[0]
        
        if not start_date:
            conn.close()
            return {"error": "No trades found in journal"}
            
        # 2. Get all snapshots
        cursor.execute("SELECT snapshot_date, total_equity, total_invested FROM portfolio_snapshots ORDER BY snapshot_date ASC")
        snapshots = cursor.fetchall()
        
        # 3. Get Realized PnL history for reconstruction if snapshots are missing
        cursor.execute("SELECT exit_date, SUM(pnl) FROM trades WHERE status='CLOSED' GROUP BY exit_date ORDER BY exit_date")
        realized_history = {row[0]: row[1] for row in cursor.fetchall() if row[0]}
        
        conn.close()
        
        # 4. Fetch SPY Data
        spy = yf.download("SPY", start=start_date, progress=False)
        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = [c[0] for c in spy.columns]
        
        # Benchmark baseline
        spy_initial = spy['Close'].iloc[0]
        spy_perf = ((spy['Close'] - spy_initial) / spy_initial) * 100
        
        # 5. Build Unified Time Series
        # Since snapshots might be sparse, we align to market days
        dates = [d.strftime('%Y-%m-%d') for d in spy.index]
        spy_values = [round(v, 2) for v in spy_perf.values]
        
        # Portfolio Performance Calculation:
        # We use a Relative Growth % based on snapshots if available, 
        # or fallback to realized PnL vs an estimated capital base.
        # For simplicity in this env, we'll map existing snapshots.
        snapshot_map = {row[0]: row[1] for row in snapshots}
        
        # Baseline equity (First snapshot or estimate)
        initial_equity = snapshots[0][1] if snapshots else 10000 
        
        portfolio_values = []
        current_equity = initial_equity
        
        for d_str in dates:
            if d_str in snapshot_map:
                current_equity = snapshot_map[d_str]
            # Cumulative % growth
            pct = ((current_equity - initial_equity) / initial_equity) * 100
            portfolio_values.append(round(pct, 2))
            
        # 6. Periodic Comparison (Monthly Bars)
        # Using pandas for resample
        spy_returns = spy['Close'].resample('ME').last().pct_change().dropna() * 100
        
        # For portfolio monthly, we use snapshots
        snap_df = pd.DataFrame(snapshots, columns=['date', 'equity', 'invested'])
        snap_df['date'] = pd.to_datetime(snap_df['date'])
        snap_df.set_index('date', inplace=True)
        port_returns = snap_df['equity'].resample('ME').last().pct_change().dropna() * 100
        
        monthly_comp = []
        for d in spy_returns.index:
            month_label = d.strftime('%b %y')
            monthly_comp.append({
                "month": month_label,
                "spy": round(spy_returns.get(d, 0), 2),
                "portfolio": round(port_returns.get(d, 0), 2)
            })

        return {
            "line_data": {
                "dates": dates,
                "portfolio": portfolio_values,
                "spy": spy_values
            },
            "monthly_data": monthly_comp,
            "period_start": start_date
        }
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/api/trades/snapshots")
def get_snapshots(days: int = 30):
    """Serve historical portfolio snapshots for charting"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM portfolio_snapshots 
            ORDER BY snapshot_date ASC 
            LIMIT ?
        """, (days,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# UNIFIED PORTFOLIO (USA + Argentina)
# ============================================

@router.get("/api/trades/unified/positions")
def get_unified_positions(market: str = "all"):
    """
    Get unified positions from both USA and Argentina markets.
    market: 'all', 'usa', 'argentina'
    Returns positions normalized to USD (Argentina uses CCL rate).
    """
    import argentina_data
    import argentina_journal
    
    positions = []
    rates = argentina_data.get_dolar_rates()
    ccl = rates.get("ccl", 1200)
    
    # Get USA positions
    if market in ["all", "usa"]:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, ticker, entry_date, entry_price, shares, strategy, 
                   stop_loss, target, target2, target3, notes, status
            FROM trades WHERE status = 'open'
        """)
        usa_trades = cursor.fetchall()
        conn.close()
        
        for t in usa_trades:
            positions.append({
                "id": t["id"],
                "ticker": t["ticker"],
                "market": "USA",
                "entry_date": t["entry_date"],
                "entry_price_local": t["entry_price"],
                "entry_price_usd": t["entry_price"],
                "shares": t["shares"],
                "cost_usd": t["entry_price"] * t["shares"],
                "stop_loss": t["stop_loss"],
                "target": t["target"],
                "target2": t.get("target2"),
                "target3": t.get("target3"),
                "strategy": t["strategy"],
                "notes": t["notes"],
                "currency": "USD"
            })
    
    # Get Argentina positions
    if market in ["all", "argentina"]:
        arg_positions = argentina_journal.get_all_positions("open")
        
        for p in arg_positions:
            entry_usd = p["entry_price"] / ccl if ccl > 0 else 0
            positions.append({
                "id": f"ARG-{p['id']}",
                "ticker": p["ticker"],
                "market": "ARG",
                "asset_type": p.get("asset_type", "stock"),
                "entry_date": p["entry_date"],
                "entry_price_local": p["entry_price"],
                "entry_price_usd": round(entry_usd, 2),
                "shares": p["shares"],
                "cost_usd": round(entry_usd * p["shares"], 2),
                "stop_loss": p.get("stop_loss"),
                "target": p.get("target"),
                "strategy": p.get("strategy"),
                "notes": p.get("notes"),
                "currency": "ARS"
            })
    
    return {
        "positions": positions,
        "count": len(positions),
        "rates": {"ccl": ccl, "mep": rates.get("mep", 1150)}
    }


@router.get("/api/trades/unified/metrics")
def get_unified_metrics(market: str = "all"):
    """
    Get unified portfolio metrics for Total/USA/ARGY view.
    Returns values in multiple currencies (USD, ARS via CCL/MEP/Oficial).
    """
    import argentina_data
    import argentina_journal
    
    rates = argentina_data.get_dolar_rates()
    ccl = rates.get("ccl", 1200)
    mep = rates.get("mep", 1150)
    oficial = rates.get("oficial", 1050)
    
    # Initialize totals
    usa_invested_usd = 0.0
    usa_current_usd = 0.0
    usa_pnl_usd = 0.0
    usa_count = 0
    
    arg_invested_ars = 0.0
    arg_current_ars = 0.0
    arg_pnl_ars = 0.0
    arg_count = 0
    
    # USA Metrics (already in USD)
    # USA Metrics (already in USD)
    if market in ["all", "usa"]:
        import market_data
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. Open Positions: Calculate Unrealized P&L
        cursor.execute("SELECT ticker, entry_price, shares FROM trades WHERE UPPER(status) = 'OPEN'")
        open_trades = cursor.fetchall()
        
        tickers = [t["ticker"] for t in open_trades]
        live_prices = market_data.get_batch_latest_prices(tickers)
        
        for t in open_trades:
            invested = t["entry_price"] * t["shares"]
            usa_invested_usd += invested
            usa_count += 1
            
            # Calculate current value
            current_price = live_prices.get(t["ticker"], t["entry_price"])
            current_val = current_price * t["shares"]
            usa_current_usd += current_val
            
            # Unrealized P&L
            usa_pnl_usd += (current_val - invested)

        # 2. Closed Positions: Add Realized P&L
        cursor.execute("SELECT SUM(pnl) as realized_pnl FROM trades WHERE UPPER(status) = 'CLOSED'")
        row = cursor.fetchone()
        if row and row["realized_pnl"]:
            usa_pnl_usd += row["realized_pnl"]
            
        conn.close()
    
    # Argentina Metrics (in ARS)
    if market in ["all", "argentina"]:
        arg_portfolio = argentina_journal.get_portfolio_valuation()
        arg_count = arg_portfolio.get("position_count", 0)
        
        for h in arg_portfolio.get("holdings", []):
            arg_invested_ars += h.get("cost_basis", 0)
            arg_current_ars += h.get("value_ars", 0)
            arg_pnl_ars += h.get("pnl_ars", 0)
    
    # Convert Argentina to USD using different rates
    arg_invested_ccl = arg_invested_ars / ccl if ccl > 0 else 0
    arg_invested_mep = arg_invested_ars / mep if mep > 0 else 0
    arg_invested_oficial = arg_invested_ars / oficial if oficial > 0 else 0
    
    arg_current_ccl = arg_current_ars / ccl if ccl > 0 else 0
    arg_current_mep = arg_current_ars / mep if mep > 0 else 0
    arg_current_oficial = arg_current_ars / oficial if oficial > 0 else 0
    
    arg_pnl_ccl = arg_pnl_ars / ccl if ccl > 0 else 0
    arg_pnl_mep = arg_pnl_ars / mep if mep > 0 else 0
    arg_pnl_oficial = arg_pnl_ars / oficial if oficial > 0 else 0
    
    # Convert USA to ARS
    usa_invested_ars_ccl = usa_invested_usd * ccl
    usa_invested_ars_mep = usa_invested_usd * mep
    usa_invested_ars_oficial = usa_invested_usd * oficial
    
    # Combined totals in different currencies
    total_count = usa_count + arg_count
    
    return {
        "usa": {
            "invested_usd": round(usa_invested_usd, 2),
            "current_usd": round(usa_current_usd, 2),
            "pnl_usd": round(usa_pnl_usd, 2),
            "invested_ars_ccl": round(usa_invested_ars_ccl, 2),
            "invested_ars_mep": round(usa_invested_ars_mep, 2),
            "invested_ars_oficial": round(usa_invested_ars_oficial, 2),
            "position_count": usa_count
        },
        "argentina": {
            "invested_ars": round(arg_invested_ars, 2),
            "current_ars": round(arg_current_ars, 2),
            "pnl_ars": round(arg_pnl_ars, 2),
            "invested_usd_ccl": round(arg_invested_ccl, 2),
            "invested_usd_mep": round(arg_invested_mep, 2),
            "invested_usd_oficial": round(arg_invested_oficial, 2),
            "current_usd_ccl": round(arg_current_ccl, 2),
            "pnl_usd_ccl": round(arg_pnl_ccl, 2),
            "position_count": arg_count
        },
        "total": {
            "usd_ccl": {
                "invested": round(usa_invested_usd + arg_invested_ccl, 2),
                "current": round(usa_current_usd + arg_current_ccl, 2),
                "pnl": round(usa_pnl_usd + arg_pnl_ccl, 2)
            },
            "usd_mep": {
                "invested": round(usa_invested_usd + arg_invested_mep, 2),
                "current": round(usa_current_usd + arg_current_mep, 2),
                "pnl": round(usa_pnl_usd + arg_pnl_mep, 2)
            },
            "usd_oficial": {
                "invested": round(usa_invested_usd + arg_invested_oficial, 2),
                "current": round(usa_current_usd + arg_current_oficial, 2),
                "pnl": round(usa_pnl_usd + arg_pnl_oficial, 2)
            },
            "ars_ccl": {
                "invested": round(usa_invested_ars_ccl + arg_invested_ars, 2),
                "current": round(usa_invested_ars_ccl + arg_current_ars, 2),
                "pnl": round((usa_pnl_usd * ccl) + arg_pnl_ars, 2)
            },
            "position_count": total_count
        },
        "rates": {
            "ccl": ccl,
            "mep": mep,
            "oficial": oficial
        }
    }
