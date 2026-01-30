import sqlite3
import pickle
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import yfinance as yf
from typing import Optional, List, Tuple

class DataCache:
    """Cache for yfinance data to speed up repeated scans"""
    
    def __init__(self, db_path: str = "data/cache.db"):
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self):
        """Create database and tables if they don't exist"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_cache (
                ticker TEXT NOT NULL,
                period TEXT NOT NULL,
                interval TEXT NOT NULL,
                date_cached TIMESTAMP NOT NULL,
                data BLOB NOT NULL,
                PRIMARY KEY (ticker, period, interval)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_date_cached 
            ON price_cache(date_cached)
        """)
        
        conn.commit()
        conn.close()
    
    def get(self, ticker: str, period: str, interval: str, max_age_hours: int = 24) -> Optional[pd.DataFrame]:
        """Get cached data if available and fresh"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        cursor.execute("""
            SELECT data, date_cached FROM price_cache 
            WHERE ticker = ? AND period = ? AND interval = ?
            AND date_cached > ?
        """, (ticker, period, interval, cutoff))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            try:
                df = pickle.loads(row[0])
                return df
            except Exception as e:
                print(f"Cache error for {ticker}: {e}")
                return None
        
        return None
    
    def set(self, ticker: str, period: str, interval: str, df: pd.DataFrame):
        """Cache data"""
        if df is None or df.empty:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        data_blob = pickle.dumps(df)
        now = datetime.now()
        
        cursor.execute("""
            INSERT OR REPLACE INTO price_cache 
            (ticker, period, interval, date_cached, data)
            VALUES (?, ?, ?, ?, ?)
        """, (ticker, period, interval, now, data_blob))
        
        conn.commit()
        conn.close()
    
    def batch_check(self, tickers: List[str], period: str, interval: str, 
                    max_age_hours: int = 24) -> Tuple[dict, List[str]]:
        """
        Check which tickers are cached and which need downloading
        
        Returns:
            (cached_data, to_download)
            cached_data: dict of {ticker: DataFrame}
            to_download: list of tickers that need downloading
        """
        cached = {}
        to_download = []
        
        for ticker in tickers:
            df = self.get(ticker, period, interval, max_age_hours)
            if df is not None:
                cached[ticker] = df
            else:
                to_download.append(ticker)
        
        return cached, to_download
    
    def clear_old(self, days: int = 7):
        """Remove cache entries older than N days"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = datetime.now() - timedelta(days=days)
        
        cursor.execute("""
            DELETE FROM price_cache WHERE date_cached < ?
        """, (cutoff,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted
    
    def stats(self):
        """Get cache statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM price_cache")
        total = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM price_cache 
            WHERE date_cached > datetime('now', '-24 hours')
        """)
        fresh = cursor.fetchone()[0]
        
        conn.close()
        
        return {"total_entries": total, "fresh_24h": fresh}


# Global instance
_cache = None

def get_cache() -> DataCache:
    """Get or create global cache instance"""
    global _cache
    if _cache is None:
        _cache = DataCache()
    return _cache
