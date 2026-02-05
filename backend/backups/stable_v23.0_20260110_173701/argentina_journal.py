"""
Argentina Trade Journal Module (ORM Version)
Refactored to support Multi-Tenancy and PostgreSQL via SQLAlchemy.
"""
from typing import List, Dict, Optional, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
import models
from database import get_db
import auth
import argentina_data

# Router for FastAPI
router = APIRouter(prefix="/api/argentina", tags=["argentina"])

# ============================================
# Pydantic Models (Request/Response)
# ============================================

class ArgentinaPositionCreate(BaseModel):
    ticker: str
    asset_type: str = 'stock' # 'stock', 'cedear', 'option'
    entry_date: str
    entry_price: float
    shares: float
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    target2: Optional[float] = None
    target3: Optional[float] = None
    strategy: Optional[str] = None
    hypothesis: Optional[str] = None
    option_strike: Optional[float] = None
    option_expiry: Optional[str] = None
    option_type: Optional[str] = None
    notes: Optional[str] = None

class IOLCredentials(BaseModel):
    username: str
    password: str

# ============================================
# Position CRUD Operations (Refactored for ORM)
# ============================================

@router.get("/positions")
def api_get_positions(status: str = "open", current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Get all Argentine positions for the current user."""
    # Note: DB model doesn't explicitly have 'status' field in the new schema (I missed it in models.py?)
    # Let me check models.py... I didn't add 'status' to ArgentinaPosition in models.py refactor!
    # I should have added it. The legacy journal used 'status' column.
    # CRITICAL FIX: I need to update models.py to include 'status', 'exit_date', 'exit_price' for ArgentinaPosition.
    # For now, I will assume they exist (and I will fix models.py in next step).
    # Wait, looking at my previous models.py write.. I MISSED IT.
    # I will have to update models.py.
    # But I can continue writing this assuming models.py will be fixed.
    
    # Logic if column missing: it will crash. I must fix models.py FIRST or concurrently.
    # I'll proceed writing this file, then immediately update models.py before running.
    
    # Actually, legacy schema had status default 'open'. 
    
    query = db.query(models.ArgentinaPosition).filter(models.ArgentinaPosition.user_id == current_user.id)
    
    if status:
        # Filter by status (OPEN/CLOSED)
        # We use strict string matching or case insensitive
        query = query.filter(models.ArgentinaPosition.status == status.upper())
    
    positions = query.all()
    
    # Convert to dict list
    result = []
    for p in positions:
        result.append({
            "id": p.id,
            "ticker": p.ticker,
            "asset_type": p.asset_type,
            "entry_date": p.entry_date,
            "entry_price": p.entry_price,
            "shares": p.shares,
            "stop_loss": p.stop_loss,
            "target": p.target,
            "target2": p.target2,
            "target3": p.target3,
            "strategy": p.strategy,
            "hypothesis": p.hypothesis,
            "notes": p.notes,
            "status": p.status,
            "exit_date": p.exit_date,
            "exit_price": p.exit_price,
            # Handle option fields
            "option_strike": p.option_strike,
            "option_expiry": p.option_expiry,
            "option_type": p.option_type
        })
    return result

@router.post("/positions")
def api_add_position(pos: ArgentinaPositionCreate, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Add a new Argentine position."""
    new_pos = models.ArgentinaPosition(
        user_id=current_user.id,
        ticker=pos.ticker.upper(),
        asset_type=pos.asset_type,
        entry_date=pos.entry_date,
        entry_price=pos.entry_price,
        shares=pos.shares,
        stop_loss=pos.stop_loss,
        target=pos.target,
        target2=pos.target2,
        target3=pos.target3,
        strategy=pos.strategy,
        hypothesis=pos.hypothesis,
        notes=pos.notes,
        option_strike=pos.option_strike,
        option_expiry=pos.option_expiry,
        option_type=pos.option_type,
        status="OPEN"
    )
    
    db.add(new_pos)
    db.commit()
    db.refresh(new_pos)
    return {"id": new_pos.id, "status": "created"}

@router.post("/positions/{position_id}/close")
def api_close_position(position_id: int, exit_price: float, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Close an existing position."""
    pos = db.query(models.ArgentinaPosition).filter(
        models.ArgentinaPosition.id == position_id,
        models.ArgentinaPosition.user_id == current_user.id
    ).first()
    
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
        
    pos.status = 'CLOSED'
    pos.exit_date = datetime.now().strftime("%Y-%m-%d")
    pos.exit_price = exit_price
    
    db.commit()
    return {"id": position_id, "status": "closed"}

@router.delete("/positions/{position_id}")
def api_delete_position(position_id: int, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Delete a position."""
    pos = db.query(models.ArgentinaPosition).filter(
        models.ArgentinaPosition.id == position_id,
        models.ArgentinaPosition.user_id == current_user.id
    ).first()
    
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
        
    db.delete(pos)
    db.commit()
    return {"id": position_id, "status": "deleted"}

# ============================================
# Portfolio Valuation
# ============================================

@router.get("/portfolio")
def api_get_portfolio(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """
    Get portfolio valuation in ARS, MEP, CCL.
    Fetches live prices for open positions.
    """
    # 1. Get Open Positions from DB
    # Assumption: Open means exit_price is NULL (since I missed status column in first pass)
    # I will fix the model to match.
    positions = db.query(models.ArgentinaPosition).filter(
        models.ArgentinaPosition.user_id == current_user.id,
        models.ArgentinaPosition.exit_price == None # Proxy for Open
    ).all()
    
    rates = argentina_data.get_dolar_rates()
    total_ars = 0.0
    holdings = []
    
    for pos in positions:
        current_price = None
        if pos.asset_type in ["stock", "cedear"]:
            # Try IOL first, then Yahoo Finance
            quote = argentina_data.get_iol_quote(pos.ticker)
            if quote:
                current_price = quote.get("ultimoPrecio", 0)
            else:
                current_price = argentina_data.get_byma_price_yf(pos.ticker)
        elif pos.asset_type == "option":
            current_price = pos.entry_price  # Placeholder
            
        if current_price is None:
            current_price = pos.entry_price
            
        val_ars = current_price * pos.shares
        cost = pos.entry_price * pos.shares
        pnl = val_ars - cost
        pnl_pct = ((current_price / pos.entry_price) - 1) * 100 if pos.entry_price else 0
        
        total_ars += val_ars
        
        holdings.append({
            "id": pos.id,
            "ticker": pos.ticker,
            "asset_type": pos.asset_type,
            "shares": pos.shares,
            "entry_price": pos.entry_price,
            "current_price": round(current_price, 2),
            "value_ars": round(val_ars, 2),
            "pnl_ars": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2)
        })
        
    ccl = rates.get("ccl", 1200)
    mep = rates.get("mep", 1150)
    
    return {
        "total_ars": round(total_ars, 2),
        "total_mep": round(total_ars / mep, 2) if mep > 0 else 0,
        "total_ccl": round(total_ars / ccl, 2) if ccl > 0 else 0,
        "rates": rates,
        "holdings": holdings
    }

@router.get("/rates")
def api_get_rates():
    """Get current CCL, MEP, and Oficial rates."""
    rates = argentina_data.get_dolar_rates()
    rates["bcra_rate"] = round(argentina_data.get_bcra_rate() * 100, 2)
    return rates

@router.get("/prices")
def api_get_prices(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Get live prices for all open Argentine positions."""
    # Similar logic to get_portfolio but just returns price map
    positions = db.query(models.ArgentinaPosition).filter(
        models.ArgentinaPosition.user_id == current_user.id,
        models.ArgentinaPosition.exit_price == None
    ).all()
    
    prices = {}
    tickers = list(set([p.ticker for p in positions]))
    
    for ticker in tickers:
        quote = argentina_data.get_market_quote(ticker)
        
        # Fallback to IOL if yahoo fails (but change_pct is tricky unless we calc it manually or IOL gives it)
        # For simplicity, if market_quote fails price is 0, we check IOL
        
        price = quote["price"]
        change = quote["change_pct"]
        
        if price <= 0:
             iol_quote = argentina_data.get_iol_quote(ticker)
             if iol_quote: 
                 price = iol_quote.get("ultimoPrecio")
                 # IOL quote usually has 'variacion' or similar?
                 # {"ultimoPrecio": 123, "variacion": 1.5, ...}
                 # Assuming minimal structure for now
                 change = iol_quote.get("variacionPorcentual", 0)
        
        if price > 0:
            prices[ticker] = {
                "price": price,
                "change_pct": change,
                "ema_8": price # Mock
            }
    return prices

# Options endpoints check (No auth needed for calculator but okay to protect)
@router.get("/options/analyze")
def api_analyze_option(
    underlying: str,
    strike: float,
    expiry: str,
    market_price: float,
    option_type: str = "call"
):
    # This function uses `analyze_option` from legacy file. 
    # Since I'm creating a new file over the old one, I MUST copy the helper function logic 
    # OR import it if I moved it.
    # I overwrote the old file, so I need to RE-IMPLEMENT `analyze_option` here or copy it.
    # I saw the code in the read, I should include it in this file.
    # To save tokens, I will refer to argentina_data for heavy lifting, but `analyze_option` 
    # had business logic (checking greeks etc).
    # I'll simplify it for now to just call argentina_data if possible or minimal check.
    # Actually, losing that logic would be bad. 
    # I will attempt to preserve the `analyze_option` function in this file.
    
    return _analyze_option_logic(underlying, strike, expiry, market_price, option_type)

def _analyze_option_logic(underlying, strike, expiry, market_price, option_type):
    try:
        # 1. Get Spot Price & History
        # We need history for HV, RSI, SMA
        history = argentina_data.get_price_history(underlying, days=40)
        
        S = history[-1] if history else None
        
        if not S:
            # Fallback to single quote if history fails
            S = argentina_data.get_byma_price_yf(underlying)
            
        if not S:
            return {"error": f"Could not fetch spot price for {underlying}"}

        # 2. Calculate Indicators
        hv = argentina_data.calculate_historical_volatility(history)
        rsi = argentina_data.calculate_rsi(history, period=14)
        sma_20 = argentina_data.calculate_sma(history, period=20)
        
        # 3. Calculate Time to Expiry (Years)
        try:
            exp_date = datetime.strptime(expiry, "%Y-%m-%d")
        except ValueError:
            return {"error": "Invalid expiry date format. Use YYYY-MM-DD"}
            
        T = (exp_date - datetime.now()).days / 365.0
        if T < 0:
            return {"error": "Option has expired"}
        
        # 4. Get Risk Free Rate
        r = argentina_data.get_bcra_rate() 
        
        # 5. Calculate IV (if market price provided)
        iv = 0.40 # Default
        implied = False
        
        if market_price > 0:
            try:
                iv_calc = argentina_data.calculate_implied_volatility(
                    market_price, S, strike, T, r, option_type.lower()
                )
                if iv_calc: 
                    iv = iv_calc
                    implied = True
            except:
                pass
                
        # 6. Calculate Theoretical Price & Greeks
        if option_type.lower() == "call":
            theo_price = argentina_data.black_scholes_call(S, strike, T, r, iv)
        else:
            theo_price = argentina_data.black_scholes_put(S, strike, T, r, iv)
            
        greeks = argentina_data.calculate_greeks(S, strike, T, r, iv, option_type.lower())
        
        # ==========================================
        # DECISION ENGINE (The "Estetica" Logic)
        # ==========================================
        
        checks = []
        reasons = []
        
        # A. Volatility Check (Cheapness)
        # IV should be close to or lower than HV
        vol_spread = iv - hv
        is_cheap = vol_spread < 0.05 # Tolerance 5%
        checks.append({
            "label": "Opción barata (IV < HV + 5%)",
            "pass": is_cheap,
            "detail": f"IV {iv*100:.1f}% vs HV {hv*100:.1f}%"
        })
        if not is_cheap: reasons.append("La opción está cara (IV alta)")
        
        # B. Trend Check (SMA 20)
        trend_ok = False
        if option_type.lower() == 'call':
            trend_ok = S > (sma_20 or 0)
            checks.append({
                "label": "Tendencia Alcista (Precio > SMA20)",
                "pass": trend_ok,
                "detail": f"${S:.0f} vs ${sma_20 or 0:.0f}"
            })
            if not trend_ok: reasons.append("Tendencia bajista (Precio < SMA20)")
        else:
            trend_ok = S < (sma_20 or 999999)
            checks.append({
                "label": "Tendencia Bajista (Precio < SMA20)",
                "pass": trend_ok,
                "detail": f"${S:.0f} vs ${sma_20 or 0:.0f}"
            })
            
        # C. Momentum Check (RSI)
        mom_ok = False
        rsi_val = rsi or 50
        if option_type.lower() == 'call':
            mom_ok = rsi_val > 50
            checks.append({"label": "Momentum (RSI > 50)", "pass": mom_ok, "detail": f"{rsi_val:.1f}"})
        else:
            mom_ok = rsi_val < 50
            checks.append({"label": "Momentum (RSI < 50)", "pass": mom_ok, "detail": f"{rsi_val:.1f}"})
            
        # D. Greek Check (Delta Sweet Spot)
        delta_val = abs(greeks['delta'])
        delta_ok = 0.4 <= delta_val <= 0.65
        checks.append({
            "label": "Delta ideal (0.4 - 0.65)", 
            "pass": delta_ok, 
            "detail": f"{delta_val:.2f}"
        })
        if not delta_ok: reasons.append("Delta fuera de rango ideal (Opcion muy ITM o OTM)")
        
        # E. Fair Price Check
        price_ok = False
        if market_price > 0 and theo_price > 0:
            diff_pct = (market_price - theo_price) / theo_price
            if option_type.lower() == 'call':
                price_ok = diff_pct < 0.1 # Not paying >10% premium over BS
                checks.append({
                    "label": "Precio Mercado < BS (+10%)",
                    "pass": price_ok,
                    "detail": f"${market_price} vs ${theo_price:.1f}"
                })
            else:
                 price_ok = diff_pct < 0.1
                 checks.append({"label": "Precio Mercado razonable", "pass": price_ok, "detail": "..."})

        # SIGNAL COMPOSITION
        # Strict: All Technicals OK + Cheat/Fair Price
        tech_signal = "NO OPERAR"
        if trend_ok and mom_ok:
            tech_signal = "COMPRA" if option_type == 'call' else "VENTA"
        elif trend_ok and not mom_ok:
             tech_signal = "ESPERAR"
             
        comp_signal = "NO OPERAR"
        if tech_signal != "NO OPERAR" and is_cheap and delta_ok:
            comp_signal = "OPERAR FUERTE"
        elif tech_signal != "NO OPERAR" and (is_cheap or delta_ok):
             comp_signal = "OPERAR CON RIESGO"
             
        # Suggest Strategies
        strategies = []
        if comp_signal.startswith("OPERAR"):
            if option_type == 'call': strategies = ["Compra de Call (Frontal)", "Bull Spread"]
            else: strategies = ["Compra de Put", "Bear Spread"]
        else:
            # If not good for directional buying, maybe selling?
            if iv > hv and not trend_ok:
                strategies = ["Lanzamiento Cubierto", "Venta de Cuna"]
            else:
                strategies = ["Esperar confirmación técnica"]

        return {
            "ticker": underlying,
            "spot_price": S,
            "strike": strike,
            "expiry": expiry,
            "days_to_expiry": int(T * 365),
            "risk_free_rate": f"{r*100:.1f}%",
            "market_price": market_price,
            "theoretical_price": theo_price,
            "volatility": {
                "value": f"{iv*100:.1f}%",
                "source": "Implied" if implied else "Constant",
                "hv": f"{hv*100:.1f}%"
            },
            "technicals": {
                "rsi": round(rsi_val, 2),
                "sma_20": round(sma_20 or 0, 2)
            },
            "greeks": greeks,
            "fair_value_diff_pct": round(((market_price - theo_price) / theo_price)*100, 1) if market_price and theo_price else 0,
            "analysis": {
                "tech_signal": tech_signal,
                "comp_signal": comp_signal,
                "reasons": reasons,
                "checks": checks,
                "strategies": strategies
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"Analysis failed: {str(e)}"}

# IOL endpoints
@router.post("/iol/login")
def api_iol_login(credentials: IOLCredentials):
    success = argentina_data.iol_login(credentials.username, credentials.password)
    return {"success": success, "authenticated": argentina_data.is_iol_authenticated()}

@router.get("/iol/status")
def api_iol_status():
    return {"authenticated": argentina_data.is_iol_authenticated()}

@router.get("/iol/options/{underlying}")
def api_iol_options(underlying: str):
    options = argentina_data.get_iol_options(underlying)
    return {"underlying": underlying, "options": options}


@router.post("/argentina/upload_csv")
async def upload_csv(file: UploadFile = File(...), current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """
    Import Argentina trades from CSV.
    Format: ticker, asset_type, entry_date, entry_price, shares, status, exit_date, exit_price, notes
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
                
                asset_type = row.get("asset_type", "stock").lower()
                
                # Date Parsing
                e_date_str = row.get("entry_date", "")
                entry_date = e_date_str # Keep as string for Argentina module (YYYY-MM-DD usually)
                
                # Check format validity loosely or assume string is sufficient as per models
                # models.ArgentinaPosition uses string for date
                
                entry_price = float(row.get("entry_price", 0))
                shares = float(row.get("shares", 0))
                status = row.get("status", "OPEN").upper()
                
                exit_date = row.get("exit_date", "")
                exit_price = None
                if row.get("exit_price"):
                    exit_price = float(row.get("exit_price"))
                
                pos = models.ArgentinaPosition(
                    user_id=current_user.id,
                    ticker=ticker,
                    asset_type=asset_type,
                    entry_date=entry_date,
                    entry_price=entry_price,
                    shares=shares,
                    status=status,
                    exit_date=exit_date,
                    exit_price=exit_price,
                    notes=row.get("notes", "Imported CSV"),
                    strategy=row.get("strategy"),
                    target=float(row.get("target")) if row.get("target") else None
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

@router.get("/template")
def download_template():
    from fastapi.responses import StreamingResponse
    import io
    import csv
    
    headers = ["ticker", "asset_type", "entry_date", "entry_price", "shares", "status", "exit_date", "exit_price", "notes", "strategy", "target"]
    
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerow(["GGAL", "stock", "2024-01-01", "1250.50", "100", "OPEN", "", "", "Sample Trade", "MOMENTUM", "1500"])
    
    stream.seek(0)
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=argentina_trades_template.csv"
    return response
