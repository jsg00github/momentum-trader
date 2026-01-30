import yfinance as yf
import pandas as pd
from datetime import datetime
import asyncio

# Default Universe (Liquid Tech/High Momentum)
DEFAULT_UNIVERSE = ["NVDA", "TSLA", "AMD", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "NFLX", "PLTR", "MARA", "COIN", "MSTR"]

def scan_unusual_options(tickers=None):
    """
    Scans for unusual options activity (Volume > OI * threshold).
    Returns a list of unusual contracts.
    """
    if not tickers:
        tickers = DEFAULT_UNIVERSE

    results = []
    print(f"[OPTIONS] Scanning {len(tickers)} tickers for unusual activity...")

    for ticker_symbol in tickers:
        try:
            tk = yf.Ticker(ticker_symbol)
            exps = tk.options
            
            if not exps:
                continue

            # Look at nearest 2 expirations (Weekly + Monthly typically)
            for date in exps[:2]:
                # Fetch Chain
                # yfinance returns entire chain (calls/puts)
                # We need to be careful with API limits, but this is per-ticker
                chain = tk.option_chain(date)
                
                # Analyze Calls
                for idx, row in chain.calls.iterrows():
                    vol = row.get('volume', 0) or 0
                    oi = row.get('openInterest', 0) or 0
                    
                    # Criteria:
                    # 1. Significant Volume (> 500 contracts)
                    # 2. Volume > Open Interest * 1.5 (Aggressive accumulation)
                    # 3. ITM check? maybe not, OTM is more "unusual"
                    
                    if vol > 500 and vol > (oi * 1.5):
                        results.append({
                            "ticker": ticker_symbol,
                            "type": "CALL",
                            "strike": row['strike'],
                            "expiration": date,
                            "volume": int(vol),
                            "oi": int(oi),
                            "vol_oi_ratio": round(vol / (oi if oi > 0 else 1), 2),
                            "lastPrice": row['lastPrice'],
                            "impliedVolatility": round(row['impliedVolatility'] * 100, 1)
                        })

                # Analyze Puts
                for idx, row in chain.puts.iterrows():
                    vol = row.get('volume', 0) or 0
                    oi = row.get('openInterest', 0) or 0
                    
                    if vol > 500 and vol > (oi * 1.5):
                        results.append({
                            "ticker": ticker_symbol,
                            "type": "PUT",
                            "strike": row['strike'],
                            "expiration": date,
                            "volume": int(vol),
                            "oi": int(oi),
                            "vol_oi_ratio": round(vol / (oi if oi > 0 else 1), 2),
                            "lastPrice": row['lastPrice'],
                            "impliedVolatility": round(row['impliedVolatility'] * 100, 1)
                        })

        except Exception as e:
            print(f"[OPTIONS] Error scanning {ticker_symbol}: {e}")
            continue

    # Sort by Volume/OI Ratio (Most unusual first)
    results.sort(key=lambda x: x['vol_oi_ratio'], reverse=True)
    
    # Split into Bullish and Bearish
    bullish = [r for r in results if r['type'] == 'CALL']
    bearish = [r for r in results if r['type'] == 'PUT']
    
    print(f"[OPTIONS] Found {len(bullish)} bullish and {len(bearish)} bearish contracts.")

    # Expert Analysis / Recommendation Logic
    recommendations = []
    sentiment_map = {}

    # Aggregate Flow by Ticker
    all_activity = bullish + bearish
    for trade in all_activity:
        t = trade['ticker']
        if t not in sentiment_map:
            sentiment_map[t] = {'call_vol': 0, 'put_vol': 0, 'call_count': 0, 'put_count': 0}
        
        if trade['type'] == 'CALL':
            sentiment_map[t]['call_vol'] += trade['volume']
            sentiment_map[t]['call_count'] += 1
        else:
            sentiment_map[t]['put_vol'] += trade['volume']
            sentiment_map[t]['put_count'] += 1

    # Generate Recommendation per Ticker
    for ticker, stats in sentiment_map.items():
        c_vol = stats['call_vol']
        p_vol = stats['put_vol']
        total_vol = c_vol + p_vol
        
        if total_vol == 0: continue

        advice = {}
        advice['ticker'] = ticker
        
        if c_vol > (p_vol * 2):
            advice['sentiment'] = "BULLISH"
            advice['action'] = "BUY CALLS"
            advice['reason'] = f"Experts are heavy on Calls ({int(c_vol)} vs {int(p_vol)} Puts). Expect upside."
            advice['conviction'] = "HIGH" if c_vol > 2000 else "MEDIUM"
        elif p_vol > (c_vol * 2):
            advice['sentiment'] = "BEARISH"
            advice['action'] = "BUY PUTS"
            advice['reason'] = f"Experts are betting on downside ({int(p_vol)} Puts vs {int(c_vol)} Calls)."
            advice['conviction'] = "HIGH" if p_vol > 2000 else "MEDIUM"
        else:
            advice['sentiment'] = "NEUTRAL / VOLATILITY"
            advice['action'] = "WAIT / STRADDLE"
            advice['reason'] = "Mixed activity. Market expects a move but direction is split."
            advice['conviction'] = "LOW"

        # Add Technical Levels (Target/Stop)
        try:
            import screener
            levels = screener.get_technical_levels(ticker, advice['sentiment'])
            if levels:
                advice['entry'] = levels['entry']
                advice['target'] = levels['target']
                advice['stop_loss'] = levels['stop_loss']
                advice['r_r'] = levels['r_r']
            else:
                advice['entry'] = 0
                advice['target'] = 0
                advice['stop_loss'] = 0
                advice['r_r'] = 0
        except Exception as e:
            print(f"Error adding levels to {ticker}: {e}")
            advice['entry'] = 0
            advice['target'] = 0
            advice['stop_loss'] = 0
            advice['r_r'] = 0

        recommendations.append(advice)

    return {
        "bullish": bullish,
        "bearish": bearish,
        "expert_recommendations": recommendations  # New Field
    }
