"""
Portfolio Snapshots Module
Handles daily portfolio value tracking and historical data storage.
Snapshots are taken automatically at 19:00 ARG time.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import threading

# Database path
DB_PATH = Path(__file__).parent / "portfolio_snapshots.db"
_db_lock = threading.Lock()

def get_connection():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the snapshots database table."""
    with _db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                total_invested_usd REAL DEFAULT 0,
                total_value_usd REAL DEFAULT 0,
                total_pnl_usd REAL DEFAULT 0,
                total_pnl_pct REAL DEFAULT 0,
                usa_invested_usd REAL DEFAULT 0,
                usa_value_usd REAL DEFAULT 0,
                usa_pnl_usd REAL DEFAULT 0,
                argentina_invested_usd REAL DEFAULT 0,
                argentina_value_usd REAL DEFAULT 0,
                argentina_pnl_usd REAL DEFAULT 0,
                crypto_invested_usd REAL DEFAULT 0,
                crypto_value_usd REAL DEFAULT 0,
                crypto_pnl_usd REAL DEFAULT 0,
                brasil_invested_usd REAL DEFAULT 0,
                brasil_value_usd REAL DEFAULT 0,
                brasil_pnl_usd REAL DEFAULT 0,
                china_invested_usd REAL DEFAULT 0,
                china_value_usd REAL DEFAULT 0,
                china_pnl_usd REAL DEFAULT 0,
                europa_invested_usd REAL DEFAULT 0,
                europa_value_usd REAL DEFAULT 0,
                europa_pnl_usd REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        print("[PortfolioSnapshots] Database initialized.")

def take_snapshot():
    """
    Take a snapshot of the current portfolio state.
    Called automatically at 19:00 ARG or manually for testing.
    """
    try:
        # Use HTTP request to get unified metrics (most reliable source)
        import urllib.request
        import json
        
        today = datetime.now().strftime("%Y-%m-%d")
        print(f"\n>>> TAKING PORTFOLIO SNAPSHOT FOR {today} <<<")
        
        # Fetch unified metrics from internal API
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/trades/unified/metrics", timeout=30) as response:
                data = json.loads(response.read().decode())
        except Exception as e:
            print(f"  Error fetching unified metrics via HTTP: {e}")
            # Fallback: import and call directly
            import trade_journal
            data = trade_journal.get_unified_metrics()
        
        # Extract USA metrics
        usa_data = data.get("usa", {})
        usa_metrics = {
            "invested": float(usa_data.get("invested_usd", 0) or 0),
            "value": float(usa_data.get("current_usd", 0) or 0),
            "pnl": float(usa_data.get("pnl_usd", 0) or 0)
        }
        print(f"  USA: Invested=${usa_metrics['invested']:.2f}, Value=${usa_metrics['value']:.2f}, P&L=${usa_metrics['pnl']:.2f}")
        
        # Extract Argentina metrics (in USD CCL)
        arg_data = data.get("argentina", {})
        argentina_metrics = {
            "invested": float(arg_data.get("invested_usd_ccl", 0) or 0),
            "value": float(arg_data.get("current_usd_ccl", 0) or 0),
            "pnl": float(arg_data.get("pnl_usd_ccl", 0) or 0)
        }
        print(f"  Argentina: Invested=${argentina_metrics['invested']:.2f}, Value=${argentina_metrics['value']:.2f}, P&L=${argentina_metrics['pnl']:.2f}")
        
        # Crypto
        try:
            import crypto_journal
            c_data = crypto_journal.get_portfolio_metrics()
            crypto_metrics = {
                "invested": float(c_data.get("total_invested", 0) or 0),
                "value": float(c_data.get("total_value", 0) or 0),
                "pnl": float(c_data.get("total_pnl", 0) or 0)
            }
            print(f"  Crypto: Invested=${crypto_metrics['invested']:.2f}, Value=${crypto_metrics['value']:.2f}")
        except Exception as e:
            print(f"  Error fetching crypto metrics: {e}")
            crypto_metrics = {"invested": 0, "value": 0, "pnl": 0}
        
        # Brasil, China, Europa - placeholders for future expansion
        brasil_metrics = {"invested": 0, "value": 0, "pnl": 0}
        china_metrics = {"invested": 0, "value": 0, "pnl": 0}
        europa_metrics = {"invested": 0, "value": 0, "pnl": 0}
        
        # Calculate totals
        total_invested = usa_metrics["invested"] + argentina_metrics["invested"] + crypto_metrics["invested"]
        total_value = usa_metrics["value"] + argentina_metrics["value"] + crypto_metrics["value"]
        total_pnl = usa_metrics["pnl"] + argentina_metrics["pnl"] + crypto_metrics["pnl"]
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
        
        print(f"  TOTAL: Invested=${total_invested:.2f}, Value=${total_value:.2f}, P&L=${total_pnl:.2f} ({total_pnl_pct:.2f}%)")
        
        # Save to database
        with _db_lock:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Use INSERT OR REPLACE to update if today's snapshot exists
            cursor.execute('''
                INSERT OR REPLACE INTO portfolio_snapshots (
                    date, total_invested_usd, total_value_usd, total_pnl_usd, total_pnl_pct,
                    usa_invested_usd, usa_value_usd, usa_pnl_usd,
                    argentina_invested_usd, argentina_value_usd, argentina_pnl_usd,
                    crypto_invested_usd, crypto_value_usd, crypto_pnl_usd,
                    brasil_invested_usd, brasil_value_usd, brasil_pnl_usd,
                    china_invested_usd, china_value_usd, china_pnl_usd,
                    europa_invested_usd, europa_value_usd, europa_pnl_usd,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                today, total_invested, total_value, total_pnl, total_pnl_pct,
                usa_metrics["invested"], usa_metrics["value"], usa_metrics["pnl"],
                argentina_metrics["invested"], argentina_metrics["value"], argentina_metrics["pnl"],
                crypto_metrics["invested"], crypto_metrics["value"], crypto_metrics["pnl"],
                brasil_metrics["invested"], brasil_metrics["value"], brasil_metrics["pnl"],
                china_metrics["invested"], china_metrics["value"], china_metrics["pnl"],
                europa_metrics["invested"], europa_metrics["value"], europa_metrics["pnl"],
                datetime.now().isoformat()
            ))
            conn.commit()
            conn.close()
        
        print(f">>> SNAPSHOT SAVED SUCCESSFULLY <<<\n")
        return {"status": "success", "date": today, "total_value": total_value, "total_pnl": total_pnl}
        
    except Exception as e:
        print(f">>> SNAPSHOT ERROR: {e} <<<")
        return {"status": "error", "message": str(e)}

def get_history(days: int = 365):
    """
    Get portfolio history for the specified number of days.
    Returns list of snapshots ordered by date ascending.
    """
    with _db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        cursor.execute('''
            SELECT * FROM portfolio_snapshots 
            WHERE date >= ? 
            ORDER BY date ASC
        ''', (cutoff_date,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]

def get_latest():
    """Get the most recent snapshot."""
    with _db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM portfolio_snapshots 
            ORDER BY date DESC 
            LIMIT 1
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None

def get_geographic_distribution():
    """
    Get current portfolio distribution by country/region.
    Returns percentages and values for each region.
    """
    latest = get_latest()
    
    if not latest:
        return {
            "usa": {"value": 0, "pct": 0},
            "argentina": {"value": 0, "pct": 0},
            "crypto": {"value": 0, "pct": 0},
            "brasil": {"value": 0, "pct": 0},
            "china": {"value": 0, "pct": 0},
            "europa": {"value": 0, "pct": 0}
        }
    
    total = latest.get("total_value_usd", 0) or 1  # Avoid division by zero
    
    regions = {
        "usa": latest.get("usa_value_usd", 0),
        "argentina": latest.get("argentina_value_usd", 0),
        "crypto": latest.get("crypto_value_usd", 0),
        "brasil": latest.get("brasil_value_usd", 0),
        "china": latest.get("china_value_usd", 0),
        "europa": latest.get("europa_value_usd", 0)
    }
    
    return {
        region: {
            "value": value,
            "pct": round((value / total) * 100, 1) if total > 0 else 0
        }
        for region, value in regions.items()
    }

# Initialize database on module import
init_db()
