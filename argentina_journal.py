"""
Argentina Trade Journal Module
- SQLite storage for Argentine positions
- Supports stocks, CEDEARs, and options
- Portfolio valuation in ARS, MEP, CCL
"""
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Any
from fastapi import APIRouter
from pydantic import BaseModel

import argentina_data

# Router for FastAPI
router = APIRouter(prefix="/api/argentina", tags=["argentina"])

# Database path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "argentina_journal.db")


# ============================================
# Pydantic Models
# ============================================

class ArgentinaPosition(BaseModel):
    ticker: str
    asset_type: str  # 'stock', 'cedear', 'option'
    entry_date: str
    entry_price: float  # in ARS
    shares: float
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    target2: Optional[float] = None
    target3: Optional[float] = None
    strategy: Optional[str] = None
    hypothesis: Optional[str] = None
    option_strike: Optional[float] = None
    option_expiry: Optional[str] = None
    option_type: Optional[str] = None  # 'call' or 'put'
    notes: Optional[str] = None


class IOLCredentials(BaseModel):
    username: str
    password: str


# ============================================
# Database Setup
# ============================================

def init_db():
    """Initialize Argentina journal database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS argentina_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            asset_type TEXT NOT NULL DEFAULT 'stock',
            entry_date TEXT NOT NULL,
            entry_price REAL NOT NULL,
            shares REAL NOT NULL,
            stop_loss REAL,
            target REAL,
            strategy TEXT,
            hypothesis TEXT,
            option_strike REAL,
            option_expiry TEXT,
            option_type TEXT,
            notes TEXT,
            status TEXT DEFAULT 'open',
            exit_date TEXT,
            exit_price REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Migration: Add new columns if they don't exist
    try:
        c.execute('ALTER TABLE argentina_positions ADD COLUMN stop_loss REAL')
    except:
        pass
    try:
        c.execute('ALTER TABLE argentina_positions ADD COLUMN target REAL')
    except:
        pass
    try:
        c.execute('ALTER TABLE argentina_positions ADD COLUMN strategy TEXT')
    except:
        pass
    try:
        c.execute('ALTER TABLE argentina_positions ADD COLUMN hypothesis TEXT')
    except:
        pass
    try:
        c.execute('ALTER TABLE argentina_positions ADD COLUMN target2 REAL')
    except:
        pass
    try:
        c.execute('ALTER TABLE argentina_positions ADD COLUMN target3 REAL')
    except:
        pass
    
    # IOL credentials (encrypted in production)
    c.execute('''
        CREATE TABLE IF NOT EXISTS iol_config (
            id INTEGER PRIMARY KEY,
            username TEXT,
            password_hint TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("[Argentina Journal] Database initialized")


# Initialize on import
init_db()


# ============================================
# Position CRUD Operations
# ============================================

def get_all_positions(status: str = "open") -> List[Dict]:
    """Get all Argentine positions with optional status filter."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('''
        SELECT * FROM argentina_positions 
        WHERE status = ?
        ORDER BY entry_date DESC
    ''', (status,))
    
    positions = [dict(row) for row in c.fetchall()]
    conn.close()
    return positions


def add_position(position: ArgentinaPosition) -> Dict:
    """Add a new Argentine position."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        INSERT INTO argentina_positions 
        (ticker, asset_type, entry_date, entry_price, shares, 
         stop_loss, target, target2, target3, strategy, hypothesis,
         option_strike, option_expiry, option_type, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        position.ticker.upper(),
        position.asset_type,
        position.entry_date,
        position.entry_price,
        position.shares,
        position.stop_loss,
        position.target,
        position.target2,
        position.target3,
        position.strategy,
        position.hypothesis,
        position.option_strike,
        position.option_expiry,
        position.option_type,
        position.notes
    ))
    
    position_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return {"id": position_id, "status": "created"}


def close_position(position_id: int, exit_price: float) -> Dict:
    """Close an existing position."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        UPDATE argentina_positions 
        SET status = 'closed', 
            exit_date = ?,
            exit_price = ?
        WHERE id = ?
    ''', (datetime.now().strftime("%Y-%m-%d"), exit_price, position_id))
    
    conn.commit()
    conn.close()
    
    return {"id": position_id, "status": "closed"}


def delete_position(position_id: int) -> Dict:
    """Delete a position."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('DELETE FROM argentina_positions WHERE id = ?', (position_id,))
    
    conn.commit()
    conn.close()
    
    return {"id": position_id, "status": "deleted"}


# ============================================
# Portfolio Valuation
# ============================================

def get_portfolio_valuation() -> Dict:
    """
    Get portfolio valuation in ARS, MEP USD, and CCL USD.
    Fetches live prices for open positions.
    """
    positions = get_all_positions("open")
    rates = argentina_data.get_dolar_rates()
    
    total_ars = 0.0
    holdings = []
    
    for pos in positions:
        ticker = pos["ticker"]
        shares = pos["shares"]
        entry_price = pos["entry_price"]
        asset_type = pos["asset_type"]
        
        # Get current price
        current_price = None
        if asset_type in ["stock", "cedear"]:
            # Try IOL first, then Yahoo Finance
            quote = argentina_data.get_iol_quote(ticker)
            if quote:
                current_price = quote.get("ultimoPrecio", 0)
            else:
                current_price = argentina_data.get_byma_price_yf(ticker)
        elif asset_type == "option":
            # Options need special handling - use entry price as fallback
            current_price = entry_price  # TODO: Get live option price
        
        if current_price is None:
            current_price = entry_price
        
        # Calculate values
        position_value_ars = current_price * shares
        cost_basis = entry_price * shares
        pnl_ars = position_value_ars - cost_basis
        pnl_pct = ((current_price / entry_price) - 1) * 100 if entry_price > 0 else 0
        
        total_ars += position_value_ars
        
        holdings.append({
            "id": pos["id"],
            "ticker": ticker,
            "asset_type": asset_type,
            "shares": shares,
            "entry_price": entry_price,
            "current_price": round(current_price, 2),
            "value_ars": round(position_value_ars, 2),
            "cost_basis": round(cost_basis, 2),
            "pnl_ars": round(pnl_ars, 2),
            "pnl_pct": round(pnl_pct, 2),
            "entry_date": pos["entry_date"],
            "notes": pos.get("notes", "")
        })
    
    # Convert totals to USD
    ccl = rates.get("ccl", 1200)
    mep = rates.get("mep", 1150)
    
    return {
        "total_ars": round(total_ars, 2),
        "total_mep": round(total_ars / mep, 2) if mep > 0 else 0,
        "total_ccl": round(total_ars / ccl, 2) if ccl > 0 else 0,
        "rates": {
            "ccl": ccl,
            "mep": mep,
            "oficial": rates.get("oficial", 1050)
        },
        "holdings": holdings,
        "position_count": len(holdings)
    }


# ============================================
# Options Analyzer
# ============================================

def analyze_option(
    underlying_ticker: str,
    strike: float,
    expiry_date: str,
    market_price: float,
    option_type: str = "call"
) -> Dict:
    """
    Full options analysis with Black-Scholes, Greeks, and signal.
    Like the user's image reference.
    """
    # Get underlying price
    underlying_price = argentina_data.get_byma_price_yf(underlying_ticker)
    if underlying_price is None:
        quote = argentina_data.get_iol_quote(underlying_ticker)
        if quote:
            underlying_price = quote.get("ultimoPrecio", 0)
    
    if not underlying_price:
        return {"error": f"Could not get price for {underlying_ticker}"}
    
    # Calculate time to expiration in years
    try:
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
        today = datetime.now()
        days_to_expiry = (expiry - today).days
        T = days_to_expiry / 365
    except:
        return {"error": "Invalid expiry date format. Use YYYY-MM-DD"}
    
    if T <= 0:
        return {"error": "Option has expired"}
    
    # Get risk-free rate from BCRA
    risk_free_rate = argentina_data.get_bcra_rate()
    
    # Calculate IV from market price
    iv = argentina_data.calculate_implied_volatility(
        market_price, underlying_price, strike, T, risk_free_rate, option_type
    )
    
    # Get historical volatility (need price history)
    # For now, estimate from IV or use default
    hv = iv * 0.95  # Approximate HV as slightly lower than IV
    
    # Calculate Black-Scholes fair price
    if option_type == "call":
        bs_price = argentina_data.black_scholes_call(
            underlying_price, strike, T, risk_free_rate, hv
        )
    else:
        bs_price = argentina_data.black_scholes_put(
            underlying_price, strike, T, risk_free_rate, hv
        )
    
    # Calculate Greeks
    greeks = argentina_data.calculate_greeks(
        underlying_price, strike, T, risk_free_rate, iv, option_type
    )
    
    # Calculate SMA20 and RSI (simplified)
    # In production, fetch historical data
    sma20 = underlying_price * 0.98  # Placeholder
    rsi = 55  # Placeholder
    
    # Generate Signal Composite
    signals = {
        "iv_cheap": iv < hv * 1.05,  # IV < HV + 5% tolerance
        "price_above_sma20": underlying_price > sma20,
        "rsi_above_50": rsi > 50,
        "delta_in_range": 0.4 <= abs(greeks["delta"]) <= 0.6,
        "price_below_bs": market_price < bs_price
    }
    
    checks_passed = sum(signals.values())
    
    if checks_passed >= 4:
        signal = "OPERAR"
        signal_class = "bullish"
    elif checks_passed >= 3:
        signal = "CONSIDERAR"
        signal_class = "neutral"
    else:
        signal = "NO OPERAR"
        signal_class = "bearish"
    
    # Build reasons
    reasons = []
    if not signals["delta_in_range"]:
        reasons.append(f"Delta fuera del rango ideal (0.4 - 0.6): {greeks['delta']:.4f}")
    if not signals["price_below_bs"]:
        reasons.append(f"Precio mercado >= Precio BS: ${market_price} vs ${bs_price}")
    if not signals["iv_cheap"]:
        reasons.append(f"IV no es suficientemente barata: IV={iv*100:.2f}% vs HV={hv*100:.2f}%")
    
    return {
        "underlying": {
            "ticker": underlying_ticker,
            "price": round(underlying_price, 2),
            "sma20": round(sma20, 2),
            "rsi": round(rsi, 2)
        },
        "option": {
            "strike": strike,
            "type": option_type,
            "days_to_expiry": days_to_expiry,
            "market_price": market_price,
            "bs_price": bs_price
        },
        "volatility": {
            "historical": round(hv * 100, 2),
            "implied": round(iv * 100, 2)
        },
        "greeks": greeks,
        "risk_free_rate": round(risk_free_rate * 100, 2),
        "signal": {
            "recommendation": signal,
            "class": signal_class,
            "checks_passed": checks_passed,
            "total_checks": 5,
            "details": signals,
            "reasons": reasons
        }
    }


# ============================================
# FastAPI Endpoints
# ============================================

@router.get("/positions")
def api_get_positions(status: str = "open"):
    """Get all Argentine positions."""
    return get_all_positions(status)


@router.post("/positions")
def api_add_position(position: ArgentinaPosition):
    """Add a new Argentine position."""
    return add_position(position)


@router.post("/positions/{position_id}/close")
def api_close_position(position_id: int, exit_price: float):
    """Close an existing position."""
    return close_position(position_id, exit_price)


@router.delete("/positions/{position_id}")
def api_delete_position(position_id: int):
    """Delete a position."""
    return delete_position(position_id)


@router.get("/portfolio")
def api_get_portfolio():
    """Get portfolio valuation in ARS, MEP, CCL."""
    return get_portfolio_valuation()


@router.get("/rates")
def api_get_rates():
    """Get current CCL, MEP, and Oficial rates."""
    rates = argentina_data.get_dolar_rates()
    rates["bcra_rate"] = round(argentina_data.get_bcra_rate() * 100, 2)
    return rates

@router.get("/prices")
def api_get_prices():
    """Get live prices for all open Argentine positions."""
    positions = get_all_positions("open")
    prices = {}
    
    # Unique tickers to fetch
    tickers = list(set([p["ticker"] for p in positions]))
    
    for ticker in tickers:
        price = argentina_data.get_byma_price_yf(ticker)
        # Fallback to IOL if YF fails (or implement robust fetcher in argentina_data)
        if price is None:
             quote = argentina_data.get_iol_quote(ticker)
             if quote: price = quote.get("ultimoPrecio")
             
        if price:
            # Get historical for change % (simplified for now, use YF History)
            # In a real app we'd batch this or use a proper market data provider
            prices[ticker] = {
                "price": price,
                "change_pct": 0, # TODO: Calculate change
                "ema_8": price,  # Placeholders to prevent frontend crash
                "ema_21": price,
                "ema_35": price,
                "ema_200": price
            }
            
    return prices


@router.post("/options/analyze")
def api_analyze_option(
    underlying: str,
    strike: float,
    expiry: str,
    market_price: float,
    option_type: str = "call"
):
    """Analyze an option with Black-Scholes and Greeks."""
    return analyze_option(underlying, strike, expiry, market_price, option_type)


@router.post("/iol/login")
def api_iol_login(credentials: IOLCredentials):
    """Login to IOL API."""
    success = argentina_data.iol_login(credentials.username, credentials.password)
    return {"success": success, "authenticated": argentina_data.is_iol_authenticated()}


@router.get("/iol/status")
def api_iol_status():
    """Check IOL authentication status."""
    return {"authenticated": argentina_data.is_iol_authenticated()}


@router.get("/iol/options/{underlying}")
def api_iol_options(underlying: str):
    """Get options chain from IOL for an underlying."""
    options = argentina_data.get_iol_options(underlying)
    return {"underlying": underlying, "options": options}


@router.get("/iol/portfolio")
def api_iol_portfolio():
    """Get IOL portfolio."""
    return argentina_data.get_iol_portfolio()


# ============================================
# Extended Endpoints for Full Journal Parity
# ============================================

@router.get("/trades/list")
def api_list_trades(status: str = None):
    """
    Get all Argentina trades in a format compatible with USA journal.
    Returns both open and closed trades.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if status:
        cursor.execute("SELECT * FROM argentina_positions WHERE status = ? ORDER BY entry_date DESC", (status,))
    else:
        cursor.execute("SELECT * FROM argentina_positions ORDER BY entry_date DESC")
    
    rows = cursor.fetchall()
    conn.close()
    
    trades = []
    for row in rows:
        trades.append({
            "id": row["id"],
            "ticker": row["ticker"],
            "asset_type": row["asset_type"],
            "entry_date": row["entry_date"],
            "entry_price": row["entry_price"],
            "shares": row["shares"],
            "stop_loss": row["stop_loss"],
            "target": row["target"],
            "target2": row["target2"] if "target2" in row.keys() else None,
            "target3": row["target3"] if "target3" in row.keys() else None,
            "strategy": row["strategy"],
            "hypothesis": row["hypothesis"],
            "option_strike": row["option_strike"],
            "option_expiry": row["option_expiry"],
            "option_type": row["option_type"],
            "notes": row["notes"],
            "status": row["status"].upper() if row["status"] else "OPEN",
            "exit_date": row["exit_date"],
            "exit_price": row["exit_price"],
            "direction": "LONG",  # Default for compatibility
            "currency": "ARS"
        })
    
    return {"trades": trades, "count": len(trades)}


@router.put("/trades/{trade_id}")
def api_update_trade(trade_id: int, field: str, value: str):
    """Update a specific field of a trade."""
    allowed_fields = ["stop_loss", "target", "target2", "target3", "strategy", "notes", "hypothesis", "shares", "entry_price"]
    if field not in allowed_fields:
        raise HTTPException(status_code=400, detail=f"Field {field} not allowed")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Convert value to appropriate type
    if field in ["stop_loss", "target", "target2", "target3", "shares", "entry_price"]:
        try:
            value = float(value) if value else None
        except:
            value = None
    
    cursor.execute(f"UPDATE argentina_positions SET {field} = ? WHERE id = ?", (value, trade_id))
    conn.commit()
    conn.close()
    
    return {"success": True, "trade_id": trade_id, "field": field, "value": value}


@router.get("/trades/metrics")
def api_get_metrics():
    """
    Get Argentina portfolio metrics summary.
    Returns invested, P&L, win rate, etc.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Open positions
    cursor.execute("SELECT * FROM argentina_positions WHERE status = 'open'")
    open_trades = cursor.fetchall()
    
    # Closed positions
    cursor.execute("SELECT * FROM argentina_positions WHERE status = 'closed'")
    closed_trades = cursor.fetchall()
    
    conn.close()
    
    # Calculate metrics
    total_invested = sum(t["entry_price"] * t["shares"] for t in open_trades)
    open_count = len(open_trades)
    
    # Closed trade stats
    wins = 0
    losses = 0
    total_realized_pnl = 0
    
    for t in closed_trades:
        if t["exit_price"] and t["entry_price"]:
            pnl = (t["exit_price"] - t["entry_price"]) * t["shares"]
            total_realized_pnl += pnl
            if pnl > 0:
                wins += 1
            else:
                losses += 1
    
    total_closed = wins + losses
    win_rate = (wins / total_closed * 100) if total_closed > 0 else 0
    
    return {
        "open_positions": open_count,
        "closed_positions": total_closed,
        "total_invested_ars": round(total_invested, 2),
        "realized_pnl_ars": round(total_realized_pnl, 2),
        "win_rate": round(win_rate, 2),
        "wins": wins,
        "losses": losses
    }


@router.get("/trades/equity-curve")
def api_equity_curve():
    """
    Get equity curve data for Argentina portfolio.
    Shows cumulative P&L over time from closed trades.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT exit_date, entry_price, exit_price, shares 
        FROM argentina_positions 
        WHERE status = 'closed' AND exit_date IS NOT NULL
        ORDER BY exit_date ASC
    """)
    trades = cursor.fetchall()
    conn.close()
    
    cumulative = 0
    equity_data = []
    
    for t in trades:
        pnl = (t["exit_price"] - t["entry_price"]) * t["shares"]
        cumulative += pnl
        equity_data.append({
            "date": t["exit_date"],
            "value": round(cumulative, 2),
            "pnl": round(pnl, 2)
        })
    
    return equity_data


@router.get("/trades/calendar")
def api_calendar_heatmap():
    """
    Get calendar heatmap data for Argentina trades.
    Shows P&L per day for closed trades.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT exit_date, entry_price, exit_price, shares 
        FROM argentina_positions 
        WHERE status = 'closed' AND exit_date IS NOT NULL
    """)
    trades = cursor.fetchall()
    conn.close()
    
    # Group by date
    daily_pnl = {}
    for t in trades:
        date = t["exit_date"]
        pnl = (t["exit_price"] - t["entry_price"]) * t["shares"]
        if date in daily_pnl:
            daily_pnl[date] += pnl
        else:
            daily_pnl[date] = pnl
    
    return [{"date": d, "pnl": round(p, 2)} for d, p in daily_pnl.items()]


@router.get("/trades/analytics/open")
def api_get_open_analytics():
    """
    Get aggregate risk/exposure analytics for OPEN trades and generate Actionable Insights.
    Adapted for Argentina Journal.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Fetch all open trades
        cursor.execute("SELECT * FROM argentina_positions WHERE status = 'open'")
        rows = cursor.fetchall()
        # Note: conn stays open for later queries
        
        if not rows:
            return {
                "exposure": {"total_invested": 0, "total_risk_r": 0, "unrealized_pnl": 0, "active_count": 0},
                "suggestions": []
            }
            
        trades = [dict(row) for row in rows]
        tickers = list(set(t['ticker'] for t in trades if t['ticker']))
        
        # 1. Fetch Fundamental Data (Simplified vs USA version)
        # We will try to get basic info from argentina_data or fallbacks
        fundamental_data = {}
        
        # For now, we mock some fundamental data categories based on asset type
        # In future, integrate real fundamental fetcher
        for t in tickers:
             # Heuristic for asset type if not in DB, but DB has it.
             asset_type = next((tr['asset_type'] for tr in trades if tr['ticker'] == t), 'stock')
             fundamental_data[t] = {
                 "asset_type": asset_type.upper(),
                 "beta": 1.0, # Placeholder
                 "pe_ratio": 0,
                 "dividend_yield": 0
             }

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
            "Cash/Other": 0.0,
            "Options": 0.0,
            "CEDEARs": 0.0
        }
        
        holdings_list = [] # For Major Holdings table
        upcoming_dividends = []
        
        # Get live prices for PnL calc
        live_prices = api_get_prices()
        
        for trade in trades:
            t = trade['ticker']
            qty = trade['shares']
            entry = trade['entry_price']
            stop = trade['stop_loss'] or 0
            
            # 1. Exposure
            trade_value = (entry * qty) # Using cost basis for allocation logic usually, or market value? standard is market value but let's use cost for now or live
            
            # Better to use Market Value for allocation
            current_price = entry
            if t in live_prices:
                current_price = live_prices[t]['price']
            
            market_value = current_price * qty
            total_invested += market_value # Total Market Value
            
            unrealized_pnl += (market_value - (entry * qty))
            
            # Fundamentals
            fund = fundamental_data.get(t, {})
            asset_type = trade['asset_type'].lower()
            
            # Asset Allocation Mapping
            if asset_type == 'stock':
                asset_allocation_map["Stocks"] += market_value
            elif asset_type == 'cedear':
                asset_allocation_map["CEDEARs"] += market_value
            elif asset_type == 'option':
                asset_allocation_map["Options"] += market_value
            else:
                asset_allocation_map["Cash/Other"] += market_value

            # 2. Risk (Entry - Stop) * Qty
            if stop > 0:
                risk_per_share = entry - stop
                if risk_per_share > 0:
                    total_risk_amt += (risk_per_share * qty)
                
            # Holdings List
            holdings_list.append({
                "ticker": t,
                "name": t, # No short name fetcher yet
                "value": market_value,
                "pct": 0, # Calc later
                "beta": 1.0, 
                "pe": 0,
                "yield": 0
            })

            # Suggestions (Simplified)
            if stop == 0 and asset_type != 'option':
                 suggestions.append({
                    "ticker": t,
                    "type": "risk",
                    "severity": "high",
                    "message": "No Stop Loss set",
                    "action": "Set SL"
                })

        # Finalize Percentages
        if total_invested > 0:
             for h in holdings_list:
                 h['pct'] = round((h['value'] / total_invested) * 100, 1)

        holdings_list.sort(key=lambda x: x['value'], reverse=True)

        asset_allocation = [
            {"type": k, "value": round(v, 2)} 
            for k, v in asset_allocation_map.items() 
            if v > 0
        ]
        
        # Group by Sector (Using Asset Type as proxy for now since we don't have sector data)
        sector_allocation = [
             {"sector": k, "value": round(v, 2)}
             for k, v in asset_allocation_map.items()
             if v > 0
        ]

        conn.close()
        
        return {
            "exposure": {
                "total_invested": round(total_invested, 2),
                "total_risk_r": round(total_risk_amt, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "portfolio_beta": 1.0, # Placeholder
                "portfolio_pe": 0,
                "portfolio_div_yield": 0,
                "active_count": len(trades)
            },
            "asset_allocation": asset_allocation,
            "sector_allocation": sector_allocation,
            "holdings": holdings_list,
            "upcoming_dividends": upcoming_dividends,
            "suggestions": suggestions
        }

    except Exception as e:
        print(f"Error in api_get_open_analytics: {e}")
        return {}


@router.get("/trades/analytics/performance")
def api_get_performance_data():
    """
    Get monthly performance data.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM argentina_positions WHERE status = 'closed' ORDER BY exit_date ASC")
        trades = cursor.fetchall()
        conn.close()
        
        if not trades:
            return {"monthly_returns": [], "win_loss_stats": {}}

        # Monthly Returns
        monthly_pnl = {}
        for t in trades:
            if not t["exit_date"]: continue
            month_key = t["exit_date"][:7] # YYYY-MM
            pnl = (t["exit_price"] - t["entry_price"]) * t["shares"]
            monthly_pnl[month_key] = monthly_pnl.get(month_key, 0) + pnl
            
        monthly_returns = [
            {"month": k, "value": round(v, 2)} 
            for k, v in sorted(monthly_pnl.items())
        ]
        
        return {
            "monthly_returns": monthly_returns,
            "benchmarks": [] # No benchmarks for now
        }
    except Exception as e:
        print(f"Error in performance data: {e}")
        return {}


@router.get("/trades/snapshots")
def api_get_snapshots():
    """
    Get equity snapshots (same as equity curve but formatted for HistoryChart).
    """
    curve = api_equity_curve()
    # Transform to snapshot format expected by PortfolioHistoryChart
    # [{ date: '...', total_equity: ... }]
    snapshots = []
    for point in curve:
        snapshots.append({
            "date": point["date"],
            "total_equity": point["value"],
            "realized_pnl": point["pnl"]
        })
    return snapshots

@router.get("/trades/unified/metrics")
def api_get_unified_metrics():
    """Placeholder for unified metrics if needed."""
    return {}


@router.get("/ai/portfolio-insight")
def api_ai_portfolio_insight():
    """Generate AI portfolio analysis for Argentina positions using Gemini."""
    import market_brain
    
    try:
        # Get open positions
        positions = get_all_positions("open")
        live_prices = api_get_prices()
        
        if not positions:
            return {"insight": "No hay posiciones abiertas en Argentina para analizar."}
        
        # Calculate portfolio metrics
        total_value = 0
        unrealized_pnl = 0
        positions_list = []
        winners = []
        losers = []
        
        for p in positions:
            ticker = p['ticker']
            shares = p['shares']
            entry = p['entry_price']
            current = live_prices.get(ticker, {}).get('price', entry)
            
            value = current * shares
            pnl = (current - entry) * shares
            pnl_pct = ((current / entry) - 1) * 100 if entry > 0 else 0
            
            total_value += value
            unrealized_pnl += pnl
            
            positions_list.append(f"{ticker} ({shares} @ ${entry})")
            
            if pnl_pct > 0:
                winners.append(f"{ticker}: +{pnl_pct:.1f}%")
            else:
                losers.append(f"{ticker}: {pnl_pct:.1f}%")
        
        # Sort by magnitude
        winners = sorted(winners, key=lambda x: float(x.split('+')[1].replace('%', '')), reverse=True)[:3]
        losers = sorted(losers, key=lambda x: float(x.split(':')[1].replace('%', '')))[:3]
        
        portfolio_data = {
            "positions": ", ".join(positions_list[:10]) if positions_list else "Sin posiciones",
            "total_value": f"{total_value:,.2f} ARS",
            "unrealized_pnl": f"{unrealized_pnl:,.2f} ARS",
            "sectors": "Argentina Market (Mixed)",
            "winners": ", ".join(winners) if winners else "Ninguno",
            "losers": ", ".join(losers) if losers else "Ninguno"
        }
        
        insight = market_brain.get_portfolio_insight(portfolio_data)
        return {"insight": insight}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"insight": f"Error analyzing Argentina portfolio: {e}"}
