"""
Script to regenerate portfolio snapshots with real P&L values.
Includes USA (Trades), Argentina (ArgentinaPosition), and Crypto (CryptoPosition).
"""

from datetime import datetime, timedelta
from database import SessionLocal
import models
import market_data
import argentina_data

def rebuild_snapshots_with_pnl(user_id: int):
    db = SessionLocal()
    try:
        print(f"[Snapshots] Starting rebuild for user {user_id}...")
        
        # --- 1. Fetch ALL Position Types ---
        
        # USA Trades
        usa_trades = db.query(models.Trade).filter(models.Trade.user_id == user_id).all()
        
        # Argentine Positions
        try:
            arg_positions = db.query(models.ArgentinaPosition).filter(models.ArgentinaPosition.user_id == user_id).all()
        except:
            db.rollback() # Reset transaction if table missing
            arg_positions = []
            print("Warning: Could not fetch Argentina positions (table might be missing)")
            
        # Crypto Positions
        try:
            crypto_positions = db.query(models.CryptoPosition).filter(models.CryptoPosition.user_id == user_id).all()
        except:
            db.rollback() # Reset transaction if table missing
            crypto_positions = []
            print("Warning: Could not fetch Crypto positions (table might be missing)")

        total_assets = len(usa_trades) + len(arg_positions) + len(crypto_positions)
        print(f"Found {len(usa_trades)} USA trades, {len(arg_positions)} ARG positions, {len(crypto_positions)} Crypto positions.")
        
        if total_assets == 0:
            print("No assets found at all.")
            return {
                "status": "warning", 
                "message": "No assets found for this user", 
                "trades_found": 0,
                "arg_found": 0,
                "crypto_found": 0
            }

        # --- 2. Market Data Fetching (USA) ---
        usa_tickers = list(set([t.ticker for t in usa_trades if t.ticker]))
        close_prices = None
        
        if usa_tickers:
            print(f"Fetching historical prices for {len(usa_tickers)} USA tickers...")
            hist_data = market_data.safe_yf_download(usa_tickers, period="2y", threads=True)
            if not hist_data.empty:
                if len(usa_tickers) == 1:
                    close_prices = hist_data['Close'].to_frame(name=usa_tickers[0])
                else:
                    close_prices = hist_data['Close']
        
        # --- 3. Determine Date Range ---
        dates = []
        for t in usa_trades:
            if isinstance(t.entry_date, str):
                try: dates.append(datetime.strptime(t.entry_date, "%Y-%m-%d").date())
                except: pass
            else:
                if t.entry_date: dates.append(t.entry_date)
                
        # For simplicity, if ONLY ARG/Crypto exist, assume start date 30 days ago or from creation?
        # Ideally ARG positions have entry_date too.
        for p in arg_positions:
            if hasattr(p, 'entry_date') and p.entry_date:
                # ARG dates are often strings "YYYY-MM-DD"
                try: dates.append(datetime.strptime(p.entry_date, "%Y-%m-%d").date())
                except: pass
                
        for c in crypto_positions:
             if hasattr(c, 'entry_date') and c.entry_date:
                try: dates.append(datetime.strptime(c.entry_date, "%Y-%m-%d").date())
                except: pass
        
        if not dates:
            # Fallback if no valid dates found but assets exist
            start_date = datetime.now().date() - timedelta(days=30)
        else:
            start_date = min(dates)
            
        end_date = datetime.now().date()
        print(f"Rebuilding from {start_date} to {end_date}")
        
        # --- 4. Get Exchange Rates (Current) ---
        # For historical reconstruction, using current CCL is imperfect but better than 0.
        # Ideally we'd have historical CCL, but we don't.
        rates = argentina_data.get_dolar_rates()
        ccl_rate = rates.get("ccl", 1200)
        print(f"Using CCL Rate: {ccl_rate}")

        # --- 5. Clear Old Snapshots ---
        db.query(models.PortfolioSnapshot).filter(
            models.PortfolioSnapshot.user_id == user_id
        ).delete()
        db.commit()

        # --- 6. Iterate Days ---
        current = start_date
        snapshots_created = 0
        
        while current <= end_date:
            curr_str = current.strftime("%Y-%m-%d")
            
            # --- USA Calc ---
            usa_invested = 0
            usa_value = 0
            usa_pnl_val = 0
            
            for t in usa_trades:
                # Parse Dates
                t_entry = t.entry_date
                if isinstance(t_entry, str):
                    try: t_entry = datetime.strptime(t_entry, "%Y-%m-%d").date()
                    except: continue
                
                t_exit = None
                if t.exit_date:
                    if isinstance(t.exit_date, str):
                        try: t_exit = datetime.strptime(t.exit_date, "%Y-%m-%d").date()
                        except: pass
                    else:
                        t_exit = t.exit_date
                
                # Active Logic
                is_active = t_entry <= current and (t_exit is None or t_exit > current)
                is_closed = t_exit is not None and t_exit <= current
                
                if is_active:
                    cost = t.entry_price * t.shares
                    usa_invested += cost
                    
                    # Current Value
                    current_price = t.entry_price # Default
                    if close_prices is not None and t.ticker in close_prices.columns:
                        # Find closest date logic... (simplified for brevity, reuse logic)
                        # ... (Assuming reuse of previous logic or simplified for this artifact)
                        # For now, let's just use entry price if simplified, or previous logic
                        # Re-implementing simplified lookup:
                        try:
                            series = close_prices[t.ticker].dropna()
                            # Get index <= current
                            idx = series.index[series.index.date <= current]
                            if not idx.empty:
                                current_price = float(series.loc[idx[-1]])
                        except: pass
                    
                    val = current_price * t.shares
                    usa_value += val
                    usa_pnl_val += (val - cost)
                
                if is_closed and t.pnl:
                    usa_pnl_val += t.pnl

            # --- Argentina Calc ---
            arg_invested_usd = 0
            arg_value_usd = 0
            arg_pnl_usd = 0
            
            for p in arg_positions:
                # Check status based on exit_date if available?
                # Arg Position often "OPEN" or "CLOSED" string
                # Assuming simple active check: status == "OPEN" means active TODAY.
                # For historical, we check entry/exit dates.
                
                p_entry = None
                if p.entry_date:
                    try: p_entry = datetime.strptime(p.entry_date, "%Y-%m-%d").date()
                    except: pass
                
                # If no entry date, assume active? Or skip?
                if not p_entry: continue
                
                # Check active
                # Similar logic to USA
                # Simplified: If entry <= current. Exit checking is harder if format varies.
                # Assuming entry <= current is enough for "Cumulative Invested" view?
                # Ideally check exit.
                
                is_active = p_entry <= current # simplified
                if p.status == "CLOSED" and p.exit_date:
                     try: 
                        p_exit = datetime.strptime(p.exit_date, "%Y-%m-%d").date()
                        if current >= p_exit: is_active = False # It's closed
                     except: pass
                
                if is_active:
                    # Amounts are in ARS
                    inv_ars = (p.entry_price or 0) * (p.shares or 0)
                    
                    # Convert to USD
                    inv_usd = inv_ars / ccl_rate if ccl_rate else 0
                    
                    arg_invested_usd += inv_usd
                    
                    # Value: Need live price? 
                    # Without historical local data, assuming Value = Invested (flat) for history
                    # Unless we fetch BYMA history. 
                    # For now: Value = Invested (Flat line)
                    arg_value_usd += inv_usd 
            
            # --- Crypto Calc ---
            crypto_invested = 0
            crypto_value = 0
            
            for c in crypto_positions:
                # Same active logic
                c_entry = None
                if c.entry_date:
                    try: c_entry = datetime.strptime(c.entry_date, "%Y-%m-%d").date()
                    except: pass
                
                if c_entry and c_entry <= current:
                    # Invested
                    inv = (c.entry_price or 0) * (c.amount or 0)
                    crypto_invested += inv
                    
                    # Value = Invested (Flat unless we have crypto history)
                    # Current price in DB might be live, but not historical
                    crypto_value += inv

            # --- Totals ---
            total_invested = usa_invested + arg_invested_usd + crypto_invested
            total_value = usa_value + arg_value_usd + crypto_value
            total_pnl = usa_pnl_val # + arg/crypto pnl if we had it
            
            snapshot = models.PortfolioSnapshot(
                user_id=user_id,
                date=curr_str,
                
                total_invested_usd=total_invested,
                total_value_usd=total_value,
                total_pnl_usd=total_pnl,
                total_pnl_pct=(total_pnl/total_invested*100) if total_invested else 0,
                
                usa_invested_usd=usa_invested,
                usa_value_usd=usa_value,
                usa_pnl_usd=usa_pnl_val,
                
                argentina_invested_usd=arg_invested_usd,
                argentina_value_usd=arg_value_usd,
                argentina_pnl_usd=arg_pnl_usd,
                
                crypto_invested_usd=crypto_invested,
                crypto_value_usd=crypto_value,
                crypto_pnl_usd=0 # Pending historical data
            )
            db.add(snapshot)
            snapshots_created += 1
            current += timedelta(days=1)
            
        db.commit()
        
        return {
            "status": "success",
            "trades_found": len(usa_trades),
            "arg_found": len(arg_positions),
            "crypto_found": len(crypto_positions),
            "snapshots_created": snapshots_created,
            "latest_ccl": ccl_rate,
            "debug_totals": {
                "invested": total_invested,
                "value": total_value,
                "pnl": total_pnl,
                "usa_invested": usa_invested,
                "usa_pnl": usa_pnl_val,
                "arg_invested": arg_invested_usd,
                "crypto_invested": crypto_invested
            }
        }

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"{str(e)}"}
    finally:
        db.close()

if __name__ == "__main__":
    rebuild_snapshots_with_pnl(2)
