"""
Market Analysis Cache
Stores Gemini-generated market analysis to reduce API calls.
Analysis is generated 3x daily: Pre-Market, Mid-Market, After-Market.
"""

from datetime import datetime
from threading import Lock
import pytz

# Thread-safe cache
_cache_lock = Lock()
_analysis_cache = {
    "PRE_MARKET": None,
    "MID_MARKET": None,
    "AFTER_MARKET": None,
    "latest": None
}

# Session schedule (EST times)
SESSION_SCHEDULE = {
    "PRE_MARKET": {"hour": 8, "minute": 0, "name": "Pre-Market (8AM EST)"},
    "MID_MARKET": {"hour": 12, "minute": 30, "name": "Mid-Market (12:30PM EST)"},
    "AFTER_MARKET": {"hour": 16, "minute": 30, "name": "After-Market (4:30PM EST)"}
}

def set_cached_analysis(session_type: str, content: str, market_data: dict = None):
    """
    Store a new analysis in the cache.
    
    Args:
        session_type: One of PRE_MARKET, MID_MARKET, AFTER_MARKET
        content: The Gemini-generated analysis text
        market_data: Optional dict with market context used for generation
    """
    with _cache_lock:
        now = datetime.now(pytz.timezone("US/Eastern"))
        entry = {
            "content": content,
            "session": session_type,
            "session_name": SESSION_SCHEDULE.get(session_type, {}).get("name", session_type),
            "generated_at": now.isoformat(),
            "generated_at_est": now.strftime("%Y-%m-%d %H:%M EST"),
            "market_data": market_data
        }
        _analysis_cache[session_type] = entry
        _analysis_cache["latest"] = entry
        print(f"[Market Analysis Cache] Stored {session_type} analysis at {now.strftime('%H:%M EST')}")


def get_cached_analysis(session_type: str = None) -> dict:
    """
    Get cached analysis for a specific session or the latest.
    
    Args:
        session_type: Optional. If None, returns latest analysis.
        
    Returns:
        dict with content, session, generated_at, or None if not cached
    """
    with _cache_lock:
        if session_type:
            return _analysis_cache.get(session_type)
        return _analysis_cache.get("latest")


def get_all_cached() -> dict:
    """Get all cached analyses for debugging/display."""
    with _cache_lock:
        return {
            k: v for k, v in _analysis_cache.items() 
            if v is not None and k != "latest"
        }


def get_next_scheduled_session() -> dict:
    """
    Determine the next scheduled analysis session.
    
    Returns:
        dict with session_type, name, and scheduled_time
    """
    now = datetime.now(pytz.timezone("US/Eastern"))
    current_minutes = now.hour * 60 + now.minute
    
    for session_type, schedule in SESSION_SCHEDULE.items():
        scheduled_minutes = schedule["hour"] * 60 + schedule["minute"]
        if scheduled_minutes > current_minutes:
            return {
                "session_type": session_type,
                "name": schedule["name"],
                "scheduled_time": f"{schedule['hour']:02d}:{schedule['minute']:02d} EST"
            }
    
    # All sessions passed, next is PRE_MARKET tomorrow
    return {
        "session_type": "PRE_MARKET",
        "name": SESSION_SCHEDULE["PRE_MARKET"]["name"],
        "scheduled_time": "08:00 EST (tomorrow)"
    }


def is_cache_stale(max_age_hours: int = 8) -> bool:
    """
    Check if the latest cache is too old.
    
    Args:
        max_age_hours: Maximum age in hours before cache is considered stale
        
    Returns:
        True if cache is stale or empty
    """
    with _cache_lock:
        latest = _analysis_cache.get("latest")
        if not latest:
            return True
        
        try:
            generated = datetime.fromisoformat(latest["generated_at"])
            now = datetime.now(pytz.timezone("US/Eastern"))
            age = (now - generated).total_seconds() / 3600
            return age > max_age_hours
        except:
            return True
