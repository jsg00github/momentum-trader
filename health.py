import os
import sqlite3
import yfinance as yf
import psutil
import time
from datetime import datetime

def check_databases():
    """Check integrity of the system databases."""
    db_status = {}
    
    # 1. Trades Database
    trades_db = "trades.db"
    try:
        if not os.path.exists(trades_db):
            db_status["trades_db"] = {"status": "error", "message": "Database file not found"}
        else:
            conn = sqlite3.connect(trades_db)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
            if cursor.fetchone():
                db_status["trades_db"] = {"status": "ok", "message": "Connected and table exists"}
            else:
                db_status["trades_db"] = {"status": "warning", "message": "Connected but 'trades' table missing"}
            conn.close()
    except Exception as e:
        db_status["trades_db"] = {"status": "error", "message": str(e)}

    # 2. Momentum Trader Database (Watchlist)
    mt_db = "momentum_trader.db"
    try:
        if not os.path.exists(mt_db):
            db_status["momentum_trader_db"] = {"status": "error", "message": "Database file not found"}
        else:
            conn = sqlite3.connect(mt_db)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='watchlist'")
            if cursor.fetchone():
                db_status["momentum_trader_db"] = {"status": "ok", "message": "Connected and table exists"}
            else:
                db_status["momentum_trader_db"] = {"status": "warning", "message": "Connected but 'watchlist' table missing"}
            conn.close()
    except Exception as e:
        db_status["momentum_trader_db"] = {"status": "error", "message": str(e)}

    return db_status

def check_market_data():
    """Verify connectivity to yfinance via a lightweight request."""
    import requests
    try:
        start_time = time.time()
        # Use a simple requests check to Yahoo's query API with a strict timeout
        # This is much faster and more reliable for a healthcheck than yf.Ticker.history
        response = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/SPY?interval=1d&range=1d", timeout=5)
        latency = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            last_price = data['chart']['result'][0]['meta']['regularMarketPrice']
            return {
                "status": "ok",
                "message": "Connected to Yahoo Finance",
                "latency_ms": round(latency, 2),
                "last_price": last_price
            }
        else:
            return {"status": "error", "message": f"Yahoo API returned status {response.status_code}"}
    except Exception as e:
        return {"status": "error", "message": f"Yahoo connection failed or timed out: {str(e)}"}

def check_system_resources():
    """Check server resource usage."""
    try:
        cpu_usage = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('.')
        
        return {
            "cpu_usage_pct": cpu_usage,
            "ram_usage_pct": memory.percent,
            "ram_available_mb": round(memory.available / (1024 * 1024), 2),
            "disk_free_gb": round(disk.free / (1024 * 1024 * 1024), 2),
            "status": "ok" if memory.percent < 90 and disk.percent < 95 else "warning"
        }
    except Exception as e:
        return {"status": "error", "message": f"Resource check failed: {str(e)}"}

def get_full_health():
    """Aggregate all health checks."""
    dbs = check_databases()
    market = check_market_data()
    resources = check_system_resources()
    
    # Check Finnhub status
    finnhub = {"status": "disabled", "message": "Finnhub not configured"}
    try:
        import config
        import finnhub_provider
        if config.FINNHUB_ENABLED:
            finnhub = finnhub_provider.check_connectivity()
    except ImportError:
        pass
    
    # Check Cache stats
    cache_stats = {"status": "ok", "total_entries": 0, "fresh_24h": 0}
    try:
        import cache
        c = cache.get_cache()
        stats = c.stats()
        cache_stats.update(stats)
        cache_stats["status"] = "ok" if stats["total_entries"] > 0 else "empty"
    except Exception as e:
        cache_stats = {"status": "error", "message": str(e)}
    
    # Overall status logic
    # Fallback chain: Yahoo → Finnhub → Cache
    overall = "ok"
    yahoo_ok = market["status"] == "ok"
    finnhub_ok = finnhub.get("status") == "ok"
    cache_available = cache_stats.get("total_entries", 0) > 0
    
    if any(v["status"] == "error" for v in dbs.values()):
        overall = "error"
    elif not yahoo_ok and not finnhub_ok and not cache_available:
        overall = "error"  # All providers failed
    elif not yahoo_ok:
        overall = "warning"  # Yahoo down, using backups
    elif any(v["status"] == "warning" for v in dbs.values()) or resources["status"] == "warning":
        overall = "warning"
        
    return {
        "timestamp": datetime.now().isoformat(),
        "overall_status": overall,
        "components": {
            "databases": dbs,
            "market_data": market,
            "finnhub": finnhub,
            "cache": cache_stats,
            "resources": resources
        }
    }

if __name__ == "__main__":
    import json
    print(json.dumps(get_full_health(), indent=2))
