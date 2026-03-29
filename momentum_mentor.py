"""
Momentum Trading Mentor - Professional Trading Decision Engine

This is the CORE AI that replaces the basic ai_advisor.py with professional
methodology-based trading guidance.

Integrates:
- CAN SLIM scoring (William O'Neil)
- VCP pattern recognition (Mark Minervini)
- Weinstein Stage Analysis (Stan Weinstein)
- Risk management (Minervini/O'Neil/Ryan)
- Market regime awareness

The mentor provides clear BUY/HOLD/SELL decisions with detailed rationale
citing specific professional methodologies.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
import market_data
import can_slim
import risk_manager
import market_regime
import exit_manager
import screener
import indicators


def _sanitize_for_json(obj):
    """Recursively convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    return obj


class MomentumMentor:
    """
    Professional trading mentor that makes evidence-based decisions.
    """
    
    def __init__(self, account_value: float = 100000):
        """
        Initialize mentor with account details.
        
        Args:
            account_value: Current account size for position sizing
        """
        self.account_value = account_value
        self.market_regime_cache = None
        self.last_regime_update = None
        
    
    def analyze_entry_opportunity(self, ticker: str, df=None) -> Dict:
        """
        Comprehensive entry analysis combining all professional methodologies.
        
        Args:
            ticker: Stock symbol
            df: Optional pre-downloaded DataFrame (avoids re-downloading)
        
        Returns BUY/WAIT decision with complete rationale and execution plan.
        """
        try:
            # Get market environment (critical first step)
            regime = self._get_market_regime()
            
            # If market is bearish, don't even analyze
            if regime['regime'] == 'BEAR':
                return {
                    'action': 'WAIT',
                    'confidence': 0,
                    'reason': '🔴 BEAR MARKET - No new positions',
                    'market_regime': regime['regime'],
                    'lesson': 'O\'Neil: 3 out of 4 stocks follow the market. Don\'t fight the tape.'
                }
            
            # Use provided df or download
            if df is None:
                df = market_data.safe_yf_download(ticker, period="2y", interval="1d", auto_adjust=False)
            if df is None or df.empty or len(df) < 50:
                return {'action': 'ERROR', 'reason': 'Insufficient data'}
            
            if isinstance(df.columns, pd.MultiIndex):
                try:
                    if ticker in df.columns.get_level_values(1):
                        df = df.xs(ticker, axis=1, level=1)
                    elif ticker in df.columns.get_level_values(0):
                        df = df.xs(ticker, axis=1, level=0)
                    else:
                        df.columns = df.columns.get_level_values(0)
                except Exception:
                    df.columns = df.columns.get_level_values(0)
                # Deduplicate columns if any remain
                df = df.loc[:, ~df.columns.duplicated()]
            
            current_price = float(df['Close'].iloc[-1])
            
            # === REQUIRED FILTERS (ALL MUST PASS) ===
            filters_passed = []
            filters_failed = []
            
            # Filter 1: Weinstein Stage 2 (Uptrend)
            stage_data = indicators.calculate_weinstein_stage(df, current_price)
            if stage_data['stage'] == 2:
                filters_passed.append(f"✓ Weinstein Stage 2 (Uptrend confirmed)")
            else:
                filters_failed.append(f"✗ Not in Stage 2 uptrend (Current: Stage {stage_data['stage']})")
            
            # Filter 2: Price above key EMAs
            ema_50 = float(df['Close'].ewm(span=50).mean().iloc[-1])
            ema_200 = float(df['Close'].ewm(span=200).mean().iloc[-1]) if len(df) >= 200 else ema_50 * 0.95
            
            if current_price > ema_50 and current_price > ema_200:
                filters_passed.append(f"✓ Price above 50 EMA (${ema_50:.2f}) and 200 EMA (${ema_200:.2f})")
            else:
                filters_failed.append(f"✗ Price not above both 50/200 EMAs")
            
            # Filter 3: CAN SLIM Score
            canslim = can_slim.calculate_can_slim_score(ticker, regime['regime'])
            if canslim and canslim['total_score'] >= 70:
                filters_passed.append(f"✓ CAN SLIM Score: {canslim['total_score']} (Grade {canslim['grade']})")
            else:
                score = canslim['total_score'] if canslim else 0
                filters_failed.append(f"✗ CAN SLIM Score too low: {score} (Need 70+)")
            
            # Filter 4: Relative Strength (L factor)
            if canslim and canslim['factor_scores']['L'] >= 70:
                filters_passed.append(f"✓ Market Leader - RS Rating {canslim['factor_scores']['L']:.0f}")
            else:
                rs = canslim['factor_scores']['L'] if canslim else 0
                filters_failed.append(f"✗ Relative Strength weak: {rs:.0f} (Need 70+)")
            
            # === COMPUTE TECHNICAL DATA (always, for ALL responses) ===
            ema50_distance_pct = ((current_price - ema_50) / ema_50) * 100
            ema200_distance_pct = ((current_price - ema_200) / ema_200) * 100
            
            # RSI
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs_val = gain / loss
            rsi = 100 - (100 / (1 + rs_val))
            current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
            
            # Volume
            vol_avg_50 = float(df['Volume'].tail(50).mean())
            vol_today = float(df['Volume'].iloc[-1])
            vol_ratio = vol_today / vol_avg_50 if vol_avg_50 > 0 else 0
            
            # 52-Week High
            high_52w = float(df['High'].tail(252).max()) if len(df) >= 252 else float(df['High'].max())
            low_52w = float(df['Low'].tail(252).min()) if len(df) >= 252 else float(df['Low'].min())
            distance_from_high = ((high_52w - current_price) / high_52w) * 100
            
            # ATR
            sma_20 = float(df['Close'].tail(20).mean())
            atr_14 = float((df['High'] - df['Low']).tail(14).mean())
            
            # Pattern detection (run for all stocks)
            vcp = screener.scan_vcp_pattern(df, ticker)
            bull_flag = screener.scan_bull_flag(df, ticker)
            asc_tri = screener.scan_ascending_triangle(df, ticker)
            base_bo = screener.scan_base_breakout(df, ticker)
            
            patterns_detected = []
            if vcp: patterns_detected.append({'name': 'VCP', 'details': _sanitize_for_json(vcp)})
            if bull_flag: patterns_detected.append({'name': 'Bull Flag', 'details': _sanitize_for_json(bull_flag)})
            if asc_tri: patterns_detected.append({'name': 'Ascending Triangle', 'details': _sanitize_for_json(asc_tri)})
            if base_bo: patterns_detected.append({'name': 'Base Breakout', 'details': _sanitize_for_json(base_bo)})
            
            # === PRICE PROJECTION (ATR range + EMA trend) ===
            import math
            projection = {}
            try:
                # EMA slope: daily change over last 20 days
                ema50_20d_ago = float(df['Close'].ewm(span=50).mean().iloc[-20])
                ema_slope_daily = (ema_50 - ema50_20d_ago) / 20
                
                atr_sqrt_22 = atr_14 * math.sqrt(22)   # 1-month vol envelope
                atr_sqrt_66 = atr_14 * math.sqrt(66)   # 3-month vol envelope
                
                # Trend projection: extend EMA slope
                trend_1m = current_price + (ema_slope_daily * 22)
                trend_3m = current_price + (ema_slope_daily * 66)
                
                # Combine: trend as target, ATR as range
                proj_1m_low = round(max(current_price - atr_sqrt_22, low_52w * 0.95), 2)
                proj_1m_target = round(trend_1m, 2)
                proj_1m_high = round(current_price + atr_sqrt_22, 2)
                
                proj_3m_low = round(max(current_price - atr_sqrt_66, low_52w * 0.90), 2)
                proj_3m_target = round(trend_3m, 2)
                proj_3m_high = round(min(current_price + atr_sqrt_66, high_52w * 1.30), 2)
                
                # Trend bias
                if ema_slope_daily > 0.1:
                    trend_bias = 'bullish'
                elif ema_slope_daily < -0.1:
                    trend_bias = 'bearish'
                else:
                    trend_bias = 'neutral'
                
                projected_move = round(((proj_1m_target - current_price) / current_price) * 100, 1)
                
                projection = {
                    '1_month': {'low': proj_1m_low, 'target': proj_1m_target, 'high': proj_1m_high},
                    '3_month': {'low': proj_3m_low, 'target': proj_3m_target, 'high': proj_3m_high},
                    'trend_bias': trend_bias,
                    'projected_move_pct': projected_move,
                    'support': round(float(df['Low'].tail(20).min()), 2),
                    'resistance': round(high_52w, 2),
                }
            except Exception:
                projection = {}
            
            # === FUNDAMENTAL DATA ===
            fundamentals = {}
            earnings_history = []
            try:
                import yfinance as yf
                stock = yf.Ticker(ticker)
                info = stock.info
                
                def _safe_pct(v):
                    if v is None: return None
                    return round(v * 100, 1)
                
                def _fmt_big(v):
                    if v is None: return 'N/A'
                    if v >= 1e12: return f'{v/1e12:.1f}T'
                    if v >= 1e9: return f'{v/1e9:.1f}B'
                    if v >= 1e6: return f'{v/1e6:.0f}M'
                    return str(v)
                
                fundamentals = {
                    'eps_trailing': round(info.get('trailingEps', 0) or 0, 2),
                    'eps_forward': round(info.get('forwardEps', 0) or 0, 2),
                    'eps_growth_qoq': _safe_pct(info.get('earningsQuarterlyGrowth')),
                    'revenue_growth': _safe_pct(info.get('revenueGrowth')),
                    'profit_margin': _safe_pct(info.get('profitMargins')),
                    'roe': _safe_pct(info.get('returnOnEquity')),
                    'forward_pe': round(info.get('forwardPE', 0) or 0, 1),
                    'trailing_pe': round(info.get('trailingPE', 0) or 0, 1),
                    'peg_ratio': round(info.get('pegRatio', 0) or 0, 2),
                    'institutional_pct': _safe_pct(info.get('heldPercentInstitutions')),
                    'float_shares': _fmt_big(info.get('floatShares')),
                    'market_cap': _fmt_big(info.get('marketCap')),
                    'sector': info.get('sector', 'N/A'),
                    'industry': info.get('industry', 'N/A'),
                    'beta': round(info.get('beta', 0) or 0, 2),
                }
                
                # === EARNINGS HISTORY (last 3 reported quarters) ===
                try:
                    ed = stock.earnings_dates
                    if ed is not None and not ed.empty:
                        # Filter only reported (have Reported EPS)
                        reported = ed.dropna(subset=['Reported EPS']).head(4)
                        beats = 0
                        for idx, row in reported.iterrows():
                            eps_est = row.get('EPS Estimate')
                            eps_act = row.get('Reported EPS')
                            surprise = row.get('Surprise(%)')
                            
                            if pd.notna(eps_act):
                                beat = bool(eps_act >= eps_est) if pd.notna(eps_est) else None
                                if beat:
                                    beats += 1
                                earnings_history.append({
                                    'date': idx.strftime('%b %Y') if hasattr(idx, 'strftime') else str(idx)[:7],
                                    'eps_estimate': round(float(eps_est), 2) if pd.notna(eps_est) else None,
                                    'eps_actual': round(float(eps_act), 2),
                                    'surprise_pct': round(float(surprise), 1) if pd.notna(surprise) else None,
                                    'beat': beat,
                                })
                        
                        fundamentals['earnings_streak'] = beats
                        fundamentals['earnings_verdict'] = (
                            '🔥 Aceleración perfecta' if beats >= 4 else
                            '✅ Sólido' if beats >= 3 else
                            '⚠️ Inconsistente' if beats >= 2 else
                            '❌ Débil'
                        )
                except Exception:
                    pass
                    
            except Exception:
                pass
            
            # Build technicals dict (attached to ALL responses)
            technicals = {
                'price': round(current_price, 2),
                'ema_50': round(ema_50, 2),
                'ema_200': round(ema_200, 2),
                'ema50_distance_pct': round(ema50_distance_pct, 1),
                'ema200_distance_pct': round(ema200_distance_pct, 1),
                'above_50_ema': bool(current_price > ema_50),
                'above_200_ema': bool(current_price > ema_200),
                'ema_stacking': bool(ema_50 > ema_200),  # Bullish alignment
                'weinstein_stage': stage_data['stage'],
                'rsi': round(current_rsi, 1),
                'volume_ratio': round(vol_ratio, 2),
                'volume_avg_50d': int(vol_avg_50),
                'high_52w': round(high_52w, 2),
                'low_52w': round(low_52w, 2),
                'distance_from_52w_high': round(distance_from_high, 1),
                'atr_14': round(atr_14, 2),
                'canslim_score': canslim['total_score'] if canslim else 0,
                'canslim_grade': canslim['grade'] if canslim else 'N/A',
                'canslim_factors': canslim['factor_scores'] if canslim else {},
                'rs_rating': round(canslim['factor_scores']['L'], 0) if canslim else 0,
                'patterns': [p['name'] for p in patterns_detected],
                'patterns_details': patterns_detected,
                'projection': projection,
                'fundamentals': fundamentals,
                'earnings_history': earnings_history,
            }
            
            # If core filters failed, return WAIT with full technicals
            if filters_failed:
                return {
                    'action': 'WAIT',
                    'confidence': 30,
                    'ticker': ticker,
                    'price': current_price,
                    'reason': 'Does not meet minimum entry criteria',
                    'filters_failed': filters_failed,
                    'filters_passed': filters_passed,
                    'technicals': technicals,
                    'lesson': 'Minervini: Only trade A+ setups. Patience is key to outperformance.'
                }
            
            # === OVEREXTENSION FILTERS (Reject stocks too far from base) ===
            extension_warnings = []
            
            if ema50_distance_pct > 40:
                extension_warnings.append(f"Extended {ema50_distance_pct:.0f}% above 50 EMA — ideal entries within 15%")
            if ema200_distance_pct > 100:
                extension_warnings.append(f"Parabolic: {ema200_distance_pct:.0f}% above 200 EMA — high pullback risk")
            if atr_14 > 0:
                atrs_above = (current_price - sma_20) / atr_14
                if atrs_above > 5:
                    extension_warnings.append(f"Price {atrs_above:.1f} ATRs above 20-day SMA — abnormally stretched")
            if len(df) >= 15:
                price_15d_ago = float(df['Close'].iloc[-15])
                gain_3w = ((current_price - price_15d_ago) / price_15d_ago) * 100
                if gain_3w > 40:
                    extension_warnings.append(f"Climax run: +{gain_3w:.0f}% in 3 weeks — exhaustion likely")
            if current_rsi > 85:
                extension_warnings.append(f"RSI at {current_rsi:.0f} (severely overbought) — wait for cooldown")
            
            # Need 2+ warnings to call it EXTENDED (one alone is still tradeable)
            if len(extension_warnings) >= 2:
                return {
                    'action': 'EXTENDED',
                    'confidence': int(canslim['total_score']) if canslim else 50,
                    'ticker': ticker,
                    'current_price': round(current_price, 2),
                    'ema50_distance': round(ema50_distance_pct, 1),
                    'rsi': round(current_rsi, 1),
                    'filters_passed': filters_passed,
                    'extension_warnings': extension_warnings,
                    'reason': extension_warnings[0],
                    'pullback_target': round(ema_50 * 1.05, 2),
                    'technicals': technicals,
                    'lesson': "Minervini: The time to buy is when a stock pulls back to its 50-day MA after an advance — not when it's extended far above it."
                }
            
            # === ENTRY TRIGGERS (At least ONE must be present) ===
            triggers = []
            trigger_scores = []
            
            # Trigger 1: VCP Pattern
            if vcp:
                triggers.append({'type': 'VCP Breakout', 'description': 'Minervini VCP detected - Volatility contracting, ready to breakout', 'score': 90})
                trigger_scores.append(90)
            
            # Trigger 2: Weekly RSI Bullish Cross
            rsi_data = indicators.calculate_weekly_rsi_analytics(df)
            if rsi_data and rsi_data.get('signal_buy'):
                triggers.append({'type': 'Weekly RSI Cross', 'description': 'RSI bullish cross - Early momentum signal', 'score': 80})
                trigger_scores.append(80)
            
            # Trigger 3: Near 52-Week High
            if distance_from_high < 15:
                triggers.append({'type': 'Near 52-Week High', 'description': f"Within {distance_from_high:.1f}% of 52-week high (O'Neil new high principle)", 'score': 75})
                trigger_scores.append(75)
            
            # Trigger 4: Volume Surge
            if vol_ratio > 1.5:
                triggers.append({'type': 'Volume Breakout', 'description': f'Volume {vol_ratio:.1f}x above average - Institutional interest', 'score': 70})
                trigger_scores.append(70)
            
            # Trigger 5: Bull Flag
            if bull_flag:
                triggers.append({'type': 'Bull Flag', 'description': f"Bull Flag: +{bull_flag['pole_gain_pct']}% pole, {bull_flag['flag_days']}d flag ({bull_flag['retracement_pct']:.0f}% pullback)", 'score': 88})
                trigger_scores.append(88)
            
            # Trigger 6: Ascending Triangle
            if asc_tri:
                triggers.append({'type': 'Ascending Triangle', 'description': f"Ascending Triangle: {asc_tri['touches']} resistance touches, price at {asc_tri['squeeze_pct']:.0f}% of range", 'score': 85})
                trigger_scores.append(85)
            
            # Trigger 7: Base Breakout (AGI-style)
            if base_bo:
                triggers.append({'type': 'Base Breakout', 'description': f"Base Breakout: +{base_bo['impulse_gain_pct']}% impulse → {base_bo['base_weeks']}w base ({base_bo['base_depth_pct']:.0f}% depth), price at {base_bo['position_in_base']:.0f}% of range", 'score': 92})
                trigger_scores.append(92)
            
            # If no triggers, it's a WATCH — calculate entry targets
            if not triggers:
                recent_high = float(df['High'].tail(20).max())
                pivot_price = round(recent_high * 1.01, 2)
                recent_low = float(df['Low'].tail(20).min())
                watch_stop = round(recent_low * 0.98, 2)
                risk_per_share = pivot_price - watch_stop
                reward_per_share = pivot_price * 0.20
                rr_ratio = round(reward_per_share / risk_per_share, 1) if risk_per_share > 0 else 0
                
                missing = []
                if not vcp: missing.append('VCP contraction')
                if vol_ratio <= 1.5: missing.append(f'volume surge (currently {vol_ratio:.1f}x, need >1.5x)')
                if distance_from_high >= 15: missing.append(f'closer to 52w high ({distance_from_high:.0f}% away)')
                
                return {
                    'action': 'WATCH',
                    'confidence': 40,
                    'ticker': ticker,
                    'price': current_price,
                    'reason': 'Passes filters but no entry trigger yet',
                    'filters_passed': filters_passed,
                    'entry_target': pivot_price,
                    'stop_loss': watch_stop,
                    'risk_reward': rr_ratio,
                    'distance_to_pivot': round(((pivot_price - current_price) / current_price) * 100, 1),
                    'waiting_for': missing[:2],
                    'technicals': technicals,
                    'next_steps': f'Set alert at ${pivot_price:.2f}. Buy on breakout with volume >1.5x avg.',
                    'lesson': 'David Ryan: The best traders wait for the perfect setup, not just a good one.'
                }
            
            # === CALCULATE ENTRY PLAN ===
            
            # Determine ideal entry price
            if vcp:
                entry_price = current_price * 1.01  # 1% above current for breakout
            else:
                entry_price = current_price  # Market order
            
            # Calculate stop loss (ATR-based or 7-8% rule)
            atr_stop = risk_manager.calculate_atr_stop(df, atr_multiplier=2.0)
            pct_stop = current_price * 0.92  # 8% stop
            stop_loss = max(atr_stop, pct_stop)  # Use wider stop (more conservative)
            
            # Position sizing
            position_data = risk_manager.calculate_position_size(
                account_value=self.account_value,
                entry_price=entry_price,
                stop_loss=stop_loss,
                risk_per_trade=0.02,  # 2% risk
                max_position_pct=0.10  # Max 10% position
            )
            
            # Adjust for market regime
            regime_multiplier = regime['position_size_multiplier']
            adjusted_shares = int(position_data['shares'] * regime_multiplier)
            adjusted_position_value = adjusted_shares * entry_price
            
            # Calculate targets (Minervini multi-target method)
            target1 = entry_price * 1.20  # +20%
            target2 = entry_price * 1.40  # +40%
            target3 = entry_price * 1.60  # +60%
            
            # Calculate confidence score
            base_confidence = canslim['total_score'] if canslim else 50
            trigger_boost = max(trigger_scores) / 100 * 20  # Up to +20 points
            regime_adjustment = regime_multiplier * 10  # Market regime impact
            
            final_confidence = min(100, base_confidence + trigger_boost + regime_adjustment)
            
            # === RETURN BUY RECOMMENDATION ===
            return {
                'action': 'BUY',
                'confidence': int(final_confidence),
                'ticker': ticker,
                'current_price': round(current_price, 2),
                'entry_price': round(entry_price, 2),
                'stop_loss': round(stop_loss, 2),
                'position_size': {
                    'shares': adjusted_shares,
                    'value': round(adjusted_position_value, 2),
                    'percent_of_account': round((adjusted_position_value / self.account_value) * 100, 1),
                   'risk_dollars': round(position_data['total_risk'] * regime_multiplier, 2),
                    'risk_percent': round(position_data['risk_pct'] * regime_multiplier * 100, 2)
                },
                'targets': {
                    'target1': round(target1, 2),
                    'target2': round(target2, 2),
                    'target3': round(target3, 2)
                },
                'rationale': [
                    *filters_passed,
                    *[f"🎯 {t['type']}: {t['description']}" for t in triggers]
                ],
                'market_regime': {
                    'status': regime['regime'],
                    'adjustment': f"Position size {int(regime_multiplier*100)}% of normal due to {regime['regime']} market"
                },
                'risk_reward': round((target1 - entry_price) / (entry_price - stop_loss), 2),
                'technicals': technicals,
                'methodology': 'Combined CAN SLIM + VCP + Weinstein Stage Analysis',
                'lesson': self._generate_entry_lesson(triggers, canslim)
            }
            
        except Exception as e:
            return {
                'action': 'ERROR',
                'reason': f'Analysis failed: {str(e)}',
                'ticker': ticker
            }
    
    
    def analyze_hold_decision(self, ticker: str, entry_price: float, 
                             current_shares: int, stop_loss: float, 
                             peak_price: Optional[float] = None) -> Dict:
        """
        Analyze whether to continue holding a position.
        
        Returns HOLD/REDUCE/EXIT decision with updated stops and targets.
        """
        try:
            # Get current data
            df = market_data.safe_yf_download(ticker, period="1y", interval="1d", auto_adjust=False)
            if df is None or df.empty:
                return {'action': 'ERROR', 'reason': 'Cannot fetch current data'}
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            current_price = float(df['Close'].iloc[-1])
            
            # Update peak if not provided or if current is higher
            if peak_price is None or current_price > peak_price:
                peak_price = current_price
            
            # Get exit analysis
            exit_analysis = exit_manager.evaluate_exit_signals(
                ticker=ticker,
                entry_price=entry_price,
                current_price=current_price,
                stop_loss=stop_loss,
                peak_price=peak_price,
                df=df,
                position_shares=current_shares
            )
            
            # Calculate current P&L
            current_gain_pct = (current_price - entry_price) / entry_price
            current_pnl = (current_price - entry_price) * current_shares
            
            return {
                **exit_analysis,
                'ticker': ticker,
                'current_price': round(current_price, 2),
                'entry_price': entry_price,
                'peak_price': round(peak_price, 2),
                'current_gain_pct': round(current_gain_pct * 100, 2),
                'current_pnl': round(current_pnl, 2),
                'shares': current_shares,
                'methodology': 'Minervini trailing stops + O\'Neil distribution detection + Weinstein stage analysis'
            }
            
        except Exception as e:
            return {
                'action': 'ERROR',
                'reason': f'Hold analysis failed: {str(e)}',
                'ticker': ticker
            }
    
    
    def _get_market_regime(self) -> Dict:
        """Get current market regime (cached for performance)"""
        import time
        
        # Cache for 15 minutes
        if (self.market_regime_cache is None or 
            self.last_regime_update is None or 
            time.time() - self.last_regime_update > 900):
            
            self.market_regime_cache = market_regime.get_market_regime()
            self.last_regime_update = time.time()
        
        return self.market_regime_cache
    
    
    def _generate_entry_lesson(self, triggers: List[Dict], canslim: Dict) -> str:
        """Generate educational lesson for entry"""
        
        if any(t['type'] == 'VCP Breakout' for t in triggers):
            return ("Minervini VCP: The best setups have 3-4 contracting volatility pivots before breakout. "
                   "This shows supply drying up as weak hands get shaken out.")
        
        if canslim and canslim['factor_scores']['L'] >= 85:
            return ("O'Neil: Focus on market leaders (RS >85). These are the stocks that will give you "
                   "outsized gains. Laggards rarely become leaders.")
        
        return ("Professional traders combine multiple signals. No single indicator is enough. "
               "CAN SLIM + Stage 2 + Entry trigger = High probability setup.")


# === API Functions for main.py ===

# Global mentor instance
_mentor = MomentumMentor(account_value=100000)


def get_entry_analysis(ticker: str, account_value: Optional[float] = None, df=None) -> Dict:
    """
    Get entry recommendation for a ticker.
    
    Args:
        ticker: Stock symbol
        account_value: Optional account size override
        df: Optional pre-downloaded DataFrame
        
    Returns:
        Dict with BUY/WAIT/WATCH decision and complete execution plan
    """
    if account_value:
        _mentor.account_value = account_value
    
    return _mentor.analyze_entry_opportunity(ticker, df=df)


def get_hold_analysis(ticker: str, entry_price: float, shares: int,
                      stop_loss: float, peak_price: Optional[float] = None) -> Dict:
    """
    Get hold/exit recommendation for existing position.
    
    Args:
        ticker: Stock symbol
        entry_price: Original entry price
        shares: Number of shares held
        stop_loss: Current stop loss
        peak_price: Highest price since entry (optional)
        
    Returns:
        Dict with HOLD/REDUCE/EXIT decision and updated stops
    """
    return _mentor.analyze_hold_decision(ticker, entry_price, shares, stop_loss, peak_price)


_hmm_cache = None
_last_hmm_update = None

def get_market_status() -> Dict:
    """Get current market regime, position sizing, and HMM latent state guidance"""
    import time
    
    # 1. Get the base rule-based regime
    base_regime = market_regime.get_market_regime()
    
    # 2. Add HMM Analysis (with 1-hour cache to avoid fitting on every request)
    global _hmm_cache, _last_hmm_update
    
    try:
        import market_regime_hmm
        
        # 3600 seconds = 1 hour cache
        if _hmm_cache is None or _last_hmm_update is None or (time.time() - _last_hmm_update > 3600):
            print("[HMM] Fitting new Market Regime Model...")
            # We use SPY as the proxy for the overall market regime
            _hmm_cache = market_regime_hmm.analyze_regime("SPY", n_regimes=4, vol_window=5)
            _last_hmm_update = time.time()
            
        base_regime['hmm_analysis'] = _hmm_cache
    except Exception as e:
        print(f"[HMM Error] Failed to get HMM regime: {e}")
        base_regime['hmm_analysis'] = None
        
    return base_regime
