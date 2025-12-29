"""
Telegram Alert System
Monitors trading positions and sends alerts via Telegram
"""
import requests
import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Import market_data with fallback
try:
    import market_data
except ImportError:
    try:
        from backend import market_data
    except ImportError:
        from . import market_data

# Telegram Configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")  # Set via environment variable
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None

DB_PATH = os.path.join(os.path.dirname(__file__), "trades.db")


def send_telegram(chat_id: str, message: str) -> bool:
    """Send message via Telegram"""
    if not TELEGRAM_API or not BOT_TOKEN:
        print("⚠️ Telegram BOT_TOKEN not configured")
        return False
    
    try:
        url = f"{TELEGRAM_API}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, data=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending Telegram: {e}")
        return False


def get_alert_settings() -> Optional[Dict]:
    """Get alert configuration from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alert_settings LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            "telegram_chat_id": row[1],
            "enabled": bool(row[2]),
            "check_interval": row[3],
            "notify_sl": bool(row[4]),
            "notify_tp": bool(row[5]),
            "notify_rsi_sell": bool(row[6]),
            "sl_warning_pct": row[7]
        }
    except Exception as e:
        print(f"Error getting alert settings: {e}")
        return None


def check_price_alerts():
    """
    Check all open positions for alert conditions:
    1. Stop Loss hit
    2. Target hit
    3. Price near SL (warning)
    4. W.RSI bearish (sell signal)
    """
    settings = get_alert_settings()
    if not settings or not settings["enabled"] or not settings["telegram_chat_id"]:
        return
    
    try:
        # Import here to avoid circular dependency
        import yfinance as yf
        import indicators
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get open positions
        cursor.execute("""
            SELECT id, ticker, entry_price, shares, stop_loss, target, target2, target3, entry_date
            FROM trades 
            WHERE status = 'OPEN'
        """)
        trades = cursor.fetchall()
        
        # Get last sent alerts to avoid spam
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER,
                alert_type TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Batch fetch prices using market_data
        tickers = [t[1] for t in trades]
        prices_map = market_data.get_batch_latest_prices(tickers)
        
        for trade in trades:
            trade_id, ticker, entry_price, shares, stop_loss, target, target2, target3, entry_date = trade
            
            # Get current price from batch
            current_price = prices_map.get(ticker)
            if not current_price:
                continue
            
            # Check 1: Stop Loss Hit
            if settings["notify_sl"] and stop_loss and current_price <= stop_loss:
                if not alert_recently_sent(cursor, trade_id, 'SL_HIT'):
                    loss_pct = ((current_price - entry_price) / entry_price) * 100
                    message = f"""
🔴 <b>STOP LOSS HIT</b>

Ticker: <b>{ticker}</b>
Entry: ${entry_price:.2f}
Current: ${current_price:.2f}
Stop Loss: ${stop_loss:.2f}

Loss: ${(current_price - entry_price) * shares:.2f} ({loss_pct:.2f}%)

⚠️ Consider exiting position
"""
                    send_telegram(settings["telegram_chat_id"], message)
                    log_alert(cursor, trade_id, 'SL_HIT')
            
            # Check 2: Target Hit (any of the 3 targets)
            if settings["notify_tp"]:
                targets = [("T1", target), ("T2", target2), ("T3", target3)]
                for label, tgt in targets:
                    if tgt and current_price >= tgt:
                        alert_type = f'TP_HIT_{label}'
                        if not alert_recently_sent(cursor, trade_id, alert_type):
                            profit_pct = ((current_price - entry_price) / entry_price) * 100
                            message = f"""
🟢 <b>TARGET {label} HIT</b>

Ticker: <b>{ticker}</b>
Entry: ${entry_price:.2f}
Current: ${current_price:.2f}
Target: ${tgt:.2f}

Profit: ${(current_price - entry_price) * shares:.2f} (+{profit_pct:.2f}%)

✅ Consider taking profits
"""
                            send_telegram(settings["telegram_chat_id"], message)
                            log_alert(cursor, trade_id, alert_type)
            
            # Check 3: Price near SL (warning)
            if settings["notify_sl"] and stop_loss:
                warning_threshold = stop_loss * (1 + settings["sl_warning_pct"] / 100)
                if stop_loss < current_price <= warning_threshold:
                    if not alert_recently_sent(cursor, trade_id, 'SL_WARNING', hours=24):
                        message = f"""
🟡 <b>APPROACHING STOP LOSS</b>

Ticker: <b>{ticker}</b>
Current: ${current_price:.2f}
Stop Loss: ${stop_loss:.2f}
Distance: {((current_price - stop_loss) / stop_loss * 100):.1f}%

⚠️ Monitor closely
"""
                        send_telegram(settings["telegram_chat_id"], message)
                        log_alert(cursor, trade_id, 'SL_WARNING')
            
            # Check 4: W.RSI Bearish (Sell Signal)
            if settings["notify_rsi_sell"]:
                try:
                    # Fetch weekly data and calculate RSI
                    df = yf.download(ticker, period="2y", interval="1wk", progress=False, auto_adjust=False)
                    if df.empty:
                        continue
                    
                    # Handle MultiIndex
                    if hasattr(df.columns, 'levels'):
                        df = df.xs(ticker, level=1, axis=1) if ticker in df.columns.get_level_values(1) else df
                    
                    weekly_analytics = indicators.calculate_weekly_rsi_analytics(df)
                    if weekly_analytics and weekly_analytics.get('signal_sell'):
                        if not alert_recently_sent(cursor, trade_id, 'RSI_BEARISH', hours=168):  # Once per week
                            message = f"""
📉 <b>WEEKLY RSI BEARISH</b>

Ticker: <b>{ticker}</b>
RSI: {weekly_analytics['rsi']:.1f}
SMA3: {weekly_analytics['sma3']:.1f}
SMA14: {weekly_analytics['sma14']:.1f}

❗ SMA3 crossed below SMA14
Consider trimming position
"""
                            send_telegram(settings["telegram_chat_id"], message)
                            log_alert(cursor, trade_id, 'RSI_BEARISH')
                except Exception as e:
                    print(f"Error checking RSI for {ticker}: {e}")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error in check_price_alerts: {e}")


def alert_recently_sent(cursor, trade_id: int, alert_type: str, hours: int = 24) -> bool:
    """Check if alert was sent recently to avoid spam"""
    cursor.execute("""
        SELECT COUNT(*) FROM alert_history 
        WHERE trade_id = ? AND alert_type = ? 
        AND sent_at > datetime('now', '-' || ? || ' hours')
    """, (trade_id, alert_type, hours))
    count = cursor.fetchone()[0]
    return count > 0


def log_alert(cursor, trade_id: int, alert_type: str):
    """Log sent alert to history"""
    cursor.execute("""
        INSERT INTO alert_history (trade_id, alert_type) VALUES (?, ?)
    """, (trade_id, alert_type))


def init_alert_db():
    """Initialize alert settings table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alert_settings (
            id INTEGER PRIMARY KEY,
            telegram_chat_id TEXT,
            enabled BOOLEAN DEFAULT 0,
            check_interval INTEGER DEFAULT 300,
            notify_sl BOOLEAN DEFAULT 1,
            notify_tp BOOLEAN DEFAULT 1,
            notify_rsi_sell BOOLEAN DEFAULT 1,
            sl_warning_pct REAL DEFAULT 2.0
        )
    """)
    
    # Create default settings if not exists
    cursor.execute("SELECT COUNT(*) FROM alert_settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO alert_settings (enabled, telegram_chat_id) VALUES (0, '')
        """)
    
    conn.commit()
    conn.close()


def send_scheduled_briefing(report_type: str) -> bool:
    """
    Sends a scheduled market briefing.
    report_type: 'MORNING' or 'EVENING'
    """
    settings = get_alert_settings()
    if not settings or not settings["telegram_chat_id"]:
        print("Scheduled Alert Skipped: No Chat ID")
        return False
        
    try:
        # Fetch fresh data
        status = market_data.get_market_status()
        if "error" in status:
            print(f"Error fetching data for briefing: {status['error']}")
            return False
            
        message = ""
        
        if report_type == "MORNING":
            message = market_data.generate_morning_briefing(status['indices'], status['sectors'])
        elif report_type == "EVENING":
            summary = status['expert_summary']
            message = f"""
🌙 <b>CLOSING BELL BRIEFING</b>

<b>Mood:</b> {summary['mood']}
<b>Setup:</b> {summary['setup']}

<b>Market Internals:</b>
{summary['internals']}

<b>Expert Play:</b>
{summary['play']}

<i>"Markets are closed. Review your journal."</i>
"""
        
        if message:
            return send_telegram(settings["telegram_chat_id"], message)
            
    except Exception as e:
        print(f"Error sending scheduled briefing: {e}")
        return False


# Watchlist DB Management
def init_watchlist_db():
    """Initialize watchlist table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            ticker TEXT PRIMARY KEY,
            note TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def get_watchlist():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, note, added_at FROM watchlist ORDER BY added_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{"ticker": r[0], "note": r[1], "added_at": r[2]} for r in rows]

def add_to_watchlist(ticker, note=""):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO watchlist (ticker, note) VALUES (?, ?)", (ticker, note))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding to watchlist: {e}")
        return False

def remove_from_watchlist(ticker):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error removing from watchlist: {e}")
        return False

# Initialize on module load
init_alert_db()
init_watchlist_db()
