"""
Unified Price Service with Caching
- Finnhub as primary source (fast, <500ms)
- yfinance as fallback (slower but reliable)
- In-memory cache with TTL to reduce API calls
- Thread-safe for multi-user/multi-tenant
"""

import os
import time
import threading
from typing import Dict, List, Optional
import finnhub

# Lazy import yfinance to avoid slowing startup
_yfinance = None
def get_yfinance():
    global _yfinance
    if _yfinance is None:
        import yfinance
        _yfinance = yfinance
    return _yfinance

# ============================================
# Configuration
# ============================================

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "cvmo1npr01ql90pv62e0cvmo1npr01ql90pv62eg")
CACHE_TTL_SECONDS = int(os.getenv("PRICE_CACHE_TTL", "300"))  # 5 minutes for better performance

# ============================================
# Cache Implementation
# ============================================

class PriceCache:
    """Thread-safe in-memory price cache with TTL."""
    
    def __init__(self, ttl: int = 60):
        self.ttl = ttl
        self._cache: Dict[str, dict] = {}
        self._lock = threading.Lock()
    
    def get(self, ticker: str) -> Optional[dict]:
        """Get cached price if not expired."""
        with self._lock:
            if ticker in self._cache:
                entry = self._cache[ticker]
                if time.time() - entry['timestamp'] < self.ttl:
                    return entry['data']
                else:
                    del self._cache[ticker]
        return None
    
    def set(self, ticker: str, data: dict):
        """Cache a price with current timestamp."""
        with self._lock:
            self._cache[ticker] = {
                'data': data,
                'timestamp': time.time()
            }
    
    def get_many(self, tickers: List[str]) -> Dict[str, dict]:
        """Get multiple cached prices, returns dict of hits."""
        result = {}
        for ticker in tickers:
            cached = self.get(ticker)
            if cached:
                result[ticker] = cached
        return result
    
    def clear(self):
        """Clear all cached data."""
        with self._lock:
            self._cache.clear()
    
    def stats(self) -> dict:
        """Return cache statistics."""
        with self._lock:
            return {
                'entries': len(self._cache),
                'ttl': self.ttl
            }

# Global cache instance (shared across all requests/users)
_price_cache = PriceCache(ttl=CACHE_TTL_SECONDS)

# ============================================
# Finnhub Client
# ============================================

_finnhub_client = None

def get_finnhub_client():
    global _finnhub_client
    if _finnhub_client is None:
        _finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)
    return _finnhub_client

# ============================================
# Price Fetching Functions
# ============================================

def get_price(ticker: str, use_cache: bool = True) -> dict:
    """
    Get current price for a single ticker.
    
    Returns:
        {
            'price': float,
            'change': float,
            'change_pct': float,
            'high': float,
            'low': float,
            'open': float,
            'prev_close': float,
            'source': 'finnhub' | 'yfinance' | 'cache',
            'timestamp': float
        }
    """
    ticker = ticker.upper().strip()
    
    # 1. Check cache
    if use_cache:
        cached = _price_cache.get(ticker)
        if cached:
            cached['source'] = 'cache'
            return cached
    
    # 2. Try Finnhub (primary)
    try:
        data = _fetch_finnhub(ticker)
        if data and data.get('price'):
            _price_cache.set(ticker, data)
            return data
    except Exception as e:
        print(f"[PriceService] Finnhub error for {ticker}: {e}")
    
    # 3. Fallback to yfinance
    try:
        data = _fetch_yfinance(ticker)
        if data and data.get('price'):
            _price_cache.set(ticker, data)
            return data
    except Exception as e:
        print(f"[PriceService] yfinance error for {ticker}: {e}")
    
    # 4. Return empty if all fails
    return {'price': None, 'source': 'error', 'ticker': ticker}


def get_prices(tickers: List[str], use_cache: bool = True) -> Dict[str, dict]:
    """
    Get prices for multiple tickers efficiently.
    Uses cache for hits, batches misses.
    
    Returns:
        {'AAPL': {...}, 'TSLA': {...}, ...}
    """
    tickers = [t.upper().strip() for t in tickers if t]
    result = {}
    
    # 1. Check cache for all
    if use_cache:
        cached = _price_cache.get_many(tickers)
        for ticker, data in cached.items():
            data['source'] = 'cache'
            result[ticker] = data
    
    # 2. Find missing tickers
    missing = [t for t in tickers if t not in result]
    
    if not missing:
        return result
    
    # 3. Fetch missing from Finnhub (one by one - no batch API in free tier)
    finnhub_failures = []
    for ticker in missing:
        try:
            data = _fetch_finnhub(ticker)
            if data and data.get('price'):
                _price_cache.set(ticker, data)
                result[ticker] = data
            else:
                finnhub_failures.append(ticker)
        except Exception as e:
            print(f"[PriceService] Finnhub error for {ticker}: {e}")
            finnhub_failures.append(ticker)
    
    # 4. Fallback to yfinance for failures (batch)
    if finnhub_failures:
        try:
            yf_data = _fetch_yfinance_batch(finnhub_failures)
            for ticker, data in yf_data.items():
                if data and data.get('price'):
                    _price_cache.set(ticker, data)
                    result[ticker] = data
        except Exception as e:
            print(f"[PriceService] yfinance batch error: {e}")
    
    return result


def get_crypto_price(symbol: str, use_cache: bool = True) -> dict:
    """
    Get cryptocurrency price (uses Finnhub crypto endpoint).
    Symbol format: 'BTC', 'ETH', etc.
    """
    symbol = symbol.upper().strip()
    cache_key = f"CRYPTO:{symbol}"
    
    if use_cache:
        cached = _price_cache.get(cache_key)
        if cached:
            cached['source'] = 'cache'
            return cached
    
    # Try Finnhub crypto
    try:
        client = get_finnhub_client()
        # Finnhub uses BINANCE:BTCUSDT format
        finnhub_symbol = f"BINANCE:{symbol}USDT"
        quote = client.quote(finnhub_symbol)
        
        if quote and quote.get('c'):
            data = {
                'price': quote['c'],
                'change': quote.get('d', 0),
                'change_pct': quote.get('dp', 0),
                'high': quote.get('h', 0),
                'low': quote.get('l', 0),
                'open': quote.get('o', 0),
                'prev_close': quote.get('pc', 0),
                'source': 'finnhub',
                'timestamp': time.time()
            }
            _price_cache.set(cache_key, data)
            return data
    except Exception as e:
        print(f"[PriceService] Finnhub crypto error for {symbol}: {e}")
    
    # Fallback to yfinance
    try:
        yf = get_yfinance()
        ticker = yf.Ticker(f"{symbol}-USD")
        info = ticker.fast_info
        data = {
            'price': info.last_price,
            'change': 0,
            'change_pct': 0,
            'source': 'yfinance',
            'timestamp': time.time()
        }
        _price_cache.set(cache_key, data)
        return data
    except Exception as e:
        print(f"[PriceService] yfinance crypto error for {symbol}: {e}")
    
    return {'price': None, 'source': 'error', 'symbol': symbol}


def get_argentina_price(ticker: str, use_cache: bool = True) -> dict:
    """
    Get price for BCBA (Buenos Aires Stock Exchange) tickers.
    Finnhub doesn't support BCBA, so we use yfinance with .BA suffix.
    """
    ticker = ticker.upper().strip()
    cache_key = f"BCBA:{ticker}"
    
    if use_cache:
        cached = _price_cache.get(cache_key)
        if cached:
            cached['source'] = 'cache'
            return cached
    
    # yfinance is the only reliable source for BCBA
    try:
        yf = get_yfinance()
        # Try with .BA suffix for BCBA
        yf_ticker = f"{ticker}.BA" if not ticker.endswith('.BA') else ticker
        t = yf.Ticker(yf_ticker)
        info = t.fast_info
        
        prev_close = info.previous_close or info.last_price
        change = info.last_price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0
        
        data = {
            'price': info.last_price,
            'change': change,
            'change_pct': change_pct,
            'high': info.day_high,
            'low': info.day_low,
            'open': info.open,
            'prev_close': prev_close,
            'source': 'yfinance',
            'timestamp': time.time()
        }
        _price_cache.set(cache_key, data)
        return data
    except Exception as e:
        print(f"[PriceService] BCBA error for {ticker}: {e}")
    
    return {'price': None, 'source': 'error', 'ticker': ticker}


# ============================================
# Internal Fetch Functions
# ============================================

def _fetch_finnhub(ticker: str) -> dict:
    """Fetch single ticker from Finnhub."""
    client = get_finnhub_client()
    quote = client.quote(ticker)
    
    if not quote or quote.get('c') is None or quote.get('c') == 0:
        return None
    
    return {
        'price': quote['c'],  # Current price
        'change': quote.get('d', 0),  # Change
        'change_pct': quote.get('dp', 0),  # Change percent
        'high': quote.get('h', 0),  # Day high
        'low': quote.get('l', 0),  # Day low
        'open': quote.get('o', 0),  # Open
        'prev_close': quote.get('pc', 0),  # Previous close
        'source': 'finnhub',
        'timestamp': time.time()
    }


def _fetch_yfinance(ticker: str) -> dict:
    """Fetch single ticker from yfinance."""
    yf = get_yfinance()
    t = yf.Ticker(ticker)
    info = t.fast_info
    
    if not info or not info.last_price:
        return None
    
    prev_close = info.previous_close or info.last_price
    change = info.last_price - prev_close if prev_close else 0
    change_pct = (change / prev_close * 100) if prev_close else 0
    
    return {
        'price': info.last_price,
        'change': change,
        'change_pct': change_pct,
        'high': info.day_high,
        'low': info.day_low,
        'open': info.open,
        'prev_close': prev_close,
        'source': 'yfinance',
        'timestamp': time.time()
    }


def _fetch_yfinance_batch(tickers: List[str]) -> Dict[str, dict]:
    """Fetch multiple tickers from yfinance in one call."""
    yf = get_yfinance()
    result = {}
    
    try:
        data = yf.download(tickers, period="5d", threads=True, progress=False)
        
        if data.empty:
            return result
        
        for ticker in tickers:
            try:
                if len(tickers) == 1:
                    close = data['Close']
                else:
                    close = data['Close'][ticker] if ticker in data['Close'].columns else None
                
                if close is None or close.empty:
                    continue
                
                last_price = float(close.iloc[-1])
                prev_price = float(close.iloc[-2]) if len(close) > 1 else last_price
                change = last_price - prev_price
                change_pct = (change / prev_price * 100) if prev_price else 0
                
                result[ticker] = {
                    'price': last_price,
                    'change': change,
                    'change_pct': change_pct,
                    'source': 'yfinance',
                    'timestamp': time.time()
                }
            except Exception as e:
                print(f"[PriceService] yfinance parse error for {ticker}: {e}")
    except Exception as e:
        print(f"[PriceService] yfinance batch download error: {e}")
    
    return result


# ============================================
# Utility Functions
# ============================================

def clear_cache():
    """Clear the price cache."""
    _price_cache.clear()
    return {'status': 'cleared'}


def cache_stats() -> dict:
    """Get cache statistics."""
    return _price_cache.stats()


# ============================================
# Test
# ============================================

if __name__ == "__main__":
    print("Testing PriceService...")
    
    # Test single price
    print("\n1. Single price (AAPL):")
    result = get_price("AAPL")
    print(f"   Price: ${result.get('price')}, Source: {result.get('source')}")
    
    # Test cache hit
    print("\n2. Cache hit (AAPL again):")
    result = get_price("AAPL")
    print(f"   Price: ${result.get('price')}, Source: {result.get('source')}")
    
    # Test batch
    print("\n3. Batch prices (TSLA, GOOGL, MSFT):")
    results = get_prices(["TSLA", "GOOGL", "MSFT"])
    for ticker, data in results.items():
        print(f"   {ticker}: ${data.get('price')}, Source: {data.get('source')}")
    
    # Test crypto
    print("\n4. Crypto (BTC):")
    result = get_crypto_price("BTC")
    print(f"   Price: ${result.get('price')}, Source: {result.get('source')}")
    
    # Test Argentina
    print("\n5. Argentina (GGAL):")
    result = get_argentina_price("GGAL")
    print(f"   Price: ${result.get('price')}, Source: {result.get('source')}")
    
    # Cache stats
    print("\n6. Cache stats:")
    print(f"   {cache_stats()}")


# ============================================
# Background Price Update (for scheduler)
# ============================================

def background_price_update():
    """
    Background job to pre-populate price cache for all open positions.
    Called by scheduler every 5 minutes.
    This makes user requests instant since prices are already cached.
    """
    from database import SessionLocal
    import models
    
    print("[PriceService] 🔄 Background price update starting...")
    
    db = SessionLocal()
    try:
        # Get all unique tickers from open positions across all users
        usa_tickers = set()
        argentina_tickers = set()
        crypto_tickers = set()
        
        # USA trades
        usa_trades = db.query(models.Trade).filter(models.Trade.status == "OPEN").all()
        for t in usa_trades:
            if t.ticker:
                usa_tickers.add(t.ticker.upper())
        
        # Argentina positions
        arg_positions = db.query(models.ArgentinaPosition).filter(models.ArgentinaPosition.status == "OPEN").all()
        for p in arg_positions:
            if p.ticker:
                argentina_tickers.add(p.ticker.upper())
        
        # Crypto positions
        crypto_positions = db.query(models.CryptoPosition).all()
        for p in crypto_positions:
            if p.ticker:
                crypto_tickers.add(p.ticker.upper())
        
        db.close()
        
        # Fetch and cache USA prices (batch)
        if usa_tickers:
            print(f"[PriceService] Fetching {len(usa_tickers)} USA tickers...")
            try:
                get_prices(list(usa_tickers))
                print(f"[PriceService] ✅ USA prices cached")
            except Exception as e:
                print(f"[PriceService] ⚠️ USA prices error: {e}")
        
        # Fetch and cache Argentina prices
        if argentina_tickers:
            print(f"[PriceService] Fetching {len(argentina_tickers)} Argentina tickers...")
            try:
                for ticker in argentina_tickers:
                    get_argentina_price(ticker)
                print(f"[PriceService] ✅ Argentina prices cached")
            except Exception as e:
                print(f"[PriceService] ⚠️ Argentina prices error: {e}")
        
        # Fetch and cache Crypto prices
        if crypto_tickers:
            print(f"[PriceService] Fetching {len(crypto_tickers)} Crypto tickers...")
            try:
                for ticker in crypto_tickers:
                    get_crypto_price(ticker)
                print(f"[PriceService] ✅ Crypto prices cached")
            except Exception as e:
                print(f"[PriceService] ⚠️ Crypto prices error: {e}")
        
        stats = cache_stats()
        print(f"[PriceService] ✅ Background update complete. Cache: {stats['entries']} entries")
        
    except Exception as e:
        print(f"[PriceService] ❌ Background update error: {e}")
    finally:
        try:
            db.close()
        except:
            pass
