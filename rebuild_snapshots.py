"""
Script to regenerate portfolio snapshots with real P&L values.
Uses historical closing prices from yfinance to calculate daily P&L.
"""

from datetime import datetime, timedelta
from database import SessionLocal
import models
import market_data

def rebuild_snapshots_with_pnl(user_id: int):
    db = SessionLocal()
    try:
        print(f"[Snapshots] Starting rebuild for user {user_id}...")
        
        # 1. Get all trades for this user
        trades = db.query(models.Trade).filter(models.Trade.user_id == user_id).all()
        if not trades:
            print("No trades found.")
            return
        
        # 2. Get unique tickers
        tickers = list(set([t.ticker for t in trades if t.ticker]))
        print(f"Found {len(trades)} trades, {len(tickers)} unique tickers")
        
        # 3. Fetch 2 years of historical data for all tickers
        print(f"Fetching historical prices for {len(tickers)} tickers...")
        hist_data = market_data.safe_yf_download(tickers, period="2y", threads=True)
        
        if hist_data.empty:
            print("No historical data returned!")
            return
        
        # Extract Close prices
        if len(tickers) == 1:
            close_prices = hist_data['Close'].to_frame(name=tickers[0])
        else:
            close_prices = hist_data['Close']
        
        print(f"Historical data shape: {close_prices.shape}")
        
        # 4. Get date range
        dates = []
        for t in trades:
            if isinstance(t.entry_date, str):
                try: dates.append(datetime.strptime(t.entry_date, "%Y-%m-%d").date())
                except: pass
            else:
                dates.append(t.entry_date)
        
        if not dates:
            print("No valid dates found.")
            return
        
        start_date = min(dates)
        end_date = datetime.now().date()
        print(f"Date range: {start_date} to {end_date}")
        
        # 5. Clear existing snapshots for this user
        db.query(models.PortfolioSnapshot).filter(
            models.PortfolioSnapshot.user_id == user_id
        ).delete()
        db.commit()
        print("Cleared existing snapshots.")
        
        # 6. Iterate through each day
        current = start_date
        snapshots_created = 0
        
        while current <= end_date:
            curr_str = current.strftime("%Y-%m-%d")
            
            daily_invested = 0
            daily_pnl = 0
            daily_value = 0
            
            for t in trades:
                # Parse dates
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
                
                # Check if trade was active on this day
                is_active = t_entry <= current and (t_exit is None or t_exit > current)
                is_closed = t_exit is not None and t_exit <= current
                
                if is_active:
                    cost = t.entry_price * t.shares
                    daily_invested += cost
                    
                    # Get closing price for this day
                    try:
                        # Try to get price from historical data
                        if t.ticker in close_prices.columns:
                            # Find closest available price
                            price_series = close_prices[t.ticker]
                            available_dates = price_series.dropna().index
                            
                            # Find closest date <= current
                            close_date = None
                            for d in available_dates:
                                if d.date() <= current:
                                    close_date = d
                            
                            if close_date:
                                current_price = float(price_series.loc[close_date])
                                current_val = current_price * t.shares
                                daily_value += current_val
                                daily_pnl += (current_val - cost)
                            else:
                                # No price available, use entry price
                                daily_value += cost
                        else:
                            # Ticker not found, use entry price
                            daily_value += cost
                    except Exception as e:
                        daily_value += cost
                
                if is_closed:
                    if t.pnl is not None:
                        daily_pnl += t.pnl
            
            # Create snapshot
            snapshot = models.PortfolioSnapshot(
                user_id=user_id,
                date=curr_str,
                total_invested_usd=daily_invested,
                total_value_usd=daily_value,
                total_pnl_usd=daily_pnl,
                total_pnl_pct=(daily_pnl / daily_invested * 100) if daily_invested > 0 else 0,
                usa_invested_usd=daily_invested,
                usa_value_usd=daily_value,
                usa_pnl_usd=daily_pnl
            )
            db.add(snapshot)
            snapshots_created += 1
            
            current += timedelta(days=1)
        
        db.commit()
        print(f"Created {snapshots_created} snapshots successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    rebuild_snapshots_with_pnl(2)  # User test@momentum.com
