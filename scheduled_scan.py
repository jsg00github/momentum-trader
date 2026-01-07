"""
Scheduled Scanner - Runs RSI scan at US after hours and saves JSON report.

Schedule: Daily at 6PM Argentina time (4PM EST = start of US after hours)
Output: scan_reports/scan_YYYYMMDD_HHMM.json
"""
import threading
import time
import json
import os
from datetime import datetime
import pytz

import scan_engine

# Config
SCAN_HOUR = 18  # 6pm Argentina time (4pm EST)
SCAN_MINUTE = 0
REPORTS_DIR = "scan_reports"

# Ensure reports directory exists
os.makedirs(REPORTS_DIR, exist_ok=True)

def run_scheduled_scan():
    """Execute scan and save JSON report."""
    print(f"\n{'='*60}")
    print(f"[SCHEDULED SCAN] Starting at {datetime.now().isoformat()}")
    print(f"{'='*60}\n")
    
    try:
        # Run the scan
        results = scan_engine.run_market_scan(limit=1000, strategy="weekly_rsi")
        
        if results and "results" in results:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"scan_{timestamp}.json"
            filepath = os.path.join(REPORTS_DIR, filename)
            
            # Prepare report
            report = {
                "scan_date": datetime.now().isoformat(),
                "strategy": "weekly_rsi",
                "tickers_scanned": results.get("scanned", 0),
                "results_found": len(results.get("results", [])),
                "spy_ret_3m": results.get("spy_ret_3m", 0),
                "top_picks": results.get("results", [])[:20],  # Top 20 for quick view
                "all_results": results.get("results", [])
            }
            
            # Save to JSON
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"\n[SCHEDULED SCAN] ✅ Complete!")
            print(f"[SCHEDULED SCAN] Found {len(results.get('results', []))} setups")
            print(f"[SCHEDULED SCAN] Report saved: {filepath}")
            
            return filepath
        else:
            print("[SCHEDULED SCAN] ❌ No results returned")
            return None
            
    except Exception as e:
        print(f"[SCHEDULED SCAN] ❌ Error: {e}")
        return None


def check_and_run():
    """Check if it's time to run the scan."""
    argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
    now = datetime.now(argentina_tz)
    
    if now.hour == SCAN_HOUR and now.minute == SCAN_MINUTE:
        run_scheduled_scan()


def start_scheduler():
    """Start background scheduler thread."""
    def scheduler_loop():
        print(f"[SCHEDULER] Started - Will run daily at {SCAN_HOUR}:{SCAN_MINUTE:02d} Argentina time")
        last_run_date = None
        
        while True:
            argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
            now = datetime.now(argentina_tz)
            today = now.date()
            
            # Run at scheduled time, but only once per day
            if now.hour == SCAN_HOUR and now.minute >= SCAN_MINUTE and last_run_date != today:
                # Only run on weekdays (Mon=0, Sun=6)
                if now.weekday() < 5:  # Monday to Friday
                    last_run_date = today
                    run_scheduled_scan()
                else:
                    print(f"[SCHEDULER] Weekend - skipping scan")
                    last_run_date = today
            
            # Sleep for 30 seconds before checking again
            time.sleep(30)
    
    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
    return thread


def get_latest_report():
    """Get the most recent scan report."""
    if not os.path.exists(REPORTS_DIR):
        return None
    
    files = [f for f in os.listdir(REPORTS_DIR) if f.startswith("scan_") and f.endswith(".json")]
    if not files:
        return None
    
    files.sort(reverse=True)
    latest = os.path.join(REPORTS_DIR, files[0])
    
    with open(latest, 'r', encoding='utf-8') as f:
        return json.load(f)


def list_reports():
    """List all available reports."""
    if not os.path.exists(REPORTS_DIR):
        return []
    
    files = [f for f in os.listdir(REPORTS_DIR) if f.startswith("scan_") and f.endswith(".json")]
    files.sort(reverse=True)
    return files
