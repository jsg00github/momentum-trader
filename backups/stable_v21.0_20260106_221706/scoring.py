"""
Scoring system for momentum candidates.

Scores each qualifying ticker from 0-100 based on:
- Momentum strength (40 pts)
- Consolidation quality (30 pts)
- Volume surge (15 pts)
- Breakout proximity (15 pts)
"""

def calculate_score(result: dict) -> float:
    """
    Calculate momentum score (0-100) for a qualifying ticker
    
    Args:
        result: Dictionary with keys:
            - ret_3m_pct: 3-month return percentage
            - ret_1m_pct: 1-month return percentage
            - ret_1w_pct: 1-week return percentage
            - close: current price
            - rally_high: highest price in 3M window
            - avg_vol_60: 60-day average volume (optional)
            - volume: current volume (optional)
    
    Returns:
        Score from 0-100
    """
    # If Weekly RSI Signal
    if "rsi" in result and "ema3" in result:
        rsi = result["rsi"]
        base_score = 50.0
        
        # 1. RSI Zone Scoring (30-50)
        if 30 <= rsi <= 50:
            # 30 -> +30 pts, 50 -> +10 pts
            rsi_score = 30 - ((rsi - 30) / 20 * 20)
            base_score += rsi_score
            
        # 2. Volume Trend Bonus (Phase 14)
        vol_ratio = result.get("vol_ratio", 1.0)
        if vol_ratio > 1.2:
            base_score += 20
        elif vol_ratio > 1.05:
            base_score += 10
            
        return min(100, round(base_score, 2))

    # Momentum Strategy Scoring (Default)
    score = 0.0
    
    # 1. Momentum Strength (0-40 points)
    # Scale: 90% → 0, 300% → 40
    ret_3m = result.get("ret_3m_pct", 0)
    if ret_3m >= 90:
        momentum_score = min(40, (ret_3m - 90) / 210 * 40)
        score += momentum_score
    
    # 2. Consolidation Quality (0-30 points)
    # Ideal pullback is -12.5% (midpoint of -25% to 0%)
    # Reward tickers close to this ideal
    ret_1m = result.get("ret_1m_pct", 0)
    ideal_pullback = -12.5
    
    if -25 <= ret_1m <= 0:
        # Distance from ideal
        distance = abs(ret_1m - ideal_pullback)
        # Max distance is 12.5 (from -25 or 0 to -12.5)
        consolidation_score = 30 * (1 - min(distance, 12.5) / 12.5)
        score += consolidation_score
    
    # 3. Volume Surge (0-15 points)
    # If current volume >> average, shows strong interest
    avg_vol = result.get("avg_vol_60")
    current_vol = result.get("volume")  # Would need to add this to result
    
    if avg_vol and current_vol and avg_vol > 0:
        vol_ratio = current_vol / avg_vol
        # 2x average volume = full points, cap at 3x
        volume_score = min(15, (vol_ratio - 1) * 15)
        score += volume_score
    else:
        # If no volume data, give neutral score
        score += 7.5
    
    # 4. Breakout Proximity (0-15 points)
    # Reward tickers consolidating near their 3M high
    close = result.get("close", 0)
    rally_high = result.get("rally_high", 0)
    
    if close > 0 and rally_high > 0:
        distance_pct = ((rally_high - close) / rally_high) * 100
        # Within 5% of high = full points, linear decay to 20%
        if distance_pct <= 5:
            proximity_score = 15
        elif distance_pct <= 20:
            proximity_score = 15 * (1 - (distance_pct - 5) / 15)
        else:
            proximity_score = 0
        score += proximity_score
    
    return round(score, 2)


def get_score_breakdown(result: dict) -> dict:
    """
    Get detailed breakdown of score components
    
    Returns dict with individual component scores
    """
    ret_3m = result.get("ret_3m_pct", 0)
    ret_1m = result.get("ret_1m_pct", 0)
    close = result.get("close", 0)
    rally_high = result.get("rally_high", 0)
    avg_vol = result.get("avg_vol_60")
    current_vol = result.get("volume")
    
    # Momentum
    momentum = min(40, (ret_3m - 90) / 210 * 40) if ret_3m >= 90 else 0
    
    # Consolidation
    ideal_pullback = -12.5
    if -25 <= ret_1m <= 0:
        distance = abs(ret_1m - ideal_pullback)
        consolidation = 30 * (1 - min(distance, 12.5) / 12.5)
    else:
        consolidation = 0
    
    # Volume
    if avg_vol and current_vol and avg_vol > 0:
        vol_ratio = current_vol / avg_vol
        volume = min(15, (vol_ratio - 1) * 15)
    else:
        volume = 7.5
    
    # Proximity
    if close > 0 and rally_high > 0:
        distance_pct = ((rally_high - close) / rally_high) * 100
        if distance_pct <= 5:
            proximity = 15
        elif distance_pct <= 20:
            proximity = 15 * (1 - (distance_pct - 5) / 15)
        else:
            proximity = 0
    else:
        proximity = 0
    
    return round(momentum + consolidation + volume + proximity, 2)


def score_to_grade(score: float) -> str:
    """
    Convert numeric score to letter grade
    
    A: 85-100 (Elite setups - highest probability)
    B: 70-84  (Strong setups - good risk/reward)
    C: 55-69  (Decent setups - selective trading)
    D: 0-54   (Marginal - usually skip)
    """
    if score >= 85:
        return "A"
    elif score >= 70:
        return "B"
    elif score >= 55:
        return "C"
    else:
        return "D"


def get_grade_description(grade: str) -> dict:
    """Get description and trading recommendation for grade"""
    descriptions = {
        "A": {
            "label": "Elite Setup",
            "description": "Strongest momentum + ideal consolidation + high volume",
            "action": "Prime candidate for aggressive position sizing",
            "color": "green"
        },
        "B": {
            "label": "Strong Setup", 
            "description": "Good momentum with solid consolidation pattern",
            "action": "Excellent risk/reward, standard position size",
            "color": "blue"
        },
        "C": {
            "label": "Decent Setup",
            "description": "Meets criteria but less ideal pattern",
            "action": "Selective - wait for better entry or confirmation",
            "color": "yellow"
        },
        "D": {
            "label": "Marginal",
            "description": "Barely qualifies, lower quality setup",
            "action": "Generally skip unless exceptional circumstances",
            "color": "gray"
        }
    }
    return descriptions.get(grade, descriptions["D"])
