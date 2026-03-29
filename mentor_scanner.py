import json
import os
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd

# Local imports
import screener
import market_data
import cache
import momentum_mentor

# Config
SCAN_CACHE_DIR = "scan_reports"
SCAN_CACHE_FILE = "mentor_scan_latest.json"
CACHE_TTL_HOURS = 4  # Re-use scan results for 4 hours

# Ensure directory exists
os.makedirs(SCAN_CACHE_DIR, exist_ok=True)

# Global scan status
SCAN_STATUS = {
    "is_running": False,
    "total": 0,
    "current": 0,
    "buy_count": 0,
    "watch_count": 0,
    "last_ticker": "",
    "start_time": None,
    "estimated_time_remaining": 0,
    "scan_thread": None
}


def get_scan_status():
    """Get current scan progress"""
    return {
        "is_running": SCAN_STATUS["is_running"],
        "total": SCAN_STATUS["total"],
        "current": SCAN_STATUS["current"],
        "buy_count": SCAN_STATUS["buy_count"],
        "watch_count": SCAN_STATUS["watch_count"],
        "last_ticker": SCAN_STATUS["last_ticker"],
        "progress_pct": round((SCAN_STATUS["current"] / SCAN_STATUS["total"] * 100) if SCAN_STATUS["total"] > 0 else 0, 1),
        "estimated_time_remaining": SCAN_STATUS["estimated_time_remaining"]
    }


def load_cached_results() -> Optional[Dict]:
    """
    Load cached scan results if they exist and are fresh.
    
    Returns:
        Dict with scan results or None if cache is stale/missing
    """
    cache_path = os.path.join(SCAN_CACHE_DIR, SCAN_CACHE_FILE)
    
    if not os.path.exists(cache_path):
        return None
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if cache is fresh
        scan_time = datetime.fromisoformat(data.get('timestamp', '2000-01-01'))
        age_hours = (datetime.now() - scan_time).total_seconds() / 3600
        
        if age_hours < CACHE_TTL_HOURS:
            print(f"[MENTOR SCANNER] Using cached results ({age_hours:.1f}h old)")
            return data
        else:
            print(f"[MENTOR SCANNER] Cache stale ({age_hours:.1f}h old), will rescan")
            return None
            
    except Exception as e:
        print(f"[MENTOR SCANNER] Error loading cache: {e}")
        return None


def save_scan_results(results: Dict):
    """Save scan results to JSON cache"""
    cache_path = os.path.join(SCAN_CACHE_DIR, SCAN_CACHE_FILE)
    
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"[MENTOR SCANNER] Results cached: {cache_path}")
    except Exception as e:
        print(f"[MENTOR SCANNER] Error saving cache: {e}")


def _run_scan_background():
    """Background scanning function - runs in separate thread.
    Uses same universe and cache strategy as W.RSI scanner."""
    print(f"\n{'='*60}")
    print(f"[MENTOR SCANNER] Starting background scan at {datetime.now().isoformat()}")
    print(f"{'='*60}\n")
    
    # Initialize scan status
    SCAN_STATUS["is_running"] = True
    SCAN_STATUS["start_time"] = time.time()
    SCAN_STATUS["current"] = 0
    SCAN_STATUS["buy_count"] = 0
    SCAN_STATUS["watch_count"] = 0
    
    try:
        # Get FULL ticker list - same as W.RSI scanner
        tickers = screener.get_sec_tickers()
        if not tickers:
            print("[MENTOR SCANNER] ERROR: No tickers found")
            SCAN_STATUS["is_running"] = False
            SCAN_STATUS["scan_thread"] = None
            return
        
        SCAN_STATUS["total"] = len(tickers)
        print(f"[MENTOR SCANNER] Scanning {len(tickers)} SEC tickers (full universe)...")
        
        buy_opportunities = []
        watch_opportunities = []
        extended_opportunities = []
        errors = []
        
        # Track timing for ETA
        start_time = time.time()
        processed_count = 0
        
        # PHASE 1: Use shared cache (same as scan_engine)
        c = cache.get_cache()
        period = screener.PERIOD  # 1y 
        cached_data, to_download = c.batch_check(tickers, period, "1d", max_age_hours=4)
        
        print(f"[MENTOR SCANNER] Cache: {len(cached_data)} cached, {len(to_download)} need download")
        SCAN_STATUS["last_ticker"] = f"Cache: {len(cached_data)} cached, {len(to_download)} to download"
        
        # PHASE 2: Process cached tickers (fast!)
        if cached_data:
            print(f"[MENTOR SCANNER] Processing {len(cached_data)} cached tickers...")
            for ticker, df in cached_data.items():
                SCAN_STATUS["current"] += 1
                SCAN_STATUS["last_ticker"] = f"[CACHE] {ticker}"
                processed_count += 1
                
                try:
                    _analyze_ticker(ticker, df, buy_opportunities, watch_opportunities, extended_opportunities)
                except Exception as e:
                    errors.append({'ticker': ticker, 'error': str(e)})
                
                # Update ETA every 20 tickers
                if processed_count % 20 == 0:
                    elapsed = time.time() - start_time
                    avg = elapsed / processed_count
                    remaining = len(tickers) - processed_count
                    SCAN_STATUS["estimated_time_remaining"] = int(avg * remaining)
        
        # PHASE 3: Download missing tickers in batches (same as scan_engine)
        if to_download:
            batch_size = 25
            total_batches = (len(to_download) + batch_size - 1) // batch_size
            
            for i in range(0, len(to_download), batch_size):
                batch = to_download[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                
                print(f"[MENTOR SCANNER] Downloading batch {batch_num}/{total_batches} ({len(batch)} tickers)...")
                SCAN_STATUS["last_ticker"] = f"Batch {batch_num}/{total_batches}: {', '.join(batch[:3])}..."
                
                try:
                    batch_df = market_data.safe_yf_download(batch, period=period, auto_adjust=False, threads=True)
                    
                    if batch_df is not None and not batch_df.empty:
                        for ticker in batch:
                            SCAN_STATUS["current"] += 1
                            SCAN_STATUS["last_ticker"] = f"[NET] {ticker}"
                            processed_count += 1
                            
                            try:
                                # Extract single ticker data from batch
                                if isinstance(batch_df.columns, pd.MultiIndex):
                                    if ticker in batch_df.columns.get_level_values(1):
                                        df = batch_df.xs(ticker, axis=1, level=1)
                                    else:
                                        continue
                                else:
                                    df = batch_df
                                
                                if df.empty or len(df) < 50:
                                    continue
                                
                                # Cache available for future use (data already in memory)
                                pass
                                
                                _analyze_ticker(ticker, df, buy_opportunities, watch_opportunities, extended_opportunities)
                            except Exception as e:
                                errors.append({'ticker': ticker, 'error': str(e)})
                    else:
                        # Count skipped tickers
                        SCAN_STATUS["current"] += len(batch)
                        processed_count += len(batch)
                        
                except Exception as e:
                    print(f"[MENTOR SCANNER] Batch error: {e}")
                    SCAN_STATUS["current"] += len(batch)
                    processed_count += len(batch)
                
                # Update ETA
                if processed_count > 0:
                    elapsed = time.time() - start_time
                    avg = elapsed / processed_count
                    remaining = len(tickers) - processed_count
                    SCAN_STATUS["estimated_time_remaining"] = int(avg * remaining)
                
                # Small delay between batches
                if i + batch_size < len(to_download):
                    time.sleep(1)
        
        # Sort results
        buy_opportunities.sort(key=lambda x: x['confidence'], reverse=True)
        watch_opportunities.sort(key=lambda x: x['confidence'], reverse=True)
        extended_opportunities.sort(key=lambda x: x['confidence'], reverse=True)
        
        elapsed = time.time() - start_time
        
        # Prepare results
        results = {
            'timestamp': datetime.now().isoformat(),
            'scan_time': round(elapsed, 2),
            'total_scanned': len(tickers),
            'buy_signals': len(buy_opportunities),
            'watch_signals': len(watch_opportunities),
            'extended_signals': len(extended_opportunities),
            'buy_opportunities': buy_opportunities,
            'watch_opportunities': watch_opportunities[:50],
            'extended_opportunities': extended_opportunities[:50],
            'errors_count': len(errors),
            'errors_sample': errors[:10],
            'cache_valid_until': (datetime.now() + timedelta(hours=CACHE_TTL_HOURS)).isoformat()
        }
        
        # Save to cache
        save_scan_results(results)
        
        print(f"\n[MENTOR SCANNER] ✅ Background scan complete!")
        print(f"[MENTOR SCANNER] Scanned {len(tickers)} tickers in {elapsed:.1f}s")
        print(f"[MENTOR SCANNER] Found {len(buy_opportunities)} BUY, {len(extended_opportunities)} EXTENDED, {len(watch_opportunities)} WATCH")
    
    except Exception as e:
        print(f"[MENTOR SCANNER] ❌ Scan error: {e}")
    finally:
        SCAN_STATUS["is_running"] = False
        SCAN_STATUS["scan_thread"] = None


def _analyze_ticker(ticker: str, df, buy_opportunities: list, watch_opportunities: list, extended_opportunities: list = None):
    """Analyze a single ticker using Momentum Mentor logic with pre-downloaded data."""
    if df is None or df.empty or len(df) < 50:
        return
    if extended_opportunities is None:
        extended_opportunities = []
    
    try:
        analysis = momentum_mentor.get_entry_analysis(ticker, df=df)
        
        if not analysis:
            return
        
        action = analysis.get('action')
        
        if action == 'BUY':
            SCAN_STATUS["buy_count"] += 1
            buy_opportunities.append({
                'ticker': ticker,
                'confidence': analysis.get('confidence', 0),
                'price': analysis.get('current_price'),
                'entry': analysis.get('entry_price'),
                'stop': analysis.get('stop_loss'),
                'target1': analysis.get('targets', {}).get('target1'),
                'target2': analysis.get('targets', {}).get('target2'),
                'target3': analysis.get('targets', {}).get('target3'),
                'position_size': analysis.get('position_size', {}),
                'rationale': analysis.get('rationale', [])[:3],
                'market_regime': analysis.get('market_regime', {}).get('status'),
                'risk_reward': analysis.get('risk_reward'),
                'lesson': analysis.get('lesson', '')
            })
        
        elif action == 'EXTENDED':
            extended_opportunities.append({
                'ticker': ticker,
                'confidence': analysis.get('confidence', 0),
                'price': analysis.get('current_price'),
                'ema50_distance': analysis.get('ema50_distance', 0),
                'rsi': analysis.get('rsi', 0),
                'pullback_target': analysis.get('pullback_target'),
                'warnings': analysis.get('extension_warnings', []),
                'reason': analysis.get('reason', 'Overextended'),
                'filters_passed': analysis.get('filters_passed', [])
            })
        
        elif action == 'WATCH':
            SCAN_STATUS["watch_count"] += 1
            watch_opportunities.append({
                'ticker': ticker,
                'confidence': analysis.get('confidence', 0),
                'price': analysis.get('price', analysis.get('current_price')),
                'reason': analysis.get('reason', 'Passes filters, waiting for trigger'),
                'entry_target': analysis.get('entry_target'),
                'stop_loss': analysis.get('stop_loss'),
                'risk_reward': analysis.get('risk_reward'),
                'distance_to_pivot': analysis.get('distance_to_pivot'),
                'waiting_for': analysis.get('waiting_for', []),
                'next_steps': analysis.get('next_steps', '')
            })
    except Exception as e:
        print(f"[MENTOR SCANNER] Error analyzing {ticker}: {e}")


def start_background_scan():
    """Start a background scan thread if not already running"""
    if SCAN_STATUS["is_running"]:
        print("[MENTOR SCANNER] Scan already in progress, skipping")
        return False
    
    # Start background thread
    thread = threading.Thread(target=_run_scan_background, daemon=True)
    thread.start()
    SCAN_STATUS["scan_thread"] = thread
    print("[MENTOR SCANNER] Background scan started")
    return True


def get_cached_or_scan(force_refresh: bool = False, limit: int = 20) -> Dict:
    """
    Main entry point: Get scan results (cached or trigger background scan).
    
    This is NON-BLOCKING - it immediately returns cached data or starts a background scan.
    
    Args:
        force_refresh: Force new scan even if cache exists
        limit: Max results to return
        
    Returns:
        Dict with scan results or scanning status
    """
    # Check cache first (unless force refresh)
    if not force_refresh:
        cached = load_cached_results()
        if cached:
            # Return cached data with limit applied
            return {
                **cached,
                'buy_opportunities': cached['buy_opportunities'][:limit],
                'watch_opportunities': cached['watch_opportunities'][:min(10, len(cached['watch_opportunities']))]
            }
    else:
        # Force refresh: DELETE old cache so polls don't return stale data
        cache_path = os.path.join(SCAN_CACHE_DIR, SCAN_CACHE_FILE)
        if os.path.exists(cache_path):
            os.remove(cache_path)
            print("[MENTOR SCANNER] Old cache deleted for force refresh")
    
    # No cache or force refresh - check if scan is running
    if SCAN_STATUS["is_running"]:
        # Scan already in progress, return status
        return {
            'scanning': True,
            'status': get_scan_status(),
            'message': 'Scan in progress. Results will be available when complete.',
            'buy_signals': 0,
            'watch_signals': 0,
            'buy_opportunities': [],
            'watch_opportunities': [],
            'total_scanned': 0,
            'scan_time': 0
        }
    
    # Start a new background scan
    start_background_scan()
    
    # Return immediate response that scan is starting
    return {
        'scanning': True,
        'status': get_scan_status(),
        'message': 'Scan started. Check back in ~60 seconds.',
        'buy_signals': 0,
        'watch_signals': 0,
        'buy_opportunities': [],
        'watch_opportunities': [],
        'total_scanned': 0,
        'scan_time': 0
    }
