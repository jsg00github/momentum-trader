"""
Market Regime Detection - Market Environment Analysis

Based on methodologies from:
- William O'Neil (Follow Through Days, Distribution Days)
- Stan Weinstein (Stage Analysis for indices)
- Mark Minervini (Market breadth analysis)

Core principle: 3 out of 4 stocks follow the market
- Don't fight the tape
- Trade smaller in weak markets
- Go aggressive in strong markets
"""

import pandas as pd
import numpy as np
import math
from typing import Dict, List
import market_data
from datetime import datetime, timedelta


def _sanitize_for_json(obj):
    """Recursively convert NaN/Inf/numpy types to JSON-safe values."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def get_market_regime() -> Dict:
    """
    Analyze overall market conditions to determine trading environment.
    
    Returns market regime classification:
    - BULL_CONFIRMED: Strong uptrend, go aggressive
    - BULL_UNDER_PRESSURE: Uptrend but showing weakness
    - CORRECTION: Market correcting, reduce exposure
    - BEAR: Downtrend, mostly cash
    
    Returns:
        Dict with regime, confidence, and position sizing multiplier
    """
    try:
        # Analyze major indices
        spy_analysis = _analyze_index("SPY", "S&P 500")
        qqq_analysis = _analyze_index("QQQ", "Nasdaq")
        iwm_analysis = _analyze_index("IWM", "Russell 2000")
        
        # Combine signals
        indices = [spy_analysis, qqq_analysis, iwm_analysis]
        
        # Count how many indices are bullish
        bullish_count = sum(1 for idx in indices if idx['stage'] == 2)
        neutral_count = sum(1 for idx in indices if idx['stage'] in [1, 3])
        bearish_count = sum(1 for idx in indices if idx['stage'] == 4)
        
        # Market breadth (% stocks above key moving averages)
        breadth = _calculate_market_breadth()
        
        # Determine regime
        if bullish_count >= 2 and breadth['pct_above_200ma'] > 0.70:
            regime = "BULL_CONFIRMED"
            confidence = 90
            position_multiplier = 1.0
            action = "Go aggressive - Full position sizes"
            
        elif bullish_count >= 2 and breadth['pct_above_200ma'] > 0.50:
            regime = "BULL"
            confidence = 75
            position_multiplier = 0.75
            action = "Favorable - Normal position sizes"
            
        elif bullish_count >= 1 and breadth['pct_above_200ma'] > 0.40:
            regime = "BULL_UNDER_PRESSURE"
            confidence = 60
            position_multiplier = 0.50
            action = "Cautious - Reduce position sizes by 50%"
            
        elif breadth['pct_above_200ma'] > 0.30:
            regime = "CORRECTION"
            confidence = 70
            position_multiplier = 0.25
            action = "Defensive - Only best setups, 25% size"
            
        else:
            regime = "BEAR"
            confidence = 85
            position_multiplier = 0.0
            action = "Cash - Do not trade"
        
        # Check for Follow-Through Day (O'Neil)
        ftd_detected = _detect_follow_through_day(spy_analysis['df'])
        
        # Check for Distribution Days (O'Neil)  
        distribution_count = _count_distribution_days(spy_analysis['df'])
        
        # Strip non-serializable DataFrames before returning
        for idx_data in [spy_analysis, qqq_analysis, iwm_analysis]:
            idx_data.pop('df', None)

        return _sanitize_for_json({
            'regime': regime,
            'confidence': confidence,
            'position_size_multiplier': position_multiplier,
            'recommended_action': action,
            'indices': {
                'SPY': spy_analysis,
                'QQQ': qqq_analysis,
                'IWM': iwm_analysis
            },
            'breadth': breadth,
            'bullish_indices': bullish_count,
            'follow_through_day': ftd_detected,
            'distribution_days': distribution_count,
            'warning': _generate_warning(regime, distribution_count, breadth)
        })
        
    except Exception as e:
        print(f"Error calculating market regime: {e}")
        # Default to cautious stance if error
        return {
            'regime': 'UNKNOWN',
            'confidence': 0,
            'position_size_multiplier': 0.25,
            'recommended_action': 'Error analyzing market - Be cautious',
            'error': str(e)
        }


def _analyze_index(ticker: str, name: str) -> Dict:
    """
    Analyze individual index using Weinstein Stage Analysis.
    
    Stage 1: Basing (accumulation)
    Stage 2: Advancing (uptrend) - BULL
    Stage 3: Topping (distribution)
    Stage 4: Declining (downtrend) - BEAR
    """
    try:
        df = market_data.safe_yf_download(ticker, period="1y", interval="1d", auto_adjust=False)
        
        if df is None or df.empty:
            return {'stage': 0, 'name': name, 'error': 'No data'}
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # Calculate 30-week SMA (150-day approximation)
        df['SMA_150'] = df['Close'].rolling(window=150).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['SMA_200'] = df['Close'].rolling(window=200).mean()
        
        current_price = df['Close'].iloc[-1]
        sma_150 = df['SMA_150'].iloc[-1]
        sma_50 = df['SMA_50'].iloc[-1]
        
        # Calculate slope of 150 SMA
        if len(df) >= 160:
            sma_10_days_ago = df['SMA_150'].iloc[-10]
            sma_slope = (sma_150 - sma_10_days_ago) / sma_10_days_ago
        else:
            sma_slope = 0
        
        # Weinstein Stage determination
        above_150 = current_price > sma_150
        sma_rising = sma_slope > 0
        strong_trend = current_price > sma_50 and sma_50 > sma_150
        
        if above_150 and sma_rising and strong_trend:
            stage = 2  # Advancing - BULL
        elif above_150 and not sma_rising:
            stage = 3  # Topping
        elif not above_150 and sma_rising:
            stage = 1  # Basing
        else:
            stage = 4  # Declining - BEAR
        
        return {
            'ticker': ticker,
            'name': name,
            'stage': stage,
            'stage_name': ['Unknown', 'Basing', 'Advancing', 'Topping', 'Declining'][stage],
            'current_price': round(current_price, 2),
            'sma_150': round(sma_150, 2) if not pd.isna(sma_150) else None,
            'distance_from_sma': round((current_price / sma_150 - 1) * 100, 2) if not pd.isna(sma_150) else 0,
            'is_bullish': stage == 2,
            'df': df  # Keep for further analysis
        }
        
    except Exception as e:
        return {'stage': 0, 'name': name, 'error': str(e)}


def _calculate_market_breadth() -> Dict:
    """
    Calculate percentage of stocks above key moving averages.
    
    Minervini uses this to gauge market health:
    - >70% above 200 MA = Healthy bull market
    - 50-70% = Normal bull market
    - 30-50% = Weak/correcting market
    - <30% = Bear market
    """
    try:
        # Sample major stocks from SPY
        # In production, you'd scan all SPY constituents
        sample_tickers = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B',
            'JPM', 'JNJ', 'V', 'PG', 'UNH', 'MA', 'HD', 'DIS', 'PYPL', 'NFLX',
            'ADBE', 'CRM', 'COST', 'PEP', 'TMO', 'CSCO', 'ABT', 'CVX', 'MCD'
        ]
        
        above_50 = 0
        above_200 = 0
        total = 0
        
        for ticker in sample_tickers:
            try:
                df = market_data.safe_yf_download(ticker, period="1y", interval="1d", auto_adjust=False)
                if df is None or df.empty or len(df) < 200:
                    continue
                
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                
                current = df['Close'].iloc[-1]
                sma_50 = df['Close'].rolling(50).mean().iloc[-1]
                sma_200 = df['Close'].rolling(200).mean().iloc[-1]
                
                if current > sma_50:
                    above_50 += 1
                if current > sma_200:
                    above_200 += 1
                    
                total += 1
                
            except:
                continue
        
        if total == 0:
            return {'pct_above_50ma': 0.5, 'pct_above_200ma': 0.5, 'sample_size': 0}
        
        return {
            'pct_above_50ma': round(above_50 / total, 3),
            'pct_above_200ma': round(above_200 / total, 3),
            'sample_size': total,
            'health': 'Strong' if above_200/total > 0.70 else 'Weak' if above_200/total < 0.30 else 'Normal'
        }
        
    except:
        return {'pct_above_50ma': 0.5, 'pct_above_200ma': 0.5, 'sample_size': 0}


def _detect_follow_through_day(df: pd.DataFrame) -> bool:
    """
    Detect William O'Neil's Follow-Through Day.
    
    FTD Criteria:
    1. Occurs on day 4-7 of a rally attempt
    2. Strong volume (>avg)
    3. Index gains >1.5%
    4. Confirms market bottom
    
    Returns True if recent FTD detected
    """
    try:
        if len(df) < 20:
            return False
        
        recent = df.tail(10)
        
        for i in range(4, 8):  # Days 4-7
            if i >= len(recent):
                continue
                
            day = recent.iloc[-i]
            prev_day = recent.iloc[-i-1]
            
            # Calculate gain
            gain = (day['Close'] - prev_day['Close']) / prev_day['Close']
            
            # Check volume
            avg_volume = recent['Volume'].mean()
            volume_surge = day['Volume'] > avg_volume
            
            # FTD criteria
            if gain > 0.015 and volume_surge:  # >1.5% gain on high volume
                return True
        
        return False
        
    except:
        return False


def _count_distribution_days(df: pd.DataFrame) -> int:
    """
    Count distribution days in last 25 trading days (O'Neil method).
    
    Distribution Day = Index down >0.2% on higher volume than previous day
    
    O'Neil Rule:
    - 3-4 distribution days = Warning
    - 5+ distribution days = Major topping signal
    """
    try:
        if len(df) < 25:
            return 0
        
        recent = df.tail(25)
        dist_count = 0
        
        for i in range(1, len(recent)):
            day = recent.iloc[i]
            prev = recent.iloc[i-1]
            
            price_down = (day['Close'] - prev['Close']) / prev['Close'] < -0.002  # Down >0.2%
            volume_up = day['Volume'] > prev['Volume']
            
            if price_down and volume_up:
                dist_count += 1
        
        return dist_count
        
    except:
        return 0


def _generate_warning(regime: str, distribution_days: int, breadth: Dict) -> str:
    """Generate actionable warning based on market conditions"""
    
    warnings = []
    
    if distribution_days >= 5:
        warnings.append(f"🔴 CRITICAL: {distribution_days} distribution days detected - Market topping")
    elif distribution_days >= 3:
        warnings.append(f"⚠ WARNING: {distribution_days} distribution days - Use tight stops")
    
    if breadth['pct_above_200ma'] < 0.30:
        warnings.append(f"🔴 Breadth weak: Only {breadth['pct_above_200ma']*100:.0f}% stocks above 200 MA")
    elif breadth['pct_above_200ma'] < 0.50:
        warnings.append(f"⚠ Breadth warning: {breadth['pct_above_200ma']*100:.0f}% stocks above 200 MA")
    
    if regime == "BEAR":
        warnings.append("🔴 BEAR MARKET - Preserve capital, stay in cash")
    elif regime == "CORRECTION":
        warnings.append("⚠ CORRECTION PHASE - Only trade A+ setups")
    
    if not warnings:
        return "✓ Market conditions favorable for trading"
    
    return " | ".join(warnings)


def get_position_size_adjustment(regime: str, distribution_days: int) -> float:
    """
    Calculate position size adjustment based on market conditions.
    
    Minervini Rule: Adjust position size based on market strength
    
    Returns:
        Multiplier for normal position size (0.0 to 1.0)
    """
    base_multiplier = {
        "BULL_CONFIRMED": 1.0,
        "BULL": 0.75,
        "BULL_UNDER_PRESSURE": 0.50,
        "CORRECTION": 0.25,
        "BEAR": 0.0
    }.get(regime, 0.50)
    
    # Further reduce if excessive distribution
    if distribution_days >= 5:
        base_multiplier *= 0.5
    elif distribution_days >= 3:
        base_multiplier *= 0.75
    
    return base_multiplier
