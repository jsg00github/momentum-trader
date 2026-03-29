"""
Exit Strategy Manager - Professional Trade Management

Based on methodologies from:
- Mark Minervini (Cut losses at 7-8%, trail winners)
- William O'Neil (Multi-target profit taking)
- Stan Weinstein (Stage shift exits)

Exit Rules:
1. Initial stop: 7-8% or key support (whichever is closer)
2. Raise to breakeven after 20% gain
3. Trail stops as position grows
4. Exit on distribution signs
5. Exit on stage shifts (Stage 2 → 3)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import indicators


def evaluate_exit_signals(
    ticker: str,
    entry_price: float,
    current_price: float,
    stop_loss: float,
    peak_price: float,
    df: pd.DataFrame,
    position_shares: int = 0
) -> Dict:
    """
    Comprehensive exit analysis combining multiple professional methods.
    
    Returns recommendations with clear rationale and urgency level.
    
    Args:
        ticker: Stock symbol
        entry_price: Original entry price
        current_price: Current market price
        stop_loss: Current stop loss
        peak_price: Highest price reached since entry
        df: Price dataframe
        position_shares: Number of shares held
        
    Returns:
        Dict with action, urgency, and detailed reasoning
    """
    signals = []
    urgency_scores = []
    
    current_gain_pct = (current_price - entry_price) / entry_price
    
    # Signal 1: Stop Loss Check (HIGHEST PRIORITY)
    stop_signal = _check_stop_loss(current_price, stop_loss, entry_price)
    if stop_signal['triggered']:
        return stop_signal  # Immediate exit
    
    # Signal 2: Distribution Detection (O'Neil)
    dist_signal = _detect_distribution(df)
    if dist_signal['severity'] != 'NONE':
        signals.append(dist_signal)
        urgency_scores.append(dist_signal['urgency_score'])
    
    # Signal 3: Stage Shift (Weinstein)
    stage_signal = _check_stage_shift(df, current_price)
    if stage_signal['should_exit']:
        signals.append(stage_signal)
        urgency_scores.append(stage_signal['urgency_score'])
    
    # Signal 4: Weekly RSI Deterioration
    rsi_signal = _check_rsi_warning(df)
    if rsi_signal['warning_level'] != 'NONE':
        signals.append(rsi_signal)
        urgency_scores.append(rsi_signal['urgency_score'])
    
    # Signal 5: Profit-Taking Levels (Minervini multi-target)
    profit_signal = _check_profit_targets(current_gain_pct, position_shares)
    if profit_signal['should_take_profit']:
        signals.append(profit_signal)
        urgency_scores.append(profit_signal.get('urgency_score', 30))
    
    # Signal 6: Trailing Stop Update
    trail_signal = _calculate_trailing_stop_update(
        entry_price, current_price, peak_price, current_gain_pct
    )
    
    # Synthesize all signals into final recommendation
    if not signals:
        return {
            'action': 'HOLD',
            'urgency': 'NONE',
            'percent_to_sell': 0,
            'new_stop': trail_signal['stop_price'],
            'rationale': [
                f"✓ All systems green - Position up {current_gain_pct*100:.1f}%",
                f"✓ Updated trailing stop to ${trail_signal['stop_price']:.2f}",
                f"✓ Stop phase: {trail_signal['phase']}"
            ],
            'signals_checked': ['Stop Loss', 'Distribution', 'Stage', 'RSI', 'Targets'],
            'next_target': profit_signal.get('next_target_pct', 20)
        }
    
    # Determine overall urgency
    max_urgency = max(urgency_scores) if urgency_scores else 0
    
    if max_urgency >= 90:
        action = 'EXIT'
        urgency = 'IMMEDIATE'
        pct_to_sell = 100
    elif max_urgency >= 70:
        action = 'REDUCE'
        urgency = 'HIGH'
        pct_to_sell = 50
    elif max_urgency >= 50:
        action = 'REDUCE'
        urgency = 'MEDIUM'
        pct_to_sell = 30
    else:
        action = 'HOLD'
        urgency = 'LOW'
        pct_to_sell = 0
    
    # Compile rationale
    rationale = [sig.get('message', sig.get('reason', '')) for sig in signals]
    
    return {
        'action': action,
        'urgency': urgency,
        'percent_to_sell': pct_to_sell,
        'new_stop': trail_signal['stop_price'],
        'rationale': rationale,
        'signals': signals,
        'lesson': _generate_lesson(signals, current_gain_pct)
    }


def _check_stop_loss(current_price: float, stop_loss: float, entry_price: float) -> Dict:
    """Check if stop loss has been hit"""
    loss_pct = (current_price - entry_price) / entry_price
    
    if current_price <= stop_loss:
        return {
            'triggered': True,
            'action': 'EXIT',
            'urgency': 'IMMEDIATE',
            'percent_to_sell': 100,
            'reason': f'🛑 STOP LOSS HIT at ${stop_loss:.2f} (Loss: {loss_pct*100:.1f}%)',
            'lesson': 'Honoring your stop is how professionals preserve capital. This is the #1 rule.',
            'urgency_score': 100
        }
    
    # Also check if loss exceeds 7-8% (Minervini hard rule)
    if loss_pct <= -0.075:
        return {
            'triggered': True,
            'action': 'EXIT',
            'urgency': 'IMMEDIATE',
            'percent_to_sell': 100,
            'reason': f'🛑 LOSS EXCEEDS -7.5% RULE (Current: {loss_pct*100:.1f}%)',
            'lesson': 'Minervini: Never let losses exceed 7-8%. This protects you from catastrophic losses.',
            'urgency_score': 100
        }
    
    return {'triggered': False}


def _detect_distribution(df: pd.DataFrame) -> Dict:
    """
    Detect institutional distribution (selling).
    
    O'Neil Distribution Day:
    - Index/stock down >0.2% on volume higher than previous day
    - Multiple distribution days in short period = topping
    """
    try:
        if len(df) < 10:
            return {'severity': 'NONE', 'urgency_score': 0}
        
        recent = df.tail(10)
        dist_days = 0
        
        for i in range(1, len(recent)):
            day = recent.iloc[i]
            prev = recent.iloc[i-1]
            
            price_down = (day['Close'] - prev['Close']) / prev['Close'] < -0.002
            volume_up = day['Volume'] > prev['Volume'] * 1.1  # 10% higher volume
            
            if price_down and volume_up:
                dist_days += 1
        
        # Also check for single massive volume sell-off
        latest_vol = recent['Volume'].iloc[-1]
        avg_vol = recent['Volume'].iloc[:-1].mean()
        volume_spike = latest_vol > avg_vol * 2.0  # 2x volume
        latest_decline = (recent['Close'].iloc[-1] - recent['Close'].iloc[-2]) / recent['Close'].iloc[-2]
        
        if dist_days >= 3:
            return {
                'type': 'Distribution',
                'severity': 'HIGH',
                'message': f'⚠ {dist_days} distribution days detected in last 10 days - Institutions selling',
                'reason': 'Multiple distribution days (O\'Neil warning sign)',
                'urgency_score': 75
            }
        elif volume_spike and latest_decline < -0.03:
            return {
                'type': 'Distribution',
                'severity': 'MEDIUM',
                'message': f'⚠ Heavy volume sell-off detected (2x avg volume, -3%+)',
                'reason': 'Single-day distribution event',
                'urgency_score': 65
            }
        elif dist_days >= 1:
            return {
                'type': 'Distribution',
                'severity': 'LOW',
                'message': f'ℹ {dist_days} distribution day noted - Monitor closely',
                'reason': 'Early distribution warning',
                'urgency_score': 40
            }
        
        return {'severity': 'NONE', 'urgency_score': 0}
        
    except:
        return {'severity': 'NONE', 'urgency_score': 0}


def _check_stage_shift(df: pd.DataFrame, current_price: float) -> Dict:
    """
    Check for Weinstein Stage shift (Stage 2 → Stage 3 = EXIT)
    """
    try:
        stage_data = indicators.calculate_weinstein_stage(df, current_price)
        
        if stage_data['stage'] == 3:
            return {
                'should_exit': True,
                'type': 'Stage Shift',
                'message': f'🔴 Weinstein Stage 3 (Topping) - Uptrend ending',
                'reason': 'Stage shifted from 2 (Uptrend) to 3 (Distribution)',
                'urgency_score': 80
            }
        elif stage_data['stage'] == 4:
            return {
                'should_exit': True,
                'type': 'Stage Shift',
                'message': f'🔴 Weinstein Stage 4 (Downtrend) - EXIT IMMEDIATELY',
                'reason': 'Entered downtrend - all trend-following trades must exit',
                'urgency_score': 95
            }
        
        return {'should_exit': False, 'urgency_score': 0}
        
    except:
        return {'should_exit': False, 'urgency_score': 0}


def _check_rsi_warning(df: pd.DataFrame) -> Dict:
    """
    Check Weekly RSI for trend deterioration
    """
    try:
        rsi_data = indicators.calculate_weekly_rsi_analytics(df)
        
        if not rsi_data:
            return {'warning_level': 'NONE', 'urgency_score': 0}
        
        # Check if RSI turned bearish (red)
        if rsi_data.get('color') == 'red':
            return {
                'warning_level': 'HIGH',
                'type': 'RSI Warning',
                'message': '⚠ Weekly RSI turned red - Momentum deteriorating',
                'reason': 'RSI crossed below SMA3/SMA14 - Trend weakening',
                'urgency_score': 60
            }
        elif rsi_data.get('color') in ['orange', 'pink']:
            return {
                'warning_level': 'MEDIUM',
                'type': 'RSI Warning',
                'message': 'ℹ Weekly RSI showing weakness (orange/pink)',
                'reason': 'RSI not confirming uptrend anymore',
                'urgency_score': 45
            }
        
        return {'warning_level': 'NONE', 'urgency_score': 0}
        
    except:
        return {'warning_level': 'NONE', 'urgency_score': 0}


def _check_profit_targets(current_gain_pct: float, position_shares: int) -> Dict:
    """
    Minervini Multi-Target Profit Taking
    
    Target 1: 20% gain → Sell 30% of position
    Target 2: 40% gain → Sell 40% of remaining
    Target 3: 50%+ gain → Trail remainder
    """
    targets = [
        {'gain': 0.20, 'sell_pct': 30, 'name': 'Target 1'},
        {'gain': 0.40, 'sell_pct': 40, 'name': 'Target 2'},
        {'gain': 0.60, 'sell_pct': 50, 'name': 'Target 3'}
    ]
    
    for target in targets:
        # Check if we're within 2% of target
        if abs(current_gain_pct - target['gain']) < 0.02:
            shares_to_sell = int(position_shares * target['sell_pct'] / 100)
            
            return {
                'should_take_profit': True,
                'type': 'Profit Target',
                'message': f'✓ {target["name"]} reached ({target["gain"]*100:.0f}%) - Take {target["sell_pct"]}% profit',
                'reason': f'Minervini profit-taking rule: Lock in gains at key milestones',
                'shares_to_sell': shares_to_sell,
                'urgency_score': 35  # Not urgent, but recommended
            }
    
    # Find next target
    next_target = next((t['gain'] for t in targets if t['gain'] > current_gain_pct), None)
    
    return {
        'should_take_profit': False,
        'next_target_pct': int(next_target * 100) if next_target else None
    }


def _calculate_trailing_stop_update(
    entry_price: float,
    current_price: float,
    peak_price: float,
    current_gain_pct: float
) -> Dict:
    """Calculate updated trailing stop based on Minervini rules"""
    
    if current_gain_pct < 0.20:
        # Initial phase - use original stop (7-8% from entry)
        stop = entry_price * 0.92
        phase = "Initial Stop (-8%)"
        
    elif current_gain_pct < 0.30:
        # Raise to breakeven
        stop = entry_price
        phase = "Breakeven (20%+ gain)"
        
    elif current_gain_pct < 0.50:
        # Trail 15% from peak
        stop = peak_price * 0.85
        phase = "Trailing 15% from peak"
        
    else:
        # Big winner - trail 20% from peak
        stop = peak_price * 0.80
        phase = "Big Winner - Trailing 20%"
    
    return {
        'stop_price': round(stop, 2),
        'phase': phase,
        'distance_pct': round((current_price - stop) / current_price, 3)
    }


def _generate_lesson(signals: list, current_gain_pct: float) -> Optional[str]:
    """Generate educational lesson based on exit signals"""
    
    if any(s.get('type') == 'Distribution' for s in signals):
        return ("Distribution days are institutional selling. When you see heavy volume on down days, "
                "it means smart money is exiting. Don't be the last one out.")
    
    if any(s.get('type') == 'Stage Shift' for s in signals):
        return ("Weinstein Stage shifts mark major trend changes. Stage 2 (uptrend) to Stage 3 (topping) "
                "is your signal to exit momentum longs. The easy money is made in Stage 2 only.")
    
    if current_gain_pct < 0:
        return ("Small losses are part of trading. The key is cutting them quickly at 7-8% (Minervini rule). "
                "This allows you to be wrong 50% of the time and still make money with 2:1 winners.")
    
    return None
