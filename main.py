from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
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
import health # Healthcheck module
from database import engine, Base
import models

# Create Tables
Base.metadata.create_all(bind=engine)

# Import trade journal router
import trade_journal
from trade_journal import router as trade_router
import watchlist
from watchlist import router as watchlist_router
import alerts
import asyncio
import asyncio
from datetime import datetime
import socket

# Define Base Directory for relative paths (Crucial for Cloud Deployment)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Momentum Screener API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Anti-cache middleware for development (no more hard refresh needed)
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Disable caching for static files in development
        if request.url.path == "/" or request.url.path.endswith(('.js', '.css', '.html')):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheMiddleware)

# Include trade journal routes
app.include_router(trade_router)

# Include watchlist routes
app.include_router(watchlist_router)

# Include Argentina routes
import argentina_journal
app.include_router(argentina_journal.router)

# Include Crypto routes
import crypto_journal
app.include_router(crypto_journal.router)

# Static files are mounted at the end of the file to ensure API routes take priority


@app.get("/api/health")
def get_health():
    """System health and diagnostics"""
    return health.get_full_health()

# API Models
class ScanRequest(BaseModel):
    limit: int = 20000 
    strategy: str = "weekly_rsi" # rally_3m, weekly_rsi

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
                df = market_data.safe_yf_download(ticker, period=period, interval=screener.INTERVAL, 
                               auto_adjust=False)
                
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
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/universe")
def get_universe():
    return screener.get_sec_tickers()

from fastapi import BackgroundTasks

@app.post("/api/scan")
def run_scan(req: ScanRequest, background_tasks: BackgroundTasks):
    """Run a market scan (Manual Trigger)"""
    import scan_engine # Lazy import to avoid circular dep early on
    
    # Reset status if it was already finished
    if not scan_engine.SCAN_STATUS["is_running"]:
        scan_engine.SCAN_STATUS["current"] = 0
        scan_engine.SCAN_STATUS["total"] = req.limit
        scan_engine.SCAN_STATUS["results"] = []
    
    background_tasks.add_task(scan_engine.run_market_scan, limit=req.limit, strategy=req.strategy)
    return {"status": "scanning", "message": "Scan initiated in background", "limit": req.limit}

@app.get("/api/scan/progress")
def get_scan_progress():
    """Get current scan progress"""
    import scan_engine
    return scan_engine.get_scan_status()

async def scheduled_reports_loop():
    """Checks time every minute to send scheduled reports AND run automated scans"""
    import scan_engine
    
    last_sent = {
        "PRE_MARKET": None,
        "OPEN": None,
        "MID_DAY": None,
        "CLOSE": None,
        "POST_MARKET": None,
        "SCAN": None
    }
    
    while True:
        try:
            now = datetime.now()
            current_date = now.date()
            h, m = now.hour, now.minute
            
            # 08:30 AM - PRE_MARKET
            if h == 8 and m == 30:
                if last_sent["PRE_MARKET"] != current_date:
                    alerts.send_scheduled_briefing("PRE_MARKET")
                    last_sent["PRE_MARKET"] = current_date
            
            # 09:45 AM - OPEN
            if h == 9 and m == 45:
                if last_sent["OPEN"] != current_date:
                    alerts.send_scheduled_briefing("OPEN")
                    last_sent["OPEN"] = current_date
                    
            # 13:00 PM - MID_DAY
            if h == 13 and m == 0:
                if last_sent["MID_DAY"] != current_date:
                    alerts.send_scheduled_briefing("MID_DAY")
                    last_sent["MID_DAY"] = current_date
            
            # 15:50 PM - CLOSE
            if h == 15 and m == 50:
                if last_sent["CLOSE"] != current_date:
                    alerts.send_scheduled_briefing("CLOSE")
                    last_sent["CLOSE"] = current_date
                    
            # 16:30 PM - POST_MARKET & SCAN
            if h == 16 and m == 30:
                if last_sent["POST_MARKET"] != current_date:
                    alerts.send_scheduled_briefing("POST_MARKET")
                    last_sent["POST_MARKET"] = current_date
                
                if last_sent["SCAN"] != current_date:
                    print(f"[{now}] Running Post-Market Automated Scan...")
                    scan_res = scan_engine.run_market_scan(limit=2000, strategy="rally_3m")
                    if scan_res and "results" in scan_res:
                        top_picks = [r for r in scan_res["results"] if r.get("grade") in ["A", "B"]]
                        if top_picks:
                            msg = "📋 <b>DAILY WATCHLIST</b>\n\n"
                            for p in top_picks[:10]:
                                msg += f"🔹 <b>{p['ticker']}</b> (Grade: {p['grade']})\n"
                                msg += f"   Entry: ~${p.get('entry', 0):.2f}\n"
                            alerts.send_telegram(alerts.get_alert_settings()["telegram_chat_id"], msg)
                    last_sent["SCAN"] = current_date
                    
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

            df = market_data.safe_yf_download(req.ticker, period="12mo", interval="1d", auto_adjust=False)
            if isinstance(df.columns, pd.MultiIndex):
                try:
                    if req.ticker in df.columns.get_level_values(1):
                        df = df.xs(req.ticker, axis=1, level=1)
                    else:
                        df = df.xs(req.ticker, axis=1, level=0)
                except:
                    df.columns = [c[0] for c in df.columns]
            
            df = df.sort_index().dropna()
            
            
            if df.empty:
                return {"error": "Could not download data for ticker"}
            
            # Fetch Weekly Data for RSI
            df_weekly = market_data.safe_yf_download(req.ticker, period="2y", interval="1wk", auto_adjust=False)
            if isinstance(df_weekly.columns, pd.MultiIndex):
                try:
                    if req.ticker in df_weekly.columns.get_level_values(1):
                        df_weekly = df_weekly.xs(req.ticker, level=1, axis=1)
                    else:
                        df_weekly = df_weekly.xs(req.ticker, level=0, axis=1)
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

            # Interpolate Weekly RSI indicators onto Daily Index for smooth visualization
            if not df_weekly.empty:
                # Select only the indicator columns we need
                interp_cols = ['RSI', 'RSI_SMA_3', 'RSI_SMA_14', 'RSI_SMA_21']
                # Create a temporary DF with daily index, reindex weekly data, and interpolate
                df_interp = df_weekly[interp_cols].reindex(df.index)
                df_interp = df_interp.interpolate(method='linear').fillna(method='bfill')
                
                # Add to main DF
                df['rsi_weekly'] = df_interp['RSI']
                df['rsi_sma_3'] = df_interp['RSI_SMA_3']
                df['rsi_sma_14'] = df_interp['RSI_SMA_14']
                df['rsi_sma_21'] = df_interp['RSI_SMA_21']

            # Create basic chart data without bull flag metrics
            chart_data = []
            for idx, row in df.iterrows():
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
                
                # Add interpolated RSI values
                for field in ['rsi_weekly', 'rsi_sma_3', 'rsi_sma_14', 'rsi_sma_21']:
                    if field in row and not pd.isna(row[field]):
                        data_point[field] = float(row[field])
                
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
        # Use safe_yf_download for timeout protection
        df_grade = market_data.safe_yf_download(req.ticker, period=screener.PERIOD, 
                                  interval=screener.INTERVAL, auto_adjust=False)
        
        if not df_grade.empty:
            # Handle MultiIndex more robustly
            if isinstance(df_grade.columns, pd.MultiIndex):
                if req.ticker in df_grade.columns.get_level_values(1):
                    df_grade = df_grade.xs(req.ticker, axis=1, level=1)
                elif req.ticker in df_grade.columns.get_level_values(0):
                    df_grade = df_grade.xs(req.ticker, axis=1, level=0)
                else:
                    # Fallback: flatten
                    df_grade.columns = [c[0] for c in df_grade.columns]
            
            pattern_result = screener.compute_3m_pattern(df_grade)
            if pattern_result:
                score = scoring.calculate_score(pattern_result)
                grade = scoring.score_to_grade(score)
                result["grade"] = grade
                result["score"] = score
            
            # Add Elliott Wave analysis
            elliott_analysis = elliott.analyze_elliott_waves(df_grade)
            result["elliott_wave"] = elliott_analysis
    except Exception as e:
        print(f"Error in analysis extras for {req.ticker}: {e}")
        pass
    
    
    # Common Step: Fetch Options Data
    if result and "metrics" in result:
        result["metrics"]["options_sentiment"] = get_options_sentiment(req.ticker)

        # Phase 40: Integrated Journal Data (Execution Markers & Multi-Targets)
        try:
            journal_res = trade_journal.get_trades(ticker=req.ticker)
            if journal_res and journal_res.get("trades"):
                trades = journal_res["trades"]
                
                # 1. Map execution history to markers
                trade_history = []
                for t in trades:
                    # Entry
                    if t.get("entry_date"):
                        trade_history.append({
                            "time": t["entry_date"], 
                            "price": t["entry_price"], 
                            "side": "BUY" if t["direction"] == "LONG" else "SELL",
                            "qty": t.get("shares", 0)
                        })
                    # Exit (if it was a long and closed, exit is a sell)
                    if t.get("status") == "CLOSED" and t.get("exit_date"):
                        trade_history.append({
                            "time": t["exit_date"], 
                            "price": t["exit_price"], 
                            "side": "SELL" if t["direction"] == "LONG" else "BUY",
                            "qty": t.get("shares", 0)
                        })
                result["trade_history"] = trade_history

                # 2. Level overrides (Check for OPEN trade info for SL/TPs)
                open_trades = [t for t in trades if t["status"] == "OPEN"]
                if open_trades:
                    # Sort by date desc to get newest if multiple entries (FIFO means newest has latest targets)
                    latest = sorted(open_trades, key=lambda x: x['entry_date'], reverse=True)[0]
                    result["metrics"]["entry"] = latest.get("entry_price") or result["metrics"].get("entry")
                    result["metrics"]["stop_loss"] = latest.get("stop_loss") or result["metrics"].get("stop_loss")
                    result["metrics"]["target"] = latest.get("target") or result["metrics"].get("target")
                    result["metrics"]["target2"] = latest.get("target2") or 0
                    result["metrics"]["target3"] = latest.get("target3") or 0
                    result["metrics"]["is_journal_active"] = True
        except Exception as e:
            print(f"Error merging journal data for {req.ticker}: {e}")
            
    # Phase 50: Price Predictions (Request by User)
    if result and "chart_data" in result:
        # Avoid double projection if screener already did it (bull flag case)
        if not any(d.get("is_projection") for d in result["chart_data"]):
            try:
                # Use safe_yf_download for timeout protection
                df_pred = market_data.safe_yf_download(req.ticker, period="6mo", interval="1d", auto_adjust=False)
                if df_pred is not None and not df_pred.empty:
                    # Flatten MultiIndex if necessary (yf quirk)
                    if isinstance(df_pred.columns, pd.MultiIndex):
                        df_pred.columns = [c[0] for c in df_pred.columns]
                    
                    entry_p = result["metrics"].get("entry")
                    target_p = result["metrics"].get("target")
                    predictions = screener.predict_future_path(df_pred, entry_price=entry_p, target=target_p)
                    result["chart_data"].extend(predictions)
            except Exception as e:
                print(f"Prediction merging failed for {req.ticker}: {e}")
    
    return result

@app.get("/api/market-status")
def get_market_status_api():
    return market_data.get_market_status()

import news  # News module

@app.get("/api/news/portfolio")
def get_portfolio_news_api(tickers: str = ""):
    """Get news for portfolio tickers. Pass comma-separated tickers."""
    if not tickers:
        return []
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    return news.get_news_for_tickers(ticker_list, days=3, max_items=10)

@app.get("/api/news/market")
def get_market_news_api():
    """Get general market headlines."""
    return news.get_market_headlines(days=1)

import options_scanner # New Import

@app.get("/api/ai-recommendations")
def get_ai_recommendations_api():
    return ai_advisor.get_recommendations()

@app.post("/api/scan-options")
def scan_options_api():
    """Trigger a scan for unusual options activity"""
    return options_scanner.scan_unusual_options()

@app.get("/api/options-flow")
def get_options_flow_api():
    """Get cached unusual options flow"""
    return options_scanner.get_cached_options_flow()

# -----------------------------------------------------
# Scheduled Scan Reports Endpoints
# -----------------------------------------------------
import scheduled_scan

@app.get("/api/scan/reports")
def list_scan_reports():
    """List all available scan reports"""
    return {"reports": scheduled_scan.list_reports()}

@app.get("/api/scan/reports/latest")
def get_latest_scan_report():
    """Get the most recent scan report"""
    report = scheduled_scan.get_latest_report()
    if report:
        return report
    return {"error": "No reports found"}

@app.post("/api/scan/run-now")
def run_scan_now():
    """Manually trigger a scheduled scan with report"""
    filepath = scheduled_scan.run_scheduled_scan()
    if filepath:
        return {"status": "complete", "report": filepath}
    return {"status": "error", "message": "Scan failed"}

# -----------------------------------------------------
# Sharpe Portfolio Endpoints (Fundamental Analysis)
# -----------------------------------------------------
import fundamental_screener

@app.get("/api/fundamental/scan")
def scan_sharpe_portfolio(min_sharpe: float = 1.5, max_pe: float = 50.0, min_pe: float = 0.0):
    """Scan cached tickers for high Sharpe ratio stocks"""
    return fundamental_screener.scan_sharpe_portfolio(
        min_sharpe=min_sharpe, 
        max_pe=max_pe, 
        min_pe=min_pe
    )

@app.get("/api/fundamental/portfolio")
def build_sharpe_portfolio(max_positions: int = 10, min_sharpe: float = 1.5, strategy: str = 'undervalued'):
    """
    Build equal-weight portfolio. 
    Strategy='undervalued' prioritizes PE < 20.
    """
    scan_result = fundamental_screener.scan_sharpe_portfolio(
        min_sharpe=min_sharpe,
        max_pe=100.0, # Widen buffer for scan, let portfolio builder filter strict PE
        min_pe=0.0
    )
    if "error" in scan_result:
        return scan_result
        
    portfolio = fundamental_screener.build_equal_weight_portfolio(
        scan_result.get("results", []), 
        max_positions=max_positions,
        strategy=strategy
    )
    
    # Return BOTH pieces of data
    return {
        "portfolio": portfolio,
        "scan_results": scan_result
    }

# -----------------------------------------------------
# Alert System Endpoints
# -----------------------------------------------------



# -----------------------------------------------------
# AI ANALYST (MARKET BRAIN)
# -----------------------------------------------------
import market_brain

@app.get("/api/ai/insight")
def get_ai_insight():
    """Generate AI market insight using Gemini"""
    # Gather context from existing market data
    status = market_data.get_market_status()
    
    # Format context for the AI
    context = {
        "indices": {k: f"{v.get('price')} ({v.get('ext_change_pct')}%)" for k, v in status.get('indices', {}).items() if isinstance(v, dict)},
        "movers": "See market status for details", # Simplified for now
        "news": "Latest market headlines available in system",
        "breadth": status.get('breadth', 'Neutral')
    }
    
    insight = market_brain.get_market_insight(context)
    return {"insight": insight}

@app.get("/api/ai/portfolio-insight")
def get_portfolio_insight():
    """Generate AI portfolio analysis using Gemini"""
    # Gather portfolio data from trade journal
    try:
        result = trade_journal.get_trades()
        trades = result.get("trades", []) if isinstance(result, dict) else []
        # Fix: status is 'OPEN' not 'open' - use case-insensitive comparison
        open_trades = [t for t in trades if isinstance(t, dict) and str(t.get('status', '')).upper() == 'OPEN']
        
        if not open_trades:
            return {"insight": "No open positions found in the USA portfolio."}
        
        # Get live prices for accurate PnL
        live_data = trade_journal.get_open_prices()
        
        # Calculate portfolio metrics
        total_value = 0
        unrealized_pnl = 0
        positions = []
        pnl_list = []
        
        for t in open_trades:
            ticker = t.get('ticker', '?')
            shares = float(t.get('shares', 0) or 0)
            entry = float(t.get('entry_price', 0) or 0)
            
            # Get current price from live data
            live = live_data.get(ticker, {})
            current = float(live.get('price', entry) or entry)
            
            value = current * shares
            pnl = (current - entry) * shares
            pnl_pct = ((current / entry) - 1) * 100 if entry > 0 else 0
            
            total_value += value
            unrealized_pnl += pnl
            
            positions.append(f"{ticker} ({int(shares)} @ ${entry:.2f})")
            pnl_list.append({"ticker": ticker, "pnl_pct": pnl_pct})
        
        # Sort by PnL %
        sorted_by_pnl = sorted(pnl_list, key=lambda x: x['pnl_pct'], reverse=True)
        winners = [f"{p['ticker']}: +{p['pnl_pct']:.1f}%" for p in sorted_by_pnl[:3] if p['pnl_pct'] > 0]
        losers = [f"{p['ticker']}: {p['pnl_pct']:.1f}%" for p in sorted_by_pnl if p['pnl_pct'] < 0][-3:]
        
        portfolio_data = {
            "positions": ", ".join(positions[:10]) if positions else "No open positions",
            "total_value": f"${total_value:,.2f}",
            "unrealized_pnl": f"${unrealized_pnl:,.2f}",
            "sectors": "Mixed (data not available)",
            "winners": ", ".join(winners) if winners else "None",
            "losers": ", ".join(losers) if losers else "None"
        }
        
        insight = market_brain.get_portfolio_insight(portfolio_data)
        return {"insight": insight}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"insight": f"Error gathering portfolio data: {e}"}


# Portfolio Chatbot Endpoint
class ChatQuery(BaseModel):
    query: str
    history: list = []

@app.post("/api/chat/query")
def chat_query(chat: ChatQuery):
    """Conversational AI assistant for portfolio queries"""
    try:
        # Get live portfolio context
        result = trade_journal.get_trades()
        trades = result.get("trades", []) if isinstance(result, dict) else []
        open_trades = [t for t in trades if isinstance(t, dict) and str(t.get('status', '')).upper() == 'OPEN']
        
        # Get live prices
        live_data = trade_journal.get_open_prices()
        
        # Build portfolio context
        positions = []
        total_value = 0
        unrealized_pnl = 0
        
        for t in open_trades:
            ticker = t.get('ticker', '?')
            shares = float(t.get('shares', 0) or 0)
            entry = float(t.get('entry_price', 0) or 0)
            
            live = live_data.get(ticker, {})
            current = float(live.get('price', entry) or entry)
            
            value = current * shares
            pnl = (current - entry) * shares
            
            total_value += value
            unrealized_pnl += pnl
            
            positions.append({
                'ticker': ticker,
                'shares': shares,
                'entry_price': entry,
                'current_price': current
            })
        
        portfolio_context = {
            'positions': positions,
            'metrics': {
                'total_value': total_value,
                'unrealized_pnl': unrealized_pnl,
                'position_count': len(positions)
            }
        }
        
        # Call chat function
        response = market_brain.chat_with_portfolio(
            user_query=chat.query,
            conversation_history=chat.history,
            portfolio_context=portfolio_context
        )
        
        return {"response": response, "context_used": True}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"response": f"Sorry, I encountered an error: {str(e)}", "context_used": False}


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

# Watchlist endpoints are handled by the watchlist_router (imported from watchlist.py)
# which is included at the top of the file.

@app.get("/api/premarket/{ticker}")
def get_premarket_price(ticker: str):
    """Fetch pre/post market price and change %"""
    try:
        stock = yf.Ticker(ticker)
        
        # Try to get regular price from fast_info first
        regular_price = 0
        try:
            regular_price = stock.fast_info.last_price
        except:
            pass
            
        # Try to get info (buggy in yfinance, can throw NoneType errors)
        info = {}
        try:
            # We wrap this because yf.Ticker.info is notoriously unreliable
            info_data = stock.info
            if isinstance(info_data, dict):
                info = info_data
        except Exception:
            # Fallback if info fails
            pass
            
        if not regular_price:
            regular_price = info.get('regularMarketPrice', info.get('currentPrice', 0))
        
        # Extended hours data
        premarket_price = info.get('preMarketPrice')
        postmarket_price = info.get('postMarketPrice')
        
        extended_price = premarket_price or postmarket_price
        extended_change_pct = None
        
        if extended_price and regular_price and regular_price > 0:
            extended_change_pct = ((extended_price - regular_price) / regular_price) * 100
        
        return {
            "ticker": ticker.upper(),
            "regular_price": regular_price or 0,
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
                await asyncio.to_thread(alerts.check_price_alerts)
            
            # Record Portfolio Snapshot (Intra-day updates or closing)
            from trade_journal import capture_daily_snapshot
            await asyncio.to_thread(capture_daily_snapshot)
            
        except Exception as e:
            print(f"Error in alert monitor: {e}")
        
        await asyncio.sleep(300)  # 5 minutes

async def options_scanner_loop():
    """Background task that refreshes the Swing Options Flow every 30 minutes"""
    import options_scanner
    while True:
        try:
            print(f"[{datetime.now()}] Running automatic Options Flow scan...")
            # Use to_thread to prevent blocking the main event loop during startup
            await asyncio.to_thread(options_scanner.refresh_options_sync)
        except Exception as e:
            print(f"Error in options scanner loop: {e}")
        
        await asyncio.sleep(1800)  # 30 minutes

@app.on_event("startup")
async def start_alert_monitor():
    """Start background alert monitoring on server startup"""
    asyncio.create_task(alert_monitor_loop())
    asyncio.create_task(scheduled_reports_loop())
    asyncio.create_task(options_scanner_loop()) # Auto-scan options
    
    # Start scheduled RSI scanner (runs daily at 6pm Argentina / 4pm EST)
    import scheduled_scan
    scheduled_scan.start_scheduler()
    
    print("✅ Alert monitoring started")
    print("✅ Scheduled briefings started")
    print("✅ Automatic Options Scanning started")
    print("✅ Scheduled RSI Scanner started (6pm Argentina daily)")

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
# PORTFOLIO SNAPSHOTS ENDPOINTS
# -----------------------------------------------------
import portfolio_snapshots
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# Initialize scheduler for daily portfolio snapshots at 19:00 ARG
_snapshot_scheduler = None

def start_snapshot_scheduler():
    """Start the background scheduler for daily snapshots at 19:00 ARG."""
    global _snapshot_scheduler
    if _snapshot_scheduler is not None:
        return  # Already running
    
    try:
        tz_arg = pytz.timezone("America/Argentina/Buenos_Aires")
        _snapshot_scheduler = BackgroundScheduler(timezone=tz_arg)
        
        # Schedule daily at 19:00 ARG time
        trigger = CronTrigger(hour=19, minute=0, timezone=tz_arg)
        _snapshot_scheduler.add_job(
            portfolio_snapshots.take_snapshot,
            trigger,
            id="daily_portfolio_snapshot",
            name="Daily Portfolio Snapshot (19:00 ARG)",
            replace_existing=True
        )
        
        _snapshot_scheduler.start()
        print("[Scheduler] Portfolio snapshot scheduler started - runs daily at 19:00 ARG")
    except Exception as e:
        print(f"[Scheduler] Error starting snapshot scheduler: {e}")

# Start scheduler on app startup
@app.on_event("startup")
async def startup_event():
    start_snapshot_scheduler()
    print("[Startup] Portfolio snapshot scheduler initialized")

@app.get("/api/portfolio/snapshots")
def get_portfolio_snapshots(days: int = 365):
    """Get portfolio history for charts."""
    return portfolio_snapshots.get_history(days)

@app.get("/api/portfolio/snapshot/latest")
def get_latest_snapshot():
    """Get the most recent portfolio snapshot."""
    return portfolio_snapshots.get_latest() or {}

@app.get("/api/portfolio/distribution")
def get_portfolio_distribution():
    """Get geographic distribution of investments."""
    return portfolio_snapshots.get_geographic_distribution()

@app.post("/api/portfolio/snapshot/take")
def take_manual_snapshot():
    """Manually trigger a portfolio snapshot (for testing)."""
    return portfolio_snapshots.take_snapshot()


# -----------------------------------------------------
# BACKUP ENDPOINTS
# -----------------------------------------------------
try:
    import backup
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
static_dir = os.path.join(BASE_DIR, "static")
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
