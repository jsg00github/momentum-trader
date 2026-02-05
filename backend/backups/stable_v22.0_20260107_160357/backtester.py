import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def run_backtest(ticker: str, strategy: str = "momentum_trend"):
    """
    Simulates a trading strategy on historical data.
    
    Strategy 'momentum_trend':
    - Buy when Price > EMA(20) and RSI > 50
    - Sell/Trailing Stop: If Price drops below EMA(20) OR hits 2x Risk target.
    
    Returns a dict with performance metrics and equity curve.
    """
    try:
        # 1. Fetch Data (2 years)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=730)
        
        df = market_data.safe_yf_download(ticker, start=start_date, end=end_date)
        if df.empty or len(df) < 50:
            return {"error": "Insufficient data"}
        
        # Cleanup column names if MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            try:
                if ticker in df.columns.get_level_values(1):
                    df = df.xs(ticker, axis=1, level=1)
                else:
                    df = df.xs(ticker, axis=1, level=0)
            except:
                df.columns = [c[0] for c in df.columns]
            
        df['Close'] = df['Close'].astype(float)
        
        # 2. Calculate Indicators
        # EMA 21
        df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
        
        # RSI 14
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 3. Simulation Loop
        initial_capital = 10000.0
        details = {
            "initial_capital": initial_capital,
            "equity": initial_capital,
            "trades": [],
            "equity_curve": []
        }
        
        position = None # { 'entry_price': float, 'shares': int, 'date': date }
        equity = initial_capital
        
        for i in range(21, len(df)):
            date = df.index[i]
            price = df['Close'].iloc[i]
            prev_price = df['Close'].iloc[i-1]
            ema = df['EMA21'].iloc[i]
            rsi = df['RSI'].iloc[i]
            
            # Record daily equity (mark-to-market if holding)
            current_equity = equity
            if position:
                current_equity = equity + (price - position['entry_price']) * position['shares']
            
            # Add data point for chart (limit to last 100 points for frontend perf if needed, or send all)
            details['equity_curve'].append({
                "date": date.strftime("%Y-%m-%d"),
                "equity": round(current_equity, 2)
            })
            
            # --- Strategy Logic ---
            
            # CHECK EXIT
            if position:
                # Stop Loss: Close below EMA21
                if price < ema:
                    # SELL
                    pnl = (price - position['entry_price']) * position['shares']
                    equity += pnl
                    
                    trade = {
                        "entry_date": position['date'].strftime("%Y-%m-%d"),
                        "exit_date": date.strftime("%Y-%m-%d"),
                        "entry_price": position['entry_price'],
                        "exit_price": price,
                        "pnl": round(pnl, 2),
                        "pnl_pct": round((price - position['entry_price']) / position['entry_price'] * 100, 2)
                    }
                    details['trades'].append(trade)
                    position = None
                    
            # CHECK ENTRY
            elif not position:
                # Buy Condition: Price > EMA21 AND RSI > 50 (Momentum)
                if price > ema and rsi > 50:
                    # Risk Management: risk 2% of equity
                    risk_per_share = price * 0.05 # Assumed 5% stop distance for sizing
                    risk_amount = equity * 0.02
                    shares = int(risk_amount / risk_per_share)
                    
                    if shares > 0:
                         position = {
                            'entry_price': price,
                            'shares': shares,
                            'date': date
                        }

        # Final Cleanup
        final_equity = details['equity_curve'][-1]['equity']
        total_trades = len(details['trades'])
        wins = len([t for t in details['trades'] if t['pnl'] > 0])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        return {
            "ticker": ticker,
            "strategy": strategy,
            "initial_equity": initial_capital,
            "final_equity": round(final_equity, 2),
            "total_trades": total_trades,
            "win_rate": round(win_rate, 1),
            "trades": details['trades'], # Send last 50 trades
            "equity_curve": details['equity_curve'] # For charting
        }
        
    except Exception as e:
        print(f"Backtest Error: {e}")
        return {"error": str(e)}
