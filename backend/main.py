from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
import screener
import scoring
import indicators
from cache import get_cache
import elliott
from typing import List, Optional
import concurrent.futures
import yfinance as yf
import pandas as pd
import os
import market_data 
import ai_advisor # New Import

# Import trade journal router
from trade_journal import router as trade_router
import alerts
import asyncio
import asyncio
from datetime import datetime
import socket

app = FastAPI(title="Momentum Screener API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include trade journal routes
app.include_router(trade_router)

# Static files are mounted at the end of the file to ensure API routes take priority


# API Models
class ScanRequest(BaseModel):
    limit: int = 20000 
    strategy: str = "rally_3m" # rally_3m, weekly_rsi

class AnalyzeRequest(BaseModel):
    ticker: str

import time
import random

def process_ticker(ticker, use_cache=True, strategy="rally_3m"):
    """Process a single ticker with optional caching"""
    cache = get_cache() if use_cache else None
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Try to get from cache first
            df = None
            if cache:
                df = cache.get(ticker, screener.PERIOD, screener.INTERVAL)
                if df is not None:
                    # Cache hit!
                    pass  # Use cached data
            
            # If not in cache, download
            if df is None:
                # Determine period based on strategy
                period = screener.PERIOD
                if strategy == "weekly_rsi":
                    period = "1y" # Need more history for Weekly RSI

                # Use auto_adjust=False as verified in Colab to match results
                # CRITICAL: threads=False prevents yfinance from grouping multiple ticker downloads
                df = yf.download(ticker, period=period, interval=screener.INTERVAL, 
                               progress=False, auto_adjust=False, threads=False)
                
                # Save to cache
                if cache and df is not None and not df.empty:
                    cache.set(ticker, screener.PERIOD, screener.INTERVAL, df)
            
            # CRITICAL FIX: If yfinance downloaded multiple tickers at once (MultiIndex columns),
            # extract only THIS ticker's data
            if isinstance(df.columns, pd.MultiIndex):
                # Get all unique ticker symbols in the columns
                ticker_symbols = df.columns.get_level_values(1).unique()
                
                # If this ticker exists in the MultiIndex, extract only its columns
                if ticker in ticker_symbols:
                    df = df.xs(ticker, axis=1, level=1)
                else:
                    # This ticker's data is not in the DataFrame, skip it
                    return None
            
            if strategy == "weekly_rsi":
                result = screener.scan_rsi_crossover(df)
            else:
                result = screener.compute_3m_pattern(df)
            if result:
                result["ticker"] = ticker
                return result
            # If successful but no result (verification failed), just return None
            return None
        except Exception as e:
            # If it's the last attempt, log the error
            if attempt == max_retries - 1:
                print(f"Error processing {ticker} after {max_retries} attempts: {e}")
            else:
                # Wait a bit before retrying (exponential backoff: 1s, 2s, 4s...)
                sleep_time = (2 ** attempt) + random.random()
                time.sleep(sleep_time)
    return None

# API Routes
@app.get("/", include_in_schema=False)
def serve_root():
    """Serve the frontend index.html at root URL"""
    return FileResponse(r"C:\Users\micro\.gemini\antigravity\playground\ancient-glenn\backend\static\index.html")

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/universe")
def get_universe():
    return screener.get_sec_tickers()

@app.post("/api/scan")
def run_scan(req: ScanRequest):
    """Run a market scan (Manual Trigger)"""
    import scan_engine # Lazy import to avoid circular dep early on
    result = scan_engine.run_market_scan(limit=req.limit, strategy=req.strategy)
    if "error" in result:
        return result
    return result

@app.get("/api/scan/progress")
def get_scan_progress():
    """Get current scan progress"""
    import scan_engine
    return scan_engine.get_scan_status()

async def scheduled_reports_loop():
    """Checks time every minute to send scheduled reports AND run automated scans"""
    import scan_engine
    
    last_day_morning = None
    last_day_evening = None
    last_day_scan = None
    
    while True:
        try:
            now = datetime.now()
            current_date = now.date()
            
            # Morning Briefing: 09:00 AM
            if now.hour == 9 and now.minute == 0:
                if last_day_morning != current_date:
                    print(f"[{now}] Sending Morning Briefing...")
                    alerts.send_scheduled_briefing("MORNING")
                    last_day_morning = current_date
            
            # Evening Briefing: 16:15 PM
            if now.hour == 16 and now.minute == 15:
                if last_day_evening != current_date:
                    print(f"[{now}] Sending Evening Briefing...")
                    alerts.send_scheduled_briefing("EVENING")
                    last_day_evening = current_date
                    
            # Post-Market Scan & Watchlist: 16:30 PM
            if now.hour == 16 and now.minute == 30:
                if last_day_scan != current_date:
                    print(f"[{now}] Running Post-Market Automated Scan...")
                    # Run full scan (limit 2000 to cover most liquid names)
                    scan_res = scan_engine.run_market_scan(limit=2000, strategy="rally_3m")
                    if scan_res and "results" in scan_res:
                        top_picks = [r for r in scan_res["results"] if r.get("grade") in ["A", "B"]]
                        if top_picks:
                            # Send Watchlist via Telegram
                            msg = "📋 <b>DAILY WATCHLIST</b>\n\n"
                            for p in top_picks[:10]: # Top 10
                                msg += f"🔹 <b>{p['ticker']}</b> (Grade: {p['grade']})\n"
                                msg += f"   Entry: ~${p.get('entry', 0):.2f}\n"
                            
                            alerts.send_telegram(alerts.get_alert_settings()["telegram_chat_id"], msg)
                    
                    last_day_scan = current_date
                    
        except Exception as e:
            print(f"Error in scheduler: {e}")
            
        await asyncio.sleep(60) # Check every minute

def get_options_sentiment(ticker_symbol):
    try:
        ticker = screener.yf.Ticker(ticker_symbol)
        exps = ticker.options
        if not exps:
            return None
            
        # Get nearest expiration
        chain = ticker.option_chain(exps[0])
        calls = chain.calls
        puts = chain.puts
        
        call_vol = calls['volume'].sum() if 'volume' in calls and not calls.empty else 0
        put_vol = puts['volume'].sum() if 'volume' in puts and not puts.empty else 0
        call_oi = calls['openInterest'].sum() if 'openInterest' in calls and not calls.empty else 0
        put_oi = puts['openInterest'].sum() if 'openInterest' in puts and not puts.empty else 0
        
        return {
            "put_call_vol_ratio": round(put_vol / call_vol, 2) if call_vol > 0 else 0,
            "put_call_oi_ratio": round(put_oi / call_oi, 2) if call_oi > 0 else 0,
            "total_call_vol": int(call_vol),
            "total_put_vol": int(put_vol),
            "total_call_oi": int(call_oi),
            "total_put_oi": int(put_oi),
            "expiration_date": exps[0]
        }
    except Exception as e:
        print(f"Error fetching options for {ticker_symbol}: {e}")
        return None

@app.post("/api/analyze")
def analyze_ticker(req: AnalyzeRequest):
    # Try to analyze bull flag pattern
    result = screener.analyze_bull_flag(req.ticker)
    
    # If no bull flag pattern, create basic result structure
    if not result:
        try:
            print(f"DEBUG: Analyze Fallback for {req.ticker}...")
            df = screener.yf.download(req.ticker, period="12mo", interval="1d", progress=False, auto_adjust=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]
            
            df = df.sort_index().dropna()
            
            if not df.empty:
                print(f"DEBUG: {req.ticker} Last Close: {df['Close'].iloc[-1]}")
            
            if df.empty:
                return {"error": "Could not download data for ticker"}
            
            # Fetch Weekly Data for RSI
            df_weekly = screener.yf.download(req.ticker, period="2y", interval="1wk", progress=False, auto_adjust=False)
            if isinstance(df_weekly.columns, pd.MultiIndex):
                try:
                    df_weekly = df_weekly.xs(req.ticker, level=1, axis=1)
                except:
                    df_weekly.columns = [c[0] for c in df_weekly.columns]
            
            # Remove duplicate columns if any
            df_weekly = df_weekly.loc[:, ~df_weekly.columns.duplicated()]
            
            rsi_weekly_series = None
            if not df_weekly.empty and 'Close' in df_weekly.columns:
                 close_series = df_weekly['Close']
                 if isinstance(close_series, pd.DataFrame):
                     close_series = close_series.iloc[:, 0]
                 
                 df_weekly['RSI'] = indicators.calculate_rsi(close_series)
                 df_weekly['RSI_SMA_3'] = df_weekly['RSI'].rolling(window=3).mean()
                 df_weekly['RSI_SMA_14'] = df_weekly['RSI'].rolling(window=14).mean()
                 df_weekly['RSI_SMA_21'] = df_weekly['RSI'].rolling(window=21).mean()
                 rsi_weekly_series = df_weekly['RSI']

            # Calculate EMAs (like in Journal)
            df['EMA_8'] = df['Close'].ewm(span=8, adjust=False).mean()
            df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
            df['EMA_35'] = df['Close'].ewm(span=35, adjust=False).mean()
            df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()

            # Create basic chart data without bull flag metrics
            chart_data = []
            for idx, row in df.iterrows():
                rsi_val = None
                rsi_sma3 = None
                rsi_sma14 = None
                rsi_sma21 = None
                if not df_weekly.empty:
                    past_weeks = df_weekly[df_weekly.index <= idx]
                    if not past_weeks.empty:
                        week_row = past_weeks.iloc[-1]
                        rsi_val = float(week_row['RSI'])
                        if not pd.isna(week_row['RSI_SMA_3']):
                            rsi_sma3 = float(week_row['RSI_SMA_3'])
                        if not pd.isna(week_row['RSI_SMA_14']):
                            rsi_sma14 = float(week_row['RSI_SMA_14'])
                        if not pd.isna(week_row['RSI_SMA_21']):
                            rsi_sma21 = float(week_row['RSI_SMA_21'])

                data_point = {
                    "date": str(idx.date()),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                    "ema_8": float(row["EMA_8"]) if not pd.isna(row["EMA_8"]) else None,
                    "ema_21": float(row["EMA_21"]) if not pd.isna(row["EMA_21"]) else None,
                    "ema_35": float(row["EMA_35"]) if not pd.isna(row["EMA_35"]) else None,
                    "ema_200": float(row["EMA_200"]) if not pd.isna(row["EMA_200"]) else None,
                }
                if rsi_val is not None and not pd.isna(rsi_val):
                    data_point['rsi_weekly'] = rsi_val
                if rsi_sma3 is not None:
                    data_point['rsi_sma_3'] = rsi_sma3
                if rsi_sma14 is not None:
                    data_point['rsi_sma_14'] = rsi_sma14
                if rsi_sma21 is not None:
                    data_point['rsi_sma_21'] = rsi_sma21
                
                chart_data.append(data_point)
            
            result = {
                "symbol": req.ticker,
                "metrics": {
                    "symbol": req.ticker,  # Add symbol here too for watermark
                    "is_bull_flag": False,  # No bull flag pattern
                    "current_close": float(df['Close'].iloc[-1]),
                    "target": 0,
                    "entry": 0,
                    "stop_loss": 0
                },
                "chart_data": chart_data
            }
        except Exception as e:
            return {"error": f"Could not analyze ticker: {str(e)}"}
    
    # Calculate grade based on screener metrics
    try:
        # Download data for scoring and Elliott
        df = screener.yf.download(req.ticker, period=screener.PERIOD, 
                            interval=screener.INTERVAL, progress=False, auto_adjust=False)
        
        # Handle MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs(req.ticker, axis=1, level=1)
        
        pattern_result = screener.compute_3m_pattern(df)
        if pattern_result:
            score = scoring.calculate_score(pattern_result)
            grade = scoring.score_to_grade(score)
            result["grade"] = grade
            result["score"] = score
        
        # Add Elliott Wave analysis
        if not df.empty:
            elliott_analysis = elliott.analyze_elliott_waves(df)
            result["elliott_wave"] = elliott_analysis
    except Exception as e:
        # If scoring fails, default to showing no grade
        print(f"Error in analysis extras: {e}")
        pass
    
    
    # Common Step: Fetch Options Data
    if result and "metrics" in result:
        result["metrics"]["options_sentiment"] = get_options_sentiment(req.ticker)
    
    return result

@app.get("/api/market-status")
def get_market_status_api():
    return market_data.get_market_status()

import options_scanner # New Import

@app.get("/api/ai-recommendations")
def get_ai_recommendations_api():
    return ai_advisor.get_recommendations()

@app.post("/api/scan-options")
def scan_options_api():
    """Trigger a scan for unusual options activity"""
    return options_scanner.scan_unusual_options()

# Alert System Endpoints
@app.get("/api/alerts/settings")
def get_alert_settings():
    """Get current alert configuration"""
    settings = alerts.get_alert_settings()
    return settings or {"enabled": False, "telegram_chat_id": ""}

@app.post("/api/alerts/settings")
def update_alert_settings(settings: dict):
    """Update alert configuration"""
    import sqlite3
    conn = sqlite3.connect(alerts.DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE alert_settings SET
            telegram_chat_id = ?,
            enabled = ?,
            notify_sl = ?,
            notify_tp = ?,
            notify_rsi_sell = ?,
            sl_warning_pct = ?
        WHERE id = 1
    """, (
        settings.get('telegram_chat_id', ''),
        settings.get('enabled', False),
        settings.get('notify_sl', True),
        settings.get('notify_tp', True),
        settings.get('notify_rsi_sell', True),
        settings.get('sl_warning_pct', 2.0)
    ))
    
    conn.commit()
    conn.close()
    return {"message": "Settings updated"}

@app.post("/api/alerts/test")
def test_alert(chat_id: str = None):
    """Send test alert to verify Telegram configuration"""
    settings = alerts.get_alert_settings()
    test_chat_id = chat_id or (settings.get('telegram_chat_id') if settings else None)
    
    if not test_chat_id:
        return {"error": "No chat_id provided"}
    
    message = "🔔 <b>Test Alert</b>\n\nYour Telegram alerts are configured correctly!"
    success = alerts.send_telegram(test_chat_id, message)
    
    return {"success": success, "message": "Test alert sent" if success else "Failed to send alert"}

# Watchlist Endpoints
import sqlite3

class WatchlistAddRequest(BaseModel):
    ticker: str
    note: str = ""
    hypothesis: str = ""  # New field

@app.get("/api/watchlist")
def get_watchlist_api():
    """Get all watchlist entries with hypothesis"""
    conn = sqlite3.connect('backend/trades.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, note, hypothesis, added_at FROM watchlist ORDER BY added_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{"ticker": r["ticker"], "note": r["note"], "hypothesis": r["hypothesis"], "added_at": r["added_at"]} for r in rows]

@app.post("/api/watchlist")
def add_watchlist_api(req: WatchlistAddRequest):
    """Add ticker to watchlist with optional hypothesis"""
    conn = sqlite3.connect('backend/trades.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO watchlist (ticker, note, hypothesis, added_at) VALUES (?, ?, ?, datetime('now'))",
            (req.ticker.upper(), req.note, req.hypothesis)
        )
        conn.commit()
        success = True
    except Exception as e:
        print(f"Error adding to watchlist: {e}")
        success = False
    finally:
        conn.close()
    return {"success": success}

@app.delete("/api/watchlist/{ticker}")
def delete_watchlist_api(ticker: str):
    """Remove ticker from watchlist"""
    conn = sqlite3.connect('backend/trades.db')
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.upper(),))
        conn.commit()
        success = cursor.rowcount > 0
    except Exception as e:
        print(f"Error removing from watchlist: {e}")
        success = False
    finally:
        conn.close()
    return {"success": success}

@app.get("/api/premarket/{ticker}")
def get_premarket_price(ticker: str):
    """Fetch pre/post market price and change %"""
    try:
        stock = yf.Ticker(ticker)
        # Get regular market price
        info = stock.info
        regular_price = info.get('regularMarketPrice', info.get('currentPrice', 0))
        
        # Try to get pre/post market price
        premarket_price = info.get('preMarketPrice')
        postmarket_price = info.get('postMarketPrice')
        
        # Determine which to use
        extended_price = premarket_price or postmarket_price
        extended_change_pct = None
        
        if extended_price and regular_price:
            extended_change_pct = ((extended_price - regular_price) / regular_price) * 100
        
        return {
            "ticker": ticker.upper(),
            "regular_price": regular_price,
            "extended_price": extended_price,
            "extended_change_pct": round(extended_change_pct, 2) if extended_change_pct else None,
            "is_premarket": premarket_price is not None,
            "is_postmarket": postmarket_price is not None
        }
    except Exception as e:
        print(f"Error fetching premarket for {ticker}: {e}")
        return {"ticker": ticker.upper(), "error": str(e)}

# Background task for alert monitoring
async def alert_monitor_loop():
    """Background task that checks for alerts every 5 minutes"""
    while True:
        try:
            settings = alerts.get_alert_settings()
            if settings and settings.get('enabled'):
                print(f"[{datetime.now()}] Running alert check...")
                alerts.check_price_alerts()
        except Exception as e:
            print(f"Error in alert monitor: {e}")
        
        await asyncio.sleep(300)  # 5 minutes

@app.on_event("startup")
async def start_alert_monitor():
    """Start background alert monitoring on server startup"""
    asyncio.create_task(alert_monitor_loop())
    asyncio.create_task(scheduled_reports_loop())
    print("✅ Alert monitoring started")
    print("✅ Scheduled briefings started")

class BacktestRequest(BaseModel):
    ticker: str
    strategy: str = "momentum_trend"

@app.post("/api/backtest")
def run_backtest_api(req: BacktestRequest):
    """Run a strategy backtest simulation"""
    import backtester
    result = backtester.run_backtest(req.ticker, req.strategy)
    result = backtester.run_backtest(req.ticker, req.strategy)
    return result

@app.get("/api/system/network")
def get_network_info():
    """Detect local LAN IP for remote access"""
    try:
        # Connect to a public DNS to determine the best local interface IP
        # We don't actually send data, just establish the routing
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return {"ip": local_ip, "port": 8000, "url": f"http://{local_ip}:8000"}
    except Exception as e:
        print(f"Error finding local IP: {e}")
        return {"ip": "127.0.0.1", "port": 8000, "url": "http://127.0.0.1:8000", "error": str(e)}

# Remove duplicate scheduled_reports_loop define here if strictly necessary, but actually
# the file showed two definitions (one around line 141, one around line 468).
# I will retain the one at line 141 which has the Scan logic (Post-market).
# So I will DELETE the one at line 468.



# -----------------------------------------------------
# BACKUP ENDPOINTS
# -----------------------------------------------------
try:
    from backend import backup
except ImportError:
    import backup

@app.post("/api/backups/create")
def create_backup_endpoint():
    result = backup.create_backup()
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))
    return result

@app.get("/api/backups/list")
def list_backups_endpoint():
    return backup.list_backups()

@app.post("/api/backups/restore/{filename}")
def restore_backup_endpoint(filename: str):
    # Security check: Basic path traversal prevention
    if ".." in filename or "/" in filename or "\\" in filename:
         raise HTTPException(status_code=400, detail="Invalid filename")
         
    result = backup.restore_backup(filename)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))
    return result


# Mount Static Files (use absolute path to ensure it works regardless of CWD)
static_dir = r"C:\Users\micro\.gemini\antigravity\playground\ancient-glenn\backend\static"
if os.path.exists(static_dir):
    # Mount at /static for backwards compatibility
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    # Mount at root with html=True to serve index.html at /
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static_root")
else:
    print(f"Warning: Static directory not found at {static_dir}")

if __name__ == "__main__":
    # Trigger Reload
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
