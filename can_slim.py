"""
CAN SLIM Analyzer - William O'Neil's Proven Methodology

This module implements the complete CAN SLIM framework from 
"How to Make Money in Stocks" by William O'Neil.

CAN SLIM factors:
- C: Current Quarterly Earnings (25%+ growth)
- A: Annual Earnings Growth (3-5 year track record)
- N: New High, New Product, New Management
- S: Supply & Demand (Volume + Shares Outstanding)
- L: Leader or Laggard (RS Rating > 80)
- I: Institutional Sponsorship (Quality ownership)
- M: Market Direction (Trade with the market)
"""

import pandas as pd
import numpy as np
import yfinance as yf
from typing import Dict, Optional
import market_data


def calculate_can_slim_score(ticker: str, market_regime: str = "BULL") -> Optional[Dict]:
    """
    Calculate complete CAN SLIM score for a ticker.
    
    Args:
        ticker: Stock symbol
        market_regime: Current market phase (BULL, CORRECTION, BEAR)
        
    Returns:
        Dict with score breakdown or None if insufficient data
    """
    try:
        # Fetch price and fundamental data
        stock = yf.Ticker(ticker)
        info = stock.info
        df = market_data.safe_yf_download(ticker, period="2y", interval="1d", auto_adjust=False)
        
        if df is None or df.empty or len(df) < 252:
            return None
            
        # Handle MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # Calculate each CAN SLIM factor
        c_score = _calculate_c_factor(info)  # Current Earnings
        a_score = _calculate_a_factor(info)  # Annual Earnings
        n_score = _calculate_n_factor(df, info)  # New High
        s_score = _calculate_s_factor(df, info)  # Supply & Demand
        l_score = _calculate_l_factor(df, ticker)  # Leader/Laggard
        i_score = _calculate_i_factor(info)  # Institutional
        m_score = _calculate_m_factor(market_regime)  # Market Direction
        
        # Weighted scoring (O'Neil emphasis)
        # L (Relative Strength) is most important - 25%
        # C and A (Earnings) - 20% each
        # S (Supply/Demand) - 15%
        # N (New things) - 10%
        # I (Institutional) - 5%
        # M (Market) - 5%
        
        weights = {
            'C': 0.20,
            'A': 0.20,
            'N': 0.10,
            'S': 0.15,
            'L': 0.25,
            'I': 0.05,
            'M': 0.05
        }
        
        scores = {
            'C': c_score,
            'A': a_score,
            'N': n_score,
            'S': s_score,
            'L': l_score,
            'I': i_score,
            'M': m_score
        }
        
        # Calculate weighted total
        total_score = sum(scores[factor] * weights[factor] for factor in scores)
        
        # Grade assignment (O'Neil standards)
        if total_score >= 85:
            grade = "A+"
        elif total_score >= 80:
            grade = "A"
        elif total_score >= 70:
            grade = "B"
        elif total_score >= 60:
            grade = "C"
        else:
            grade = "D"
        
        return {
            "ticker": ticker,
            "total_score": round(total_score, 1),
            "grade": grade,
            "factor_scores": scores,
            "breakdown": _generate_breakdown(scores),
            "is_buyable": total_score >= 70 and l_score >= 80 and c_score >= 70
        }
        
    except Exception as e:
        print(f"Error calculating CAN SLIM for {ticker}: {e}")
        return None


def _calculate_c_factor(info: Dict) -> float:
    """
    C: Current Quarterly Earnings
    
    O'Neil Rule: Look for 25%+ EPS growth vs same quarter last year
    Premium stocks show 50-100%+ growth
    
    Scoring:
    100: >100% growth
    90: 75-100%
    80: 50-75%  
    70: 25-50%
    50: 10-25%
    0: <10%
    """
    try:
        # Try to get quarterly earnings growth
        eps_current_quarter = info.get('trailingEps', 0)
        eps_forward = info.get('forwardEps', eps_current_quarter)
        
        # Estimate growth (simplified - ideally use quarterly data)
        earnings_growth = info.get('earningsQuarterlyGrowth', 0)
        
        if earnings_growth is None:
            return 50  # Neutral if no data
        
        growth_pct = earnings_growth * 100
        
        if growth_pct >= 100:
            return 100
        elif growth_pct >= 75:
            return 90
        elif growth_pct >= 50:
            return 80
        elif growth_pct >= 25:
            return 70
        elif growth_pct >= 10:
            return 50
        else:
            return max(0, growth_pct * 2)  # Scale below 25%
            
    except:
        return 50


def _calculate_a_factor(info: Dict) -> float:
    """
    A: Annual Earnings Growth
    
    O'Neil Rule: 3-5 year track record of earnings growth
    Look for 25%+ annual growth, acceleration preferred
    
    Scoring based on 5-year earnings growth rate
    """
    try:
        # 5-year earnings growth
        earnings_growth_5y = info.get('earningsGrowth', None)
        
        if earnings_growth_5y is None:
            return 50
            
        growth_pct = earnings_growth_5y * 100
        
        # O'Neil standards
        if growth_pct >= 50:
            return 100
        elif growth_pct >= 30:
            return 85
        elif growth_pct >= 25:
            return 75
        elif growth_pct >= 15:
            return 60
        else:
            return max(0, growth_pct * 2)
            
    except:
        return 50


def _calculate_n_factor(df: pd.DataFrame, info: Dict) -> float:
    """
    N: New High, New Product, New Management
    
    O'Neil Rule: Best stocks make new 52-week highs BEFORE big moves
    Also look for new products, new management, industry changes
    
    Scoring:
    100: Within 5% of 52-week high
    80: Within 15% of high
    60: Within 25% of high  
    40: Within 35% of high
    20: >35% from high
    """
    try:
        current_price = df['Close'].iloc[-1]
        
        # 52-week high
        high_52w = df['High'].tail(252).max()
        
        distance_pct = ((high_52w - current_price) / high_52w) * 100
        
        # O'Neil: Best stocks are within 15% of new highs
        if distance_pct <= 5:
            return 100
        elif distance_pct <= 15:
            return 80
        elif distance_pct <= 25:
            return 60
        elif distance_pct <= 35:
            return 40
        else:
            return max(0, 100 - distance_pct)
            
    except:
        return 50


def _calculate_s_factor(df: pd.DataFrame, info: Dict) -> float:
    """
    S: Supply & Demand
    
    O'Neil Rule: Volume should surge on up days (50%+ above average)
    Smaller float is better (easier to move)
    Look for tight ownership
    
    Scoring combines:
    - Volume behavior (70% weight)
    - Shares outstanding (30% weight)
    """
    try:
        # Volume Analysis (O'Neil: "Big volume on up days")
        df_recent = df.tail(21)  # Last month
        
        # Separate up days vs down days
        df_recent['price_change'] = df_recent['Close'].pct_change()
        up_days = df_recent[df_recent['price_change'] > 0]
        down_days = df_recent[df_recent['price_change'] < 0]
        
        if len(up_days) == 0 or len(down_days) == 0:
            volume_score = 50
        else:
            avg_vol_up = up_days['Volume'].mean()
            avg_vol_down = down_days['Volume'].mean()
            
            # O'Neil: Up volume should exceed down volume
            if avg_vol_down > 0:
                vol_ratio = avg_vol_up / avg_vol_down
                
                if vol_ratio >= 1.5:  # 50% more volume on up days
                    volume_score = 100
                elif vol_ratio >= 1.2:
                    volume_score = 80
                elif vol_ratio >= 1.0:
                    volume_score = 60
                else:
                    volume_score = 40
            else:
                volume_score = 70
        
        # Shares Outstanding (smaller is better)
        shares_out = info.get('sharesOutstanding', 0)
        
        if shares_out == 0:
            supply_score = 50
        elif shares_out < 25_000_000:  # Small cap
            supply_score = 100
        elif shares_out < 100_000_000:  # Mid cap
            supply_score = 80
        elif shares_out < 500_000_000:
            supply_score = 60
        else:  # Large cap
            supply_score = 40
        
        # Weighted combination
        s_score = (volume_score * 0.7) + (supply_score * 0.3)
        return s_score
        
    except:
        return 50


def _calculate_l_factor(df: pd.DataFrame, ticker: str) -> float:
    """
    L: Leader or Laggard (Relative Strength)
    
    O'Neil Rule: RS Rating should be 80+ (top 20% of market)
    This is the MOST IMPORTANT factor in CAN SLIM
    
    Calculate RS vs SPY over multiple timeframes
    """
    try:
        # Download SPY for comparison
        spy_df = market_data.safe_yf_download("SPY", period="1y", interval="1d", auto_adjust=False)
        
        if spy_df is None or spy_df.empty:
            return 50
            
        if isinstance(spy_df.columns, pd.MultiIndex):
            spy_df.columns = spy_df.columns.get_level_values(0)
        
        # Align dates
        common_dates = df.index.intersection(spy_df.index)
        if len(common_dates) < 126:  # Need 6 months minimum
            return 50
            
        stock_prices = df.loc[common_dates, 'Close']
        spy_prices = spy_df.loc[common_dates, 'Close']
        
        # Calculate performance over multiple periods (O'Neil method)
        # 3 months (most weight), 6 months, 9 months, 12 months
        periods = [63, 126, 189, 252]
        weights = [0.40, 0.30, 0.20, 0.10]  # Recent performance matters more
        
        rs_scores = []
        for period in periods:
            if len(stock_prices) >= period:
                stock_return = (stock_prices.iloc[-1] / stock_prices.iloc[-period] - 1) * 100
                spy_return = (spy_prices.iloc[-1] / spy_prices.iloc[-period] - 1) * 100
                
                # Relative performance
                relative_perf = stock_return - spy_return
                
                # Score: 100 if 50%+ better than SPY, scale down
                if relative_perf >= 50:
                    score = 100
                elif relative_perf >= 25:
                    score = 85
                elif relative_perf >= 10:
                    score = 70
                elif relative_perf >= 0:
                    score = 60
                elif relative_perf >= -10:
                    score = 40
                else:
                    score = 20
                    
                rs_scores.append(score)
        
        if not rs_scores:
            return 50
            
        # Weighted average
        l_score = sum(score * weight for score, weight in zip(rs_scores, weights[:len(rs_scores)]))
        return l_score
        
    except Exception as e:
        print(f"Error calculating L factor: {e}")
        return 50


def _calculate_i_factor(info: Dict) -> float:
    """
    I: Institutional Sponsorship
    
    O'Neil Rule: Want a few quality institutions (not too many, not too few)
    Look for increasing ownership by top-performing funds
    
    Scoring based on institutional ownership percentage
    """
    try:
        inst_ownership = info.get('heldPercentInstitutions', 0)
        
        if inst_ownership is None:
            return 50
            
        ownership_pct = inst_ownership * 100
        
        # O'Neil sweet spot: 10-60% institutional ownership
        # Too low = no support, Too high = too crowded
        if 30 <= ownership_pct <= 60:
            return 100
        elif 20 <= ownership_pct < 30:
            return 85
        elif 10 <= ownership_pct < 20:
            return 70
        elif 60 < ownership_pct <= 75:
            return 70
        elif ownership_pct > 75:
            return 50  # Too crowded
        else:
            return 40  # Too low
            
    except:
        return 50


def _calculate_m_factor(market_regime: str) -> float:
    """
    M: Market Direction
    
    O'Neil Rule: 3 out of 4 stocks follow the market
    Don't fight the tape - trade with the market
    
    Scoring based on market regime
    """
    regime_scores = {
        "BULL_CONFIRMED": 100,
        "BULL": 100,
        "BULL_UNDER_PRESSURE": 60,
        "CORRECTION": 30,
        "BEAR": 0
    }
    
    return regime_scores.get(market_regime, 50)


def _generate_breakdown(scores: Dict) -> Dict:
    """Generate human-readable breakdown of CAN SLIM scores"""
    
    explanations = {
        'C': _explain_c(scores['C']),
        'A': _explain_a(scores['A']),
        'N': _explain_n(scores['N']),
        'S': _explain_s(scores['S']),
        'L': _explain_l(scores['L']),
        'I': _explain_i(scores['I']),
        'M': _explain_m(scores['M'])
    }
    
    return explanations


def _explain_c(score: float) -> str:
    if score >= 80:
        return "✓ Excellent earnings growth (>50% YoY)"
    elif score >= 70:
        return "✓ Strong earnings growth (25-50% YoY)"
    elif score >= 50:
        return "⚠ Moderate earnings growth (10-25%)"
    else:
        return "✗ Weak earnings growth (<10%)"


def _explain_a(score: float) -> str:
    if score >= 85:
        return "✓ Outstanding 5-year earnings record"
    elif score >= 75:
        return "✓ Solid long-term earnings growth"
    elif score >= 60:
        return "⚠ Acceptable earnings history"
    else:
        return "✗ Insufficient earnings growth track record"


def _explain_n(score: float) -> str:
    if score >= 80:
        return "✓ Near 52-week high - showing strength"
    elif score >= 60:
        return "⚠ Within striking distance of highs"
    else:
        return "✗ Far from 52-week high"


def _explain_s(score: float) -> str:
    if score >= 80:
        return "✓ Strong demand - Volume up on up days"
    elif score >= 60:
        return "⚠ Adequate volume patterns"
    else:
        return "✗ Weak volume - Selling pressure"


def _explain_l(score: float) -> str:
    if score >= 80:
        return "✓ MARKET LEADER - RS Rating 80+ (Top 20%)"
    elif score >= 70:
        return "⚠ Above average relative strength"
    elif score >= 60:
        return "⚠ Keeping up with market"
    else:
        return "✗ LAGGARD - Underperforming market"


def _explain_i(score: float) -> str:
    if score >= 85:
        return "✓ Ideal institutional support (30-60%)"
    elif score >= 70:
        return "✓ Good institutional backing"
    else:
        return "⚠ Sub-optimal institutional ownership"


def _explain_m(score: float) -> str:
    if score >= 90:
        return "✓ BULL MARKET - Go aggressive"
    elif score >= 60:
        return "⚠ Market under pressure - Be selective"
    elif score >= 30:
        return "⚠ CORRECTION - Reduce positions"
    else:
        return "✗ BEAR MARKET - Stay in cash"
