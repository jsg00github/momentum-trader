
import yfinance as yf
import pandas as pd
import numpy as np

SECTORS = {
    "Technology": "XLK",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Cons. Discret.": "XLY",
    "Cons. Staples": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Comms": "XLC",
    "Utilities": "XLU"
}

SECTOR_HOLDINGS = {
    "XLK": ["MSFT", "AAPL", "NVDA", "AVGO", "ORCL", "ADBE", "CRM", "AMD"],
    "XLF": ["JPM", "V", "MA", "BAC", "WFC", "MS", "GS", "AXP"],
    "XLV": ["LLY", "UNH", "JNJ", "MRK", "ABBV", "TMO", "AMGN", "PFE"],
    "XLY": ["AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "BKNG"],
    "XLP": ["PG", "COST", "PEP", "KO", "WMT", "PM", "MDLZ", "CL"],
    "XLE": ["XOM", "CVX", "COP", "EOG", "SLB", "MPC", "PSX", "OXY"],
    "XLI": ["GE", "CAT", "UBER", "UNP", "HON", "BA", "UPS", "DE"],
    "XLB": ["LIN", "SHW", "FCX", "APD", "ECL", "NEM", "DOW", "DD"],
    "XLRE": ["PLD", "AMT", "EQIX", "PSA", "CCI", "O", "DLR", "VIC"],
    "XLC": ["META", "GOOGL", "NFLX", "TMUS", "DIS", "CMCSA", "VZ", "T"],
    "XLU": ["NEE", "SO", "DUK", "SRE", "AEP", "D", "PEG", "ED"]
}

INDICES = ["SPY", "QQQ", "IWM", "^VIX"]

def calculate_3m_perf(series):
    if len(series) < 50: return 0.0
    # Approx 3 months ~ 63 trading days
    lookback = min(len(series)-1, 63)
    start = float(series.iloc[-lookback])
    end = float(series.iloc[-1])
    if start == 0: return 0.0
    return ((end - start) / start) * 100

def analyze_sector_constituents(sector_ticker):
    """
    Downloads data for top holdings of a sector and finds Leader/Laggard (3M).
    """
    tickers = SECTOR_HOLDINGS.get(sector_ticker, [])
    if not tickers:
        return None
    
    try:
        data = yf.download(" ".join(tickers), period="6mo", interval="1d", progress=False, auto_adjust=False)
        if isinstance(data.columns, pd.MultiIndex):
            closes = data['Close']
        else:
            closes = data
            
        results = []
        for t in tickers:
            if t in closes.columns:
                series = closes[t].dropna()
                if len(series) < 50: continue
                
                perf = calculate_3m_perf(series)
                
                # Calculate EMA50
                ema50 = float(series.ewm(span=50, adjust=False).mean().iloc[-1])
                curr_price = float(series.iloc[-1])
                trend_ok = curr_price > ema50
                
                results.append({
                    "ticker": t, 
                    "perf": perf, 
                    "trend_ok": trend_ok
                })
        
        if not results:
            return None
            
        results.sort(key=lambda x: x['perf'], reverse=True)
        leader = results[0]
        
        # Laggard Logic: "Uptrending but Laggard" (Positive & > EMA50)
        # Filter for candidates that are in Uptrend (Price > EMA50) AND Positive Perf
        weinstein_candidates = [r for r in results if r['trend_ok'] and r['perf'] > 0]
        
        if weinstein_candidates:
            # Sort asc by perf (weakest of the strong)
            weinstein_candidates.sort(key=lambda x: x['perf'])
            laggard = weinstein_candidates[0]
        else:
            # Fallback 1: Just uptrending (maybe slightly neg?)
            uptrend_candidates = [r for r in results if r['trend_ok']]
            if uptrend_candidates:
                uptrend_candidates.sort(key=lambda x: x['perf'])
                laggard = uptrend_candidates[0]
            else:
                # Fallback 2: Absolute laggard (worst perf)
                laggard = results[-1]
        
        return {
            "leader": leader,
            "laggard": laggard
        }
    except Exception as e:
        print(f"Error analyzing sector {sector_ticker}: {e}")
        return None

import time

def generate_expert_summary(indices, sectors):
    """
    Generates a rule-based narrative summary of the market.
    """
    spy = indices.get("SPY", {})
    qqq = indices.get("QQQ", {})
    vix = indices.get("VIX", {})
    
    # 1. Determine Overall Mood
    bullish_count = sum(1 for i in [spy, qqq] if i.get("color") == "Green")
    bearish_count = sum(1 for i in [spy, qqq] if i.get("color") == "Red")
    
    mood = "Neutral"
    if bullish_count == 2: mood = "Bullish"
    elif bearish_count == 2: mood = "Bearish"
    elif spy.get("color") == "Green": mood = "Cautiously Bullish"
    
    # 2. Risk Assessment
    risk_level = vix.get("level", "Normal")
    risk_text = "Risk is low, favoring aggressive plays."
    if risk_level == "Elevated": risk_text = "Volatility is rising, tighten stops."
    elif risk_level == "High": risk_text = "Extreme fear detected. Cash or deep value only."
    
    # 3. Sector Leadership
    leaders = sorted(sectors, key=lambda x: x['1m'], reverse=True)[:2]
    laggards = sorted(sectors, key=lambda x: x['1m'])[:2]
    
    leader_names = [s['name'] for s in leaders]
    laggard_names = [s['name'] for s in laggards]
    
    # 4. Construct Narrative
    # Part 1: The Setup
    setup = f"The market closes in a **{mood}** state."
    if mood == "Bullish":
        setup += f" SPY and QQQ are holding firm above their key moving averages."
    elif mood == "Bearish":
        setup += f" Major indices have lost structure. Caution is advised."
    else:
        setup += f" We are seeing mixed signals with potential chop."
        
    # Part 2: Under the Hood
    internals = f"Money is flowing into **{', '.join(leader_names)}**, while **{', '.join(laggard_names)}** are lagging behind. {risk_text}"
    
    # Part 3: The Play
    play = "Focus on high relative strength setups."
    if mood == "Bullish" and risk_level == "Low":
        play = "Conditions are prime for momentum breakouts. Look for Bull Flags in leading sectors."
    elif mood == "Bearish":
        play = "Preserve capital. Avoid long exposure until SPY reclaims EMA21."
    elif risk_level == "High":
        play = "Market is fearful. Expect wide swings. Reduce position size significantly."
        
    return {
        "setup": setup,
        "internals": internals,
        "play": play,
        "mood": mood
    }

def generate_morning_briefing(indices, sectors):
    """
    Generates a pre-market morning briefing.
    Focuses on overnight context and key levels.
    """
    spy = indices.get("SPY", {})
    vix = indices.get("VIX", {})
    
    mood = "Neutral" # Default
    if spy.get("color") == "Green": mood = "Bullish"
    elif spy.get("color") == "Red": mood = "Bearish"
    
    price = spy.get("price", 0)
    ema21 = spy.get("ema21", 0)
    
    # Context
    context = ""
    if mood == "Bullish":
        context = f"SPY is holding bullish structure above ${ema21}."
    elif mood == "Bearish":
        context = f"SPY remains in a downtrend below ${ema21}."
        
    risk = "Normal"
    if vix.get("level") == "Elevated": risk = "Elevated Volatility"
    elif vix.get("level") == "High": risk = "High Fear"
    
    # Construct Message
    message = f"""
🌅 <b>MORNING BRIEFING</b>

<b>Overall Mood:</b> {mood}
<b>SPY Level:</b> ${price} (EMA21: ${ema21})
<b>Risk Environment:</b> {risk} ({vix.get('price', 0)})

<b>Outlook:</b>
{context}

<b>Focus for Today:</b>
• Check pre-market leaders in top sectors.
• Watch for opening range breakouts.
• Risk is {risk.lower()} - adjust sizing accordingly.

<i>"Plan the trade, trade the plan."</i>
"""
    return message

def get_market_status():
    """
    Fetches market status:
    1. Trend (SPY, QQQ, IWM)
    2. Risk (VIX)
    3. Sector Performance (1M, 2M, 3M)
    4. Deep Dive for Top 3 Sectors (3M)
    """
    try:
        # 1. Fetch Indices
        print("Fetching Indices...")
        tickers = " ".join(INDICES)
        # threads=False to be safer against rate limits
        data = yf.download(tickers, period="6mo", interval="1d", progress=False, auto_adjust=False, threads=False)
        time.sleep(1) # Pause
        
        # Handle MultiIndex
        if isinstance(data.columns, pd.MultiIndex):
            closes = data['Close']
        else:
            closes = data
            
        status = {}
        
        # Calculate Trends for Indices
        for ticker in ["SPY", "QQQ", "IWM"]:
            series = None
            
            # Try getting from bulk data
            if ticker in closes.columns:
                series = closes[ticker].dropna()
                
            # Retry individual fetch if missing
            if series is None or len(series) < 50:
                print(f"Index {ticker} missing or empty. Retrying individually...")
                try:
                    retry_data = yf.download(ticker, period="6mo", interval="1d", progress=False, auto_adjust=False, threads=False)
                    if isinstance(retry_data.columns, pd.MultiIndex):
                        retry_series = retry_data['Close'][ticker]
                    else:
                        retry_series = retry_data['Close'] if 'Close' in retry_data else retry_data
                    
                    series = retry_series.dropna()
                except Exception as e:
                    print(f"Retry failed for {ticker}: {e}")

            if series is None or len(series) < 50:
                status[ticker] = {"state": "Unknown", "price": 0}
                print(f"Failed to fetch {ticker} after retry.")
                continue
                
            last_price = float(series.iloc[-1])
            ema21 = float(series.ewm(span=21, adjust=False).mean().iloc[-1])
            ema50 = float(series.ewm(span=50, adjust=False).mean().iloc[-1])
            
            # Traffic Light Logic
            if last_price > ema21 and ema21 > ema50:
                color = "Green"
                desc = "Strong Uptrend"
            elif last_price < ema50:
                color = "Red"
                desc = "Downtrend"
            else:
                color = "Yellow"
                desc = "Mixed / Chop"
                
            status[ticker] = {
                "price": round(last_price, 2),
                "ema21": round(ema21, 2),
                "ema50": round(ema50, 2),
                "color": color,
                "desc": desc
            }

        # VIX
        if "^VIX" in closes.columns:
            vix_series = closes["^VIX"].dropna()
            if not vix_series.empty:
                vix_val = float(vix_series.iloc[-1])
                risk_level = "Low" if vix_val < 15 else ("High" if vix_val > 20 else "Elevated")
                status["VIX"] = {"price": round(vix_val, 2), "level": risk_level}
            
        # 2. Fetch Sectors
        print("Fetching Sectors...")
        sec_tickers_list = list(SECTORS.values())
        sec_tickers = " ".join(sec_tickers_list)
        sec_data = yf.download(sec_tickers, period="6mo", interval="1d", progress=False, auto_adjust=False, threads=False)
        time.sleep(1) # Pause
        
        if isinstance(sec_data.columns, pd.MultiIndex):
            sec_closes = sec_data['Close']
        else:
            sec_closes = sec_data
            
        sectors_perf = []
        
        for name, ticker in SECTORS.items():
            if ticker not in sec_closes.columns:
                print(f"Sector {ticker} missing.")
                continue
                
            series = sec_closes[ticker].dropna()
            if len(series) < 65:
                continue
                
            curr = float(series.iloc[-1])
            price_1m = float(series.iloc[-22]) # ~1 month ago
            price_2m = float(series.iloc[-43]) # ~2 months ago
            price_3m = float(series.iloc[-63]) # ~3 months ago
            
            perf_1m = ((curr - price_1m) / price_1m) * 100
            perf_2m = ((curr - price_2m) / price_2m) * 100
            perf_3m = ((curr - price_3m) / price_3m) * 100
            
            sectors_perf.append({
                "name": name,
                "ticker": ticker,
                "1m": round(perf_1m, 2),
                "2m": round(perf_2m, 2),
                "3m": round(perf_3m, 2),
                "3m_val": perf_3m # Store for sorting
            })
            
        # 3. Deep Dive for Top 3 (3M Performers)
        # Sort by 3M
        print("Calculating Deep Dive...")
        top_3_sectors = sorted(sectors_perf, key=lambda x: x['3m_val'], reverse=True)[:3]
        top_tickers = {s['ticker'] for s in top_3_sectors} # Set for fast lookup
        
        for sector in sectors_perf:
            if sector['ticker'] in top_tickers:
                # Add deep dive info
                dd = analyze_sector_constituents(sector['ticker'])
                if dd:
                    sector['deep_dive'] = dd
                time.sleep(0.5) # Gentle pause between sectors

        return {
            "indices": status,
            "sectors": sectors_perf,
            "expert_summary": generate_expert_summary(status, sectors_perf)
        }




    except Exception as e:
        print(f"Error fetching market data: {e}")
        return {"error": str(e)}


def get_batch_latest_prices(tickers):
    """
    Fetch latest prices for a list of tickers in one batch request.
    Returns dict {ticker: price}
    """
    if not tickers:
        return {}
    
    unique_tickers = list(set([t for t in tickers if t]))
    if not unique_tickers:
        return {}
        
    try:
        # Download 5 days of data to ensure we get last close even if holiday/weekend
        # interval 1d is standard and fast
        data = yf.download(
            " ".join(unique_tickers), 
            period="5d", 
            interval="1d", 
            progress=False, 
            auto_adjust=False,
            threads=True
        )
        
        prices = {}
        
        # Determine if we have MultiIndex or single level
        # yfinance behavior varies by version and number of tickers
        
        closes = None
        
        # Case 1: MultiIndex columns (Ticker, PriceType) or (PriceType, Ticker)
        if isinstance(data.columns, pd.MultiIndex):
            # Try to find 'Close' in level 0 or 1
            if 'Close' in data.columns.get_level_values(0):
                # Format: Close -> Ticker
                closes = data['Close']
            elif 'Close' in data.columns.get_level_values(1):
                # Format: Ticker -> Close (less common now but possible)
                # Need to swap level?
                pass
                
        # Case 2: Single level columns (e.g. single ticker or just Close columns if formatted that way)
        elif 'Close' in data.columns:
            closes = data['Close']
            
        # Process Closes
        if closes is not None:
             # If DataFrame (multiple tickers), iterate
             if isinstance(closes, pd.DataFrame):
                 for ticker in unique_tickers:
                     if ticker in closes.columns:
                         series = closes[ticker].dropna()
                         if not series.empty:
                             prices[ticker] = float(series.iloc[-1])
             # If Series (single ticker)
             elif isinstance(closes, pd.Series):
                 if len(unique_tickers) == 1 and not closes.empty:
                     prices[unique_tickers[0]] = float(closes.iloc[-1])
        
        # Fallback for single ticker returning flat DataFrame with Open, High, Low, Close
        elif len(unique_tickers) == 1 and 'Close' in data.columns:
             series = data['Close'].dropna()
             if not series.empty:
                 prices[unique_tickers[0]] = float(series.iloc[-1])

        return prices

    except Exception as e:
        print(f"Error fetching batch prices: {e}")
        return {}
