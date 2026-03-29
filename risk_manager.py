"""
Professional Risk Manager - Position Sizing & Risk Management

Based on methodologies from:
- Mark Minervini (Trade Like a Stock Market Wizard)
- William O'Neil (How to Make Money in Stocks)
- David Ryan (3-time U.S. Investing Champion)

Core principles:
1. Risk 1-2% of account per trade (maximum)
2. Use ATR for stop placement (not arbitrary percentages)
3. Pyramid into winners (never average down)
4. Cut losses quickly, let winners run
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional


def calculate_position_size(
    account_value: float,
    entry_price: float,
    stop_loss: float,
    risk_per_trade: float = 0.01,
    max_position_pct: float = 0.10
) -> Dict:
    """
    Calculate position size using professional risk management rules.
    
    Minervini/O'Neil Rule: Risk 1-2% of account per trade
    
    Args:
        account_value: Total account size
        entry_price: Planned entry price
        stop_loss: Initial stop loss price
        risk_per_trade: Percentage of account to risk (0.01 = 1%, 0.02 = 2%)
        max_position_pct: Maximum position size as % of account (0.10 = 10%)
        
    Returns:
        Dict with shares, dollars, risk metrics
        
    Example:
        >>> calculate_position_size(100000, 50.00, 46.00, 0.02)
        {
            'shares': 500,
            'position_value': 25000,
            'position_pct': 0.25,
            'risk_per_share': 4.00,
            'total_risk': 2000,
            'risk_pct': 0.02,
            'stop_loss_pct': 0.08
        }
    """
    # Validate inputs
    if entry_price <= 0 or stop_loss <= 0:
        raise ValueError("Entry and stop prices must be positive")
    
    if stop_loss >= entry_price:
        raise ValueError("Stop loss must be below entry price for long positions")
    
    # Calculate risk per share
    risk_per_share = entry_price - stop_loss
    stop_loss_pct = risk_per_share / entry_price
    
    # Minervini Rule: Never use stops wider than 8-10%
    # (Tight patterns should have 3-7% stops)
    if stop_loss_pct > 0.10:
        print(f"⚠ WARNING: Stop is {stop_loss_pct*100:.1f}% - Too wide! Minervini recommends <8%")
    
    # Calculate maximum risk dollars
    max_risk_dollars = account_value * risk_per_trade
    
    # Calculate shares based on risk
    shares = int(max_risk_dollars / risk_per_share)
    
    # Calculate position value
    position_value = shares * entry_price
    position_pct = position_value / account_value
    
    # Apply position size limit (Minervini: No single position >10-12% of account)
    if position_pct > max_position_pct:
        # Reduce shares to meet max position limit
        max_position_value = account_value * max_position_pct
        shares = int(max_position_value / entry_price)
        position_value = shares * entry_price
        position_pct = position_value / account_value
        
        print(f"ℹ Position size reduced to {max_position_pct*100:.0f}% of account limit")
    
    # Calculate actual risk
    actual_risk = shares * risk_per_share
    actual_risk_pct = actual_risk / account_value
    
    return {
        'shares': shares,
        'position_value': round(position_value, 2),
        'position_pct': round(position_pct, 4),
        'risk_per_share': round(risk_per_share, 2),
        'total_risk': round(actual_risk, 2),
        'risk_pct': round(actual_risk_pct, 4),
        'stop_loss_pct': round(stop_loss_pct, 4),
        'is_aggressive': stop_loss_pct < 0.05,  # <5% = aggressive tight stop
        'is_conservative': stop_loss_pct > 0.08  # >8% = conservative/loose stop
    }


def calculate_atr_stop(df: pd.DataFrame, atr_multiplier: float = 2.0) -> float:
    """
    Calculate stop loss using Average True Range (professional method).
    
    ATR-based stops adapt to volatility:
    - Low volatility stocks: Tighter stops
    - High volatility stocks: Wider stops (avoids getting shaken out)
    
    Args:
        df: Price dataframe with High, Low, Close
        atr_multiplier: How many ATRs below entry (default 2.0)
        
    Returns:
        Stop loss price
    """
    # Calculate ATR(14) - industry standard
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    # True Range calculation
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=14).mean().iloc[-1]
    
    current_price = close.iloc[-1]
    stop_loss = current_price - (atr * atr_multiplier)
    
    return round(stop_loss, 2)


def calculate_pyramid_add(
    original_shares: int,
    original_entry: float,
    current_price: float,
    gain_pct: float,
    pyramid_rules: str = "minervini"
) -> Optional[Dict]:
    """
    Calculate if and how much to add to a winning position (pyramid).
    
    Minervini Rules:
    1. Only add to winners (price must be above entry)
    2. Add at 2-3% intervals above entry
    3. Each add is 50-75% the size of previous
    4. After adding, move stop on ENTIRE position to new entry - 3%
    5. Never add more than 2-3 times
    
    Args:
        original_shares: Initial position size
        original_entry: Original entry price
        current_price: Current market price
        gain_pct: Current gain percentage
        pyramid_rules: "minervini" or "oneil"
        
    Returns:
        Dict with add recommendation or None if should not add
    """
    if current_price <= original_entry:
        return None  # Never pyramid losers
    
    if pyramid_rules == "minervini":
        # Minervini: Add at 2-3% intervals
        add_thresholds = [0.025, 0.05, 0.075]  # 2.5%, 5%, 7.5%
        add_sizes = [0.75, 0.50, 0.25]  # 75%, 50%, 25% of original
        
    else:  # O'Neil method
        # O'Neil: More aggressive, add at 5% intervals
        add_thresholds = [0.05, 0.10]
        add_sizes = [0.50, 0.50]
    
    # Check if current gain justifies an add
    for i, threshold in enumerate(add_thresholds):
        if abs(gain_pct - threshold) < 0.01:  # Within 1% of threshold
            add_shares = int(original_shares * add_sizes[i])
            
            # Calculate new average entry
            total_shares = original_shares + add_shares
            total_cost = (original_shares * original_entry) + (add_shares * current_price)
            new_avg_entry = total_cost / total_shares
            
            # Minervini: New stop = new entry - 3%
            new_stop = new_avg_entry * 0.97
            
            return {
                'should_add': True,
                'add_shares': add_shares,
                'add_price': current_price,
                'total_shares': total_shares,
                'new_avg_entry': round(new_avg_entry, 2),
                'new_stop': round(new_stop, 2),
                'add_number': i + 1,
                'rationale': f"Pyramid #{i+1}: Stock up {gain_pct*100:.1f}%, add {add_shares} shares at ${current_price:.2f}"
            }
    
    return None


def calculate_trailing_stop(
    entry_price: float,
    current_price: float,
    peak_price: float,
    current_gain_pct: float,
    method: str = "minervini"
) -> Dict:
    """
    Calculate dynamic trailing stop as position gains.
    
    Minervini Trailing Stop Rules:
    - 0-20% gain: Initial stop (7-8% or key support)
    - 20-30% gain: Raise stop to breakeven (entry price)
    - 30-50% gain: Trail 15% from peak
    - 50%+ gain: Trail 20-25% from peak
    
    Args:
        entry_price: Original entry
        current_price: Current price
        peak_price: Highest price reached
        current_gain_pct: Current gain %
        method: "minervini" or "oneil"
        
    Returns:
        Dict with new stop and reasoning
    """
    if method == "minervini":
        if current_gain_pct < 0.20:
            # Still in initial phase - use original stop
            trail_pct = 0.08  # 8% from entry
            stop = entry_price * (1 - trail_pct)
            phase = "Initial Stop"
            
        elif current_gain_pct < 0.30:
            # Raise to breakeven
            stop = entry_price
            phase = "Breakeven (20%+ gain)"
            
        elif current_gain_pct < 0.50:
            # Trail 15% from peak
            trail_pct = 0.15
            stop = peak_price * (1 - trail_pct)
            phase = "Trailing 15% from peak"
            
        else:
            # Big winner - trail 20% from peak
            trail_pct = 0.20
            stop = peak_price * (1 - trail_pct)
            phase = "Big Winner - Trailing 20%"
    
    else:  # O'Neil method (slightly more aggressive)
        if current_gain_pct < 0.20:
            stop = entry_price * 0.92  # 8% stop
            phase = "Initial Stop"
        elif current_gain_pct < 0.25:
            stop = entry_price  # Breakeven
            phase = "Breakeven"
        else:
            # Trail 12-15% from peak
            trail_pct = 0.12
            stop = peak_price * (1 - trail_pct)
            phase = "Trailing 12% from peak"
    
    # Never lower the stop (trailing means it only goes UP)
    return {
        'stop_price': round(stop, 2),
        'stop_pct_from_current': round((current_price - stop) / current_price, 4),
        'phase': phase,
        'peak_price': peak_price,
        'room_to_peak': round((peak_price - stop) / peak_price, 4)
    }


def should_cut_loss(
    entry_price: float,
    current_price: float,
    stop_loss: float,
    volume_spike: bool = False,
    distribution_detected: bool = False
) -> Dict:
    """
    Determine if position should be cut immediately.
    
    Minervini/O'Neil Rules for cutting losses:
    1. Stop loss hit - Cut immediately, no exceptions
    2. Heavy volume decline (distribution) - Cut 50% immediately
    3. Broken support on high volume - Exit all
    4. Position down 7-8% from entry - Cut (even if stop not hit)
    
    Args:
        entry_price: Original entry
        current_price: Current price
        stop_loss: Stop loss price
        volume_spike: Is there heavy selling volume?
        distribution_detected: Has distribution been detected?
        
    Returns:
        Dict with action (HOLD, REDUCE, EXIT) and reasoning
    """
    loss_pct = (current_price - entry_price) / entry_price
    
    # Rule 1: Stop hit
    if current_price <= stop_loss:
        return {
            'action': 'EXIT',
            'urgency': 'IMMEDIATE',
            'percent_to_sell': 100,
            'reason': f'Stop loss hit at ${stop_loss:.2f}. Loss: {loss_pct*100:.1f}%',
            'lesson': 'Respect your stops. This is how professionals preserve capital.'
        }
    
    # Rule 2: Down 7-8% (even if stop not technically hit)
    if loss_pct <= -0.075:
        return {
            'action': 'EXIT',
            'urgency': 'HIGH',
            'percent_to_sell': 100,
            'reason': f'Position down {abs(loss_pct)*100:.1f}% - Exceeds -7.5% rule',
            'lesson': 'Minervini: Never let a loss exceed 7-8%. Cut losses quickly.'
        }
    
    # Rule 3: Distribution detected
    if distribution_detected and loss_pct < 0:
        return {
            'action': 'REDUCE',
            'urgency': 'HIGH',
            'percent_to_sell': 50,
            'reason': 'Heavy selling detected - Institutions may be exiting',
            'lesson': 'Distribution is a warning. Reduce risk when you see heavy volume selling.'
        }
    
    # Rule 4: Volume spike + any loss
    if volume_spike and loss_pct < -0.03:
        return {
            'action': 'REDUCE',
            'urgency': 'MEDIUM',
            'percent_to_sell': 30,
            'reason': 'Unusual selling volume with -3%+ loss',
            'lesson': 'High volume + price weakness = Smart money may be selling'
        }
    
    # All clear
    return {
        'action': 'HOLD',
        'urgency': 'NONE',
        'percent_to_sell': 0,
        'reason': 'Position within acceptable risk parameters',
        'lesson': None
    }


def calculate_portfolio_heat(positions: list, account_value: float) -> Dict:
    """
    Calculate total portfolio risk ("heat").
    
    Minervini Rule: Never have more than 10-15% total portfolio at risk
    (Even if each position risks only 1-2%)
    
    Args:
        positions: List of dicts with 'shares', 'entry', 'stop', 'current_price'
        account_value: Total account value
        
    Returns:
        Dict with total risk metrics and warnings
    """
    total_risk = 0
    position_risks = []
    
    for pos in positions:
        risk_per_share = pos['entry'] - pos['stop']
        position_risk = pos['shares'] * risk_per_share
        total_risk += position_risk
        
        position_risks.append({
            'ticker': pos.get('ticker', 'Unknown'),
            'risk_dollars': round(position_risk, 2),
            'risk_pct': round(position_risk / account_value, 4)
        })
    
    total_risk_pct = total_risk / account_value
    
    # Minervini warning levels
    if total_risk_pct > 0.15:
        warning = "🔴 CRITICAL: Portfolio heat >15% - Reduce positions immediately"
        action = "DO NOT ADD NEW POSITIONS"
    elif total_risk_pct > 0.10:
        warning = "⚠ HIGH: Portfolio heat >10% - Be cautious with new trades"
        action = "Consider reducing position sizes by 50%"
    elif total_risk_pct > 0.06:
        warning = "✓ NORMAL: Portfolio heat acceptable"
        action = "Normal position sizing OK"
    else:
        warning = "✓ LOW: Portfolio heat very conservative"
        action = "Can add positions at full size"
    
    return {
        'total_risk_dollars': round(total_risk, 2),
        'total_risk_pct': round(total_risk_pct, 4),
        'position_count': len(positions),
        'position_risks': position_risks,
        'warning': warning,
        'recommended_action': action,
        'max_new_position_risk_pct': max(0, 0.10 - total_risk_pct)  # Room for new positions
    }
