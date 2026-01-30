"""
Portfolio Snapshots Module (ORM Version)
Twice-migrated to support Multi-Tenancy and PostgreSQL via SQLAlchemy.
"""

from datetime import datetime, timedelta
import threading
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
import models
from database import SessionLocal

# Lock mainly for safety if we had file IO, less critical with specialized DB sessions but good practice
_monitor_lock = threading.Lock()

def take_snapshot(user_id: int = None, db: Session = None):
    """
    Take a snapshot of the portfolio state.
    
    Args:
        user_id (int, optional): ID of specific user to snapshot. 
                                 If None, snapshots ALL users (for scheduled tasks).
        db (Session, optional): Database session. If None, creates a new one.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
        
    try:
        # Determine target users
        target_users = []
        if user_id:
            user = db.query(models.User).filter(models.User.id == user_id).first()
            if user:
                target_users.append(user)
        else:
            target_users = db.query(models.User).all()
            
        today_str = datetime.now().strftime("%Y-%m-%d")
        results = []

        for user in target_users:
            print(f"[Snapshot] Processing user {user.email} (ID: {user.id})...")
            
            # 1. Fetch unified metrics for THIS user
            # We need to call the logic that calculates metrics. 
            # Ideally, we call a service function, not an HTTP endpoint to avoid recursion/auth complexity.
            # Importing here to avoid circular dependencies if possible.
            import trade_journal
            import crypto_journal
            import argentina_journal
            
            # --- USA Metrics ---
            # We need a version of get_unified_metrics that accepts a user_id or db session + filter
            # For now, let's assume valid access to models directly
            
            # USA (Trades)
            usa_query = db.query(models.Trade).filter(
                models.Trade.user_id == user.id,
                models.Trade.status == "OPEN"
            ).all()
            
            usa_invested = sum(t.entry_price * t.shares for t in usa_query)
            # Current value requires live price... for fast snapshot, might be stale if market closed.
            # Using entry price + PnL equivalent if current price not stored? 
            # Trade model doesn't store 'current_price' persistently, it's fetched live.
            # For snapshot efficiency, we might need a helper to get latest prices.
            # Reuse market_data logic?
            # For this MVP refactor, let's calculate based on what we have or fetch live.
            # Fetching live for every user might be slow. 
            # Let's try to use the existing `trade_journal.calculate_metrics` if generic enough.
            # BUT `trade_journal` is not yet refactored to accept user_id. 
            # I will implement basic calculation here to break dependency loops.
            
            usa_value = usa_invested # Placeholder until we fetch prices
            usa_pnl = 0
            
            # Try to get better values if possible
            try:
                # We can't easily call HTTP here because we need Auth token for that user.
                # So we must calculate internally.
                pass 
            except:
                pass

            # --- Argentina Metrics ---
            # Argentina positions are in ARS - must convert to USD using CCL rate
            arg_query = db.query(models.ArgentinaPosition).filter(models.ArgentinaPosition.user_id == user.id).all()
            arg_invested_ars = sum(p.entry_price * p.shares for p in arg_query)
            
            # Get CCL rate for conversion
            try:
                import argentina_data
                rates = argentina_data.get_dolar_rates()
                ccl_rate = rates.get('ccl', 1200)  # Default to 1200 if not available
            except:
                ccl_rate = 1200
            
            # Convert ARS to USD
            arg_invested = arg_invested_ars / ccl_rate if ccl_rate > 0 else 0
            arg_value = arg_invested 
            arg_pnl = 0

            # --- Crypto Metrics ---
            crypto_query = db.query(models.CryptoPosition).filter(models.CryptoPosition.user_id == user.id).all()
            crypto_invested = sum(p.amount * p.entry_price for p in crypto_query)
            crypto_value = sum(p.amount * (p.current_price or p.entry_price) for p in crypto_query)
            crypto_pnl = crypto_value - crypto_invested

            # Totals
            total_invested = usa_invested + arg_invested + crypto_invested
            total_value = usa_value + arg_value + crypto_value
            total_pnl = total_value - total_invested
            total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
            
            # Create/Update Snapshot
            # Check if exists for today
            existing = db.query(models.PortfolioSnapshot).filter(
                models.PortfolioSnapshot.user_id == user.id,
                models.PortfolioSnapshot.date == today_str
            ).first()
            
            if existing:
                existing.total_invested_usd = total_invested
                existing.total_value_usd = total_value
                existing.total_pnl_usd = total_pnl
                existing.total_pnl_pct = total_pnl_pct
                existing.usa_invested_usd = usa_invested
                existing.usa_value_usd = usa_value
                existing.usa_pnl_usd = usa_pnl
                # ... others
                existing.created_at = datetime.now()
            else:
                snapshot = models.PortfolioSnapshot(
                    user_id=user.id,
                    date=today_str,
                    total_invested_usd=total_invested,
                    total_value_usd=total_value,
                    total_pnl_usd=total_pnl,
                    total_pnl_pct=total_pnl_pct,
                    usa_invested_usd=usa_invested,
                    usa_value_usd=usa_value,
                    usa_pnl_usd=usa_pnl,
                    argentina_invested_usd=arg_invested,
                    argentina_value_usd=arg_value,
                    argentina_pnl_usd=arg_pnl,
                    crypto_invested_usd=crypto_invested,
                    crypto_value_usd=crypto_value,
                    crypto_pnl_usd=crypto_pnl
                )
                db.add(snapshot)
            
            results.append({"user": user.email, "status": "success"})
            
        db.commit()
        return results

    except Exception as e:
        print(f"[Snapshot] Error: {e}")
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        if close_db:
            db.close()

import math

def clean_nan(val, default=0):
    """Replace NaN/None values with default for JSON serialization"""
    if val is None:
        return default
    try:
        if math.isnan(val) or math.isinf(val):
            return default
    except (TypeError, ValueError):
        pass
    return val

def get_history(user_id: int, days: int = 365, db: Session = None):
    """Get portfolio history for a specific user."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
        
    try:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        snapshots = db.query(models.PortfolioSnapshot).filter(
            models.PortfolioSnapshot.user_id == user_id,
            models.PortfolioSnapshot.date >= cutoff
        ).order_by(models.PortfolioSnapshot.date.asc()).all()
        
        # Build history with calculated daily changes
        history = []
        prev_value = None
        for s in snapshots:
            current_value = clean_nan(s.total_value_usd) or 0
            daily_change = 0
            daily_change_pct = 0
            
            if prev_value is not None and prev_value > 0:
                daily_change = current_value - prev_value
                daily_change_pct = (daily_change / prev_value) * 100
            
            history.append({
                "date": s.date,
                "total_invested_usd": clean_nan(s.total_invested_usd),
                "total_value_usd": clean_nan(s.total_value_usd),
                "total_pnl_usd": clean_nan(s.total_pnl_usd),
                "total_pnl_pct": clean_nan(s.total_pnl_pct),
                "usa_invested_usd": clean_nan(s.usa_invested_usd),
                "usa_value_usd": clean_nan(s.usa_value_usd),
                "usa_pnl_usd": clean_nan(s.usa_pnl_usd),
                # Argentina
                "argentina_invested_usd": clean_nan(s.argentina_invested_usd),
                "argentina_value_usd": clean_nan(s.argentina_value_usd),
                "argentina_pnl_usd": clean_nan(s.argentina_pnl_usd),
                # Crypto
                "crypto_invested_usd": clean_nan(s.crypto_invested_usd),
                "crypto_value_usd": clean_nan(s.crypto_value_usd),
                "crypto_pnl_usd": clean_nan(s.crypto_pnl_usd),
                # Additional fields for frontend charts
                "total_equity": current_value,
                "dailyChange": round(daily_change, 2),
                "dailyChangePct": round(daily_change_pct, 2)
            })
            prev_value = current_value
        
        return history
    finally:
        if close_db:
            db.close()

def get_latest(user_id: int, db: Session = None):
    """Get latest snapshot for a user."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        s = db.query(models.PortfolioSnapshot).filter(
            models.PortfolioSnapshot.user_id == user_id
        ).order_by(models.PortfolioSnapshot.date.desc()).first()
        if not s:
            return None
        return {
            "date": s.date,
            "total_invested_usd": clean_nan(s.total_invested_usd),
            "total_value_usd": clean_nan(s.total_value_usd),
            "total_pnl_usd": clean_nan(s.total_pnl_usd),
            "total_pnl_pct": clean_nan(s.total_pnl_pct),
            "usa_value_usd": clean_nan(s.usa_value_usd),
            "argentina_value_usd": clean_nan(s.argentina_value_usd),
            "crypto_value_usd": clean_nan(s.crypto_value_usd),
        }
    finally:
        if close_db:
            db.close()

def get_geographic_distribution(user_id: int, db: Session = None):
    """
    Get geographic distribution for a user.
    - CEDEARs are classified by their underlying country (from DB or fallback mapping)
    - Crypto is EXCLUDED from geographic distribution
    - Only includes trades and argentina_positions
    """
    import price_service
    
    # CEDEAR origin mapping (fallback for positions without underlying_country)
    CEDEAR_ORIGINS = {
        # USA
        'AAPL': 'usa', 'MSFT': 'usa', 'GOOGL': 'usa', 'GOOG': 'usa', 'AMZN': 'usa', 'TSLA': 'usa',
        'META': 'usa', 'NVDA': 'usa', 'NFLX': 'usa', 'AMD': 'usa', 'INTC': 'usa', 'PYPL': 'usa',
        'DIS': 'usa', 'KO': 'usa', 'PEP': 'usa', 'MCD': 'usa', 'NKE': 'usa', 'BA': 'usa',
        'JPM': 'usa', 'GS': 'usa', 'V': 'usa', 'MA': 'usa', 'WMT': 'usa', 'HD': 'usa',
        'PFE': 'usa', 'JNJ': 'usa', 'MRNA': 'usa', 'CVX': 'usa', 'XOM': 'usa', 'T': 'usa',
        'VZ': 'usa', 'SBUX': 'usa', 'UBER': 'usa', 'ABNB': 'usa', 'COIN': 'usa', 'SQ': 'usa',
        'SNAP': 'usa', 'SPOT': 'usa', 'ZM': 'usa', 'DOCU': 'usa', 'SHOP': 'usa', 'ETSY': 'usa',
        'SPY': 'usa', 'QQQ': 'usa', 'ARKK': 'usa', 'MELI': 'usa', 'GLOB': 'usa', 'MSTR': 'usa',
        # Brasil
        'VALE': 'brasil', 'PBR': 'brasil', 'ITUB': 'brasil', 'BBD': 'brasil', 'ABEV': 'brasil',
        # China
        'BABA': 'china', 'JD': 'china', 'PDD': 'china', 'BIDU': 'china', 'NIO': 'china',
        'XPEV': 'china', 'LI': 'china', 'TME': 'china',
        # Europe
        'SAP': 'europa', 'ASML': 'europa', 'NVO': 'europa', 'AZN': 'europa', 'BP': 'europa',
        'HSBC': 'europa', 'UL': 'europa', 'DEO': 'europa',
    }
    
    # Normalize country names from DB to our internal keys
    COUNTRY_NORMALIZE = {
        'USA': 'usa', 'United States': 'usa',
        'Brazil': 'brasil', 'Brasil': 'brasil',
        'China': 'china',
        'Europe': 'europa', 'Germany': 'europa', 'United Kingdom': 'europa', 
        'France': 'europa', 'Spain': 'europa', 'Italy': 'europa',
        'Switzerland': 'europa', 'Netherlands': 'europa',
        'Argentina': 'argentina',
        'Japan': 'japan',
        'South Korea': 'south_korea', 'Korea': 'south_korea',
        'India': 'india',
        'Mexico': 'mexico',
    }
    
    # Initialize distribution
    distribution = {
        'usa': {'value': 0, 'count': 0},
        'brasil': {'value': 0, 'count': 0},
        'china': {'value': 0, 'count': 0},
        'europa': {'value': 0, 'count': 0},
        'argentina': {'value': 0, 'count': 0},
        'japan': {'value': 0, 'count': 0},
        'south_korea': {'value': 0, 'count': 0},
        'india': {'value': 0, 'count': 0},
        'mexico': {'value': 0, 'count': 0},
    }
    
    # Get CCL rate for Argentina ARS to USD conversion
    try:
        import argentina_data
        rates = argentina_data.get_dolar_rates()
        ccl_rate = rates.get('ccl', 1200)
    except:
        ccl_rate = 1200
    
    # 1. Get USA direct trades
    usa_trades = db.query(models.Trade).filter(
        models.Trade.user_id == user_id,
        models.Trade.status == "OPEN"
    ).all()
    
    for t in usa_trades:
        if not t.ticker:
            continue
        # All USA direct trades are classified as USA (values already in USD)
        value = (t.entry_price or 0) * (t.shares or 0)
        distribution['usa']['value'] += value
        distribution['usa']['count'] += 1
    
    # 2. Get Argentina positions (CEDEARs and local stocks)
    arg_positions = db.query(models.ArgentinaPosition).filter(
        models.ArgentinaPosition.user_id == user_id,
        models.ArgentinaPosition.status == "OPEN"
    ).all()
    
    for pos in arg_positions:
        if not pos.ticker:
            continue
        ticker_upper = pos.ticker.upper().replace('.BA', '')
        # Argentina values are in ARS - convert to USD
        value_ars = (pos.entry_price or 0) * (pos.shares or 0)
        value = value_ars / ccl_rate if ccl_rate > 0 else 0
        
        # Priority 1: Use underlying_country from DB (auto-detected when position was created)
        origin = None
        if pos.underlying_country:
            origin = COUNTRY_NORMALIZE.get(pos.underlying_country, pos.underlying_country.lower())
        
        # Priority 2: Fallback to hardcoded mapping for CEDEARs
        if not origin or origin not in distribution:
            origin = CEDEAR_ORIGINS.get(ticker_upper)
        
        # Priority 3: Default to Argentina for unknown local stocks
        if not origin or origin not in distribution:
            origin = 'argentina'
        
        distribution[origin]['value'] += value
        distribution[origin]['count'] += 1
    
    # Calculate total (excluding crypto)
    total = sum(d['value'] for d in distribution.values()) or 1
    
    # Calculate percentages and filter empty regions
    result = {}
    for region, data in distribution.items():
        if data['value'] > 0 or data['count'] > 0:
            result[region] = {
                'value': round(data['value'], 2),
                'count': data['count'],
                'pct': round((data['value'] / total) * 100, 2)
            }
    
    return result

def rebuild_history(user_id: int, db: Session):
    """
    Rebuild historical snapshots based on trade history.
    Iterates from the first trade date to today, calculating daily metrics.
    """
    try:
        print(f"[Snapshots] Rebuilding history for user {user_id}...")
        
        # 1. Fetch all trades
        trades = db.query(models.Trade).filter(
            models.Trade.user_id == user_id
        ).all()
        
        if not trades:
            print("No trades found.")
            return
            
        # 2. Determine date range
        # Use simple date format matching
        dates = []
        for t in trades:
            if isinstance(t.entry_date, str):
                try: dates.append(datetime.strptime(t.entry_date, "%Y-%m-%d").date())
                except: pass
            else:
                dates.append(t.entry_date)
                
        if not dates: return
        
        start_date = min(dates)
        # SANITY CHECK: Don't process dates significantly in the past (e.g. bad CSV imports with year 0001)
        if start_date.year < 2000:
            print(f"[Snapshots] Warning: Found suspiciously old date {start_date}. Clamping to 2020-01-01.")
            from datetime import date
            start_date = date(2020, 1, 1) # Default to recent history if bad dates found

        end_date = datetime.now().date()
        
        print(f"[Snapshots] Rebuilding from {start_date} to {end_date}")

        # 3. Iterate days
        current = start_date
        batch_counter = 0
        while current <= end_date:
            curr_str = current.strftime("%Y-%m-%d")
            
            # Calculate state for this day
            daily_invested = 0
            daily_pnl = 0
            
            # Filter trades active/closed on this day
            # Assuming 'entry_date' and 'exit_date' are Date objects or ISO strings
            
            for t in trades:
                # Parse Dates
                t_entry = t.entry_date
                if isinstance(t_entry, str):
                    try: t_entry = datetime.strptime(t_entry, "%Y-%m-%d").date()
                    except: continue # Skip invalid
                
                t_exit = None
                if t.exit_date:
                    if isinstance(t.exit_date, str):
                        try: t_exit = datetime.strptime(t.exit_date, "%Y-%m-%d").date()
                        except: pass
                    else:
                        t_exit = t.exit_date
                
                # Logic:
                # Is active? Entry <= current AND (Exit is None OR Exit > current)
                # Is closed? Exit <= current
                
                is_active = t_entry <= current and (t_exit is None or t_exit > current)
                is_closed = t_exit is not None and t_exit <= current
                
                if is_active:
                    daily_invested += (t.entry_price * t.shares)
                
                if is_closed:
                    if t.pnl is not None:
                        daily_pnl += t.pnl
                        
            # Calc Totals
            # Value = Invested + Realized PnL (ignoring historical unrealized for simplicity)
            daily_value = daily_invested + daily_pnl 
            
            # Update/Create Snapshot
            # Ideally we check if it exists or we wipe all first. Wiping is risky if we break running stats.
            # Upsert is safer.
            snapshot = db.query(models.PortfolioSnapshot).filter(
                models.PortfolioSnapshot.user_id == user_id,
                models.PortfolioSnapshot.date == curr_str
            ).first()
            
            if not snapshot:
                snapshot = models.PortfolioSnapshot(
                    user_id=user_id,
                    date=curr_str
                )
                db.add(snapshot)
            
            # Update fields (USA only for now as this is triggered by Import USA)
            # We preserve specific fields if we want, but "Global" usually implies sum.
            # For this "Fix", we assume these CSV imports are USA Stocks.
            
            snapshot.usa_invested_usd = daily_invested
            snapshot.usa_pnl_usd = daily_pnl
            snapshot.usa_value_usd = daily_value
            
            # Update Global Totals (assuming other assets 0 for these historical days, or we leave them alone?)
            # Safer to sum them if we have ARG data, but ARG data might not be historical in this loop.
            # We'll just update totals to match USA for now to ensure chart works.
            # If we had Arg data we should sum it.
            # Update Global Totals
            snapshot.total_invested_usd = snapshot.usa_invested_usd + (snapshot.argentina_invested_usd or 0) + (snapshot.crypto_invested_usd or 0)
            snapshot.total_pnl_usd = snapshot.usa_pnl_usd + (snapshot.argentina_pnl_usd or 0) + (snapshot.crypto_pnl_usd or 0)
            snapshot.total_value_usd = snapshot.total_invested_usd + snapshot.total_pnl_usd
            
            # Batch commit to prevent massive transactions
            batch_counter += 1
            if batch_counter >= 30:
                db.commit()
                batch_counter = 0
            
            current += timedelta(days=1)
            
        db.commit()
        print(f"[Snapshots] Rebuild complete for user {user_id}")
            
    except Exception as e:
        print(f"Error rebuilding history: {e}")
        import traceback
        traceback.print_exc()
