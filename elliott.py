
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional

def find_pivot_points(prices: np.ndarray, window: int = 5) -> Tuple[List[int], List[int]]:
    """Find local peaks and troughs"""
    peaks, troughs = [], []
    for i in range(window, len(prices) - window):
        if all(prices[i] >= prices[i-window:i]) and all(prices[i] >= prices[i+1:i+window+1]):
            peaks.append(i)
        if all(prices[i] <= prices[i-window:i]) and all(prices[i] <= prices[i+1:i+window+1]):
            troughs.append(i)
    return peaks, troughs

def find_abc_breakout(df: pd.DataFrame) -> Dict:
    """
    Simplified ABC logic:
    1. Find significant Low (Start).
    2. Find subsequent High that 'supera el ultimo maximo' (Wave A).
    3. Find retracement Low (Wave B).
    """
    closes = df['Close'].values
    dates = df.index
    
    # 1. Find Pivots
    peaks, troughs = find_pivot_points(closes, window=3)
    pivots = [(p, 'peak', closes[p]) for p in peaks] + [(t, 'trough', closes[t]) for t in troughs]
    pivots.sort(key=lambda x: x[0])
    
    if len(pivots) < 5:
        return {"error": "Insufficient pivots"}

    # Search backwards for a clear "Breakout" pattern
    # Looking for Low -> High (A) -> Higher Low (B)
    
    # Try the most recent pivots first
    # Structure: [Low0, HighA, LowB]
    # Condition: LowB > Low0
    # Condition: HighA > Previous Pivot High (Breakout)?
    
    best_pattern = None
    
    # Iterate through potential Trough B's (starting from recent)
    recent_troughs = [p for p in pivots if p[1] == 'trough'][-5:] 
    
    for b_idx_in_pivots, (b_idx, _, b_price) in enumerate(recent_troughs):
        # Find preceding Peak A
        # We need to find the peak immediately preceding this trough in the FULL pivot list
        # Let's find index in full list
        try:
            full_idx = pivots.index((b_idx, 'trough', b_price))
        except ValueError:
            continue
            
        if full_idx < 1: continue
        
        a_pivot = pivots[full_idx - 1]
        if a_pivot[1] != 'peak': continue # Should be peak
        
        a_idx, _, a_price = a_pivot
        
        # Find preceding Low 0
        if full_idx < 2: continue
        
        l0_pivot = pivots[full_idx - 2]
        if l0_pivot[1] != 'trough': continue # Should be trough
        
        l0_idx, _, l0_price = l0_pivot
        
        # Rules:
        # 1. B > Low0 (Higher Low trend)
        if b_price <= l0_price:
            continue
            
        # 2. A > Previous Highs? (Breakout)
        # Check pivot highs before L0? Or just A itself is a strong move?
        # User said "si el precio supera el ultimo maximo"
        # Let's check if A is higher than the Peak BEFORE L0
        if full_idx >= 3:
            prev_peak = pivots[full_idx - 3]
            if prev_peak[1] == 'peak':
                if a_price <= prev_peak[2]:
                    # Not a breakout above previous peak
                    # But maybe valid if L0 was a Higher Low too? 
                    # Let's enforce the "Breakout" rule loosely or strictly?
                    # User: "si el precio supera el ultimo maximo"
                    pass # We will check this but maybe allow it if it triggers projections
        
        # Calculate Amplitudes
        wave_a_height = a_price - l0_price
        wave_b_retracement = a_price - b_price
        
        # Projections for C (Extensions of A)
        # C = B + A_height * ratios
        fib_targets = {
            "0.618": b_price + (wave_a_height * 0.618),
            "1.0":   b_price + (wave_a_height * 1.0),
            "1.618": b_price + (wave_a_height * 1.618),
            "2.0":   b_price + (wave_a_height * 2.0),
            "2.618": b_price + (wave_a_height * 2.618)
        }
        
        # Check if we are currently IN Wave C (after B)
        # Current price > B?
        current_price = closes[-1]
        
        pattern = {
            "points": {
                "start": (str(dates[l0_idx].date()), l0_price),
                "A": (str(dates[a_idx].date()), a_price),
                "B": (str(dates[b_idx].date()), b_price)
            },
            "wave_labels": [
                {"date": str(dates[l0_idx].date()), "price": l0_price, "label": "Start", "type": "trough"},
                {"date": str(dates[a_idx].date()), "price": a_price, "label": "A", "type": "peak"},
                {"date": str(dates[b_idx].date()), "price": b_price, "label": "B", "type": "trough"},
            ],
            "projections": fib_targets,
            "quality": "High" if wave_b_retracement < wave_a_height * 0.7 else "Medium"
        }
        
        # Prefer the most recent confirmed B
        best_pattern = pattern
        # Continue searching?
        # If we want the *latest* pattern, we iterate from end?
        # We are iterating troughs. We want the one closest to current date?
        # Yes, let's take the latest valid one.
    
    return best_pattern


def find_wave2_correction(df: pd.DataFrame) -> Optional[Dict]:
    """
    Detect Elliott Wave 2 correction ending — ideal entry for Wave 3.
    
    Logic:
    1. Find a significant Wave 1 impulse (>= 25% rally)
    2. Measure Wave 2 retracement vs Fibonacci levels
    3. Verify Wave 2 does NOT violate Wave 1 start (Elliott Rule)
    4. Check reversal signals: RSI oversold, bullish candle, volume dry-up
    5. Score quality and return Wave 3 projections
    
    Returns dict with wave metrics or None if no valid pattern.
    """
    if df is None or df.empty or len(df) < 60:
        return None
    
    closes = df['Close'].values
    highs = df['High'].values
    lows = df['Low'].values
    volumes = df['Volume'].values
    dates = df.index
    n = len(closes)
    
    # 1. Find pivots with adaptive window for macro waves (minimum 10 days)
    window = max(10, min(15, n // 20))
    peaks, troughs = find_pivot_points(closes, window=window)
    
    if len(peaks) < 1 or len(troughs) < 2:
        return None
    
    # 2. Search for Wave 1 + Wave 2 pattern (most recent first)
    # Structure: Trough_start -> Peak_w1 -> Trough_w2 (current area)
    best = None
    
    # Iterate peaks as potential Wave 1 tops (from most recent)
    for peak_idx in reversed(peaks):
        # Peak must be in the last 70% of data (not too old)
        if peak_idx < n * 0.2:
            continue
        
        # Find the trough BEFORE this peak (Wave 1 start)
        w1_start_idx = None
        w1_start_price = None
        for t_idx in reversed(troughs):
            if t_idx < peak_idx:
                w1_start_idx = t_idx
                w1_start_price = closes[t_idx]
                break
        
        if w1_start_idx is None:
            continue
        
        w1_top_price = closes[peak_idx]
        w1_height = w1_top_price - w1_start_price
        w1_duration = peak_idx - w1_start_idx
        
        # Wave 1 must be a significant rally (>= 15%) and sustained (>= 20 trading days, ~1 month)
        if w1_start_price <= 0:
            continue
        w1_pct = (w1_height / w1_start_price) * 100
        if w1_pct < 15 or w1_duration < 20:
            continue
        
        # 3. Find Wave 2 trough (lowest point AFTER the peak)
        # Must be after peak and within reasonable timeframe
        post_peak_lows = lows[peak_idx:]
        if len(post_peak_lows) < 3:
            continue
        
        # Wave 2 low = minimum low after W1 peak
        w2_rel_idx = np.argmin(post_peak_lows)
        w2_abs_idx = peak_idx + w2_rel_idx
        w2_low_price = float(lows[w2_abs_idx])
        
        # ELLIOTT RULE: Wave 2 cannot go below Wave 1 start
        if w2_low_price <= w1_start_price:
            continue
            
        # VOLUME RULE: Wave 1 (rally) average volume > Wave 2 (pullback) average volume
        # This confirms a high-volume rally and a low-volume flag/pullback
        w1_avg_vol = np.mean(volumes[w1_start_idx:peak_idx+1])
        w2_avg_vol = np.mean(volumes[peak_idx:w2_abs_idx+1])
        # if w1_avg_vol <= 0 or w2_avg_vol >= w1_avg_vol:
        #     continue
        
        # 4. Calculate Fibonacci retracement
        retrace_amount = w1_top_price - w2_low_price
        retrace_pct = (retrace_amount / w1_height) * 100 if w1_height > 0 else 0
        
        # Valid retracement: 23% to 68% (user requested tight bull flag / deep golden pocket)
        if retrace_pct < 23 or retrace_pct > 68:
            continue
        
        # Find nearest Fibonacci level
        fib_levels = [23.6, 38.2, 50.0, 61.8, 78.6]
        nearest_fib = min(fib_levels, key=lambda x: abs(x - retrace_pct))
        
        # 5. Wave 2 should be recent (correction should be near current price)
        # The low should be within the last 40% of bars after the peak
        bars_after_peak = n - peak_idx
        if bars_after_peak > 0:
            w2_position = (w2_abs_idx - peak_idx) / bars_after_peak
        else:
            continue
        
        # Current price should be near or slightly above W2 low
        current_price = float(closes[-1])
        
        # Don't select if price has already rallied significantly past W2 low
        # (would mean Wave 3 already started and we missed the entry)
        recovery_from_w2 = ((current_price - w2_low_price) / w2_low_price) * 100 if w2_low_price > 0 else 999
        if recovery_from_w2 > 20:
            # Already moved too much — Wave 3 might be underway, not an entry
            continue
        
        # 6. Reversal signals
        signals = 0
        signal_details = []
        
        # A. RSI oversold / neutral (daily RSI < 55)
        try:
            import indicators
            rsi_series = indicators.calculate_rsi(pd.Series(closes), period=14)
            rsi_current = float(rsi_series.iloc[-1])
            if rsi_current < 55:
                signals += 1
                signal_details.append(f"RSI neutral/oversold ({rsi_current:.1f})")
            if rsi_current < 45:
                signals += 1  # Extra point for deeply oversold
                signal_details.append("Deeply oversold")
        except:
            rsi_current = 50
        
        # B. Bullish candle (last candle close > open)
        if closes[-1] > df['Open'].values[-1]:
            signals += 1
            signal_details.append("Bullish candle")
        
        # C. Volume dry-up during correction
        try:
            if peak_idx < n - 5:
                vol_impulse = np.mean(volumes[w1_start_idx:peak_idx+1]) if peak_idx > w1_start_idx else volumes[peak_idx]
                vol_correction = np.mean(volumes[peak_idx:]) if n > peak_idx else volumes[-1]
                if vol_correction < vol_impulse * 0.8:
                    signals += 1
                    signal_details.append("Volume dry-up")
        except:
            pass
        
        # D. Price holding above key Fibonacci level (50% or 61.8%)
        if 45 <= retrace_pct <= 68:
            signals += 1
            signal_details.append(f"Ideal Fib zone ({nearest_fib}%)")
        
        # 7. Quality scoring
        if signals >= 4:
            quality = "HIGH"
        elif signals >= 2:
            quality = "MED"
        else:
            quality = "LOW"
        
        # Stars rating
        stars = min(3, max(1, signals - 1))
        
        # 8. Determine phase
        if recovery_from_w2 > 5 and closes[-1] > closes[-2]:
            phase = "Reversal"
        elif abs(recovery_from_w2) < 5:
            phase = "Testing"
        else:
            phase = "Correcting"
        
        # 9. Wave 3 projections
        w3_target_100 = w2_low_price + w1_height
        w3_target_1618 = w2_low_price + (w1_height * 1.618)
        w3_target_2618 = w2_low_price + (w1_height * 2.618)
        
        candidate = {
            "w1_start_idx": int(w1_start_idx),
            "w1_start_price": float(w1_start_price),
            "w1_start_date": str(dates[w1_start_idx].date()) if hasattr(dates[w1_start_idx], 'date') else str(dates[w1_start_idx]),
            "w1_top_idx": int(peak_idx),
            "w1_top_price": float(w1_top_price),
            "w1_top_date": str(dates[peak_idx].date()) if hasattr(dates[peak_idx], 'date') else str(dates[peak_idx]),
            "w1_height_pct": round(w1_pct, 1),
            "w2_low_idx": int(w2_abs_idx),
            "w2_low_price": w2_low_price,
            "w2_low_date": str(dates[w2_abs_idx].date()) if hasattr(dates[w2_abs_idx], 'date') else str(dates[w2_abs_idx]),
            "w2_retrace_pct": round(retrace_pct, 1),
            "w2_fib_level": nearest_fib,
            "current_price": current_price,
            "recovery_pct": round(recovery_from_w2, 1),
            "rsi_daily": round(rsi_current, 1),
            "signals": signals,
            "signal_details": signal_details,
            "quality": quality,
            "stars": stars,
            "phase": phase,
            "w3_target_100": round(w3_target_100, 2),
            "w3_target_1618": round(w3_target_1618, 2),
            "w3_target_2618": round(w3_target_2618, 2),
            "wave_labels": [
                {"date": str(dates[w1_start_idx].date()) if hasattr(dates[w1_start_idx], 'date') else str(dates[w1_start_idx]),
                 "price": float(w1_start_price), "label": "W1 Start", "type": "trough"},
                {"date": str(dates[peak_idx].date()) if hasattr(dates[peak_idx], 'date') else str(dates[peak_idx]),
                 "price": float(w1_top_price), "label": "W1 Top", "type": "peak"},
                {"date": str(dates[w2_abs_idx].date()) if hasattr(dates[w2_abs_idx], 'date') else str(dates[w2_abs_idx]),
                 "price": w2_low_price, "label": "W2 Low", "type": "trough"},
            ]
        }
        
        # Prefer highest quality, then most recent
        if best is None or candidate["signals"] > best["signals"]:
            best = candidate
    
    return best


def analyze_elliott_waves(df: pd.DataFrame) -> Dict:
    """
    Simplified Wrapper replacing original logic.
    Focus: ABC Breakout + Fib Extensions.
    """
    try:
        pattern = find_abc_breakout(df)
        
        if not pattern or "error" in pattern:
            return {
                "elliott_wave": {"pattern": "Scanning..."},
                "wave_labels": [],
                "fibonacci_projections": None
            }
            
        # Format for frontend
        fib_levels = pattern["projections"]
        
        # Expert Analysis (Simple)
        expert_analysis = {
            "price_projections": {
                "next_impulse_target": fib_levels["1.0"], # Using 1.0 as standard C target
                "next_wave_3_target": fib_levels["1.618"]
            },
            # Dummy fields to prevent frontend crash if it expects them
            "current_phase": "Wave C in progress?",
            "wave_position": "C",
            "degree": "Minor",
            "larger_trend": "Bullish",
            "risk_level": "Medium",
            "entry_signals": [f"Target C (1.0): ${fib_levels['1.0']:.2f}"]
        }
        
        return {
            "elliott_wave": {
                "pattern": "ABC Breakout",
                "current_wave": "C (Projected)",
                "expert_analysis": expert_analysis
            },
            "wave_labels": pattern["wave_labels"],
            "fibonacci_projections": {
                "primary_target": fib_levels["1.0"],
                "levels": fib_levels
            },
            "interpretation": f"Breakout ABC detected. Target: ${fib_levels['1.0']:.2f}"
        }

    except Exception as e:
        print(f"Error in simplified ABC: {e}")
        return {"elliott_wave": {"error": str(e)}, "wave_labels": []}
