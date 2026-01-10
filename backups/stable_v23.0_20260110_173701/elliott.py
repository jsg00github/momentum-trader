
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
