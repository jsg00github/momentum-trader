"""
Argentina Market Data Module
- IOL API integration for quotes, options, portfolio
- CCL/MEP rates from DolarAPI
- BCRA rates for risk-free rate
"""
import os
import requests
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import math

# IOL API Configuration
IOL_API_BASE = "https://api.invertironline.com"
IOL_SANDBOX_BASE = "https://api.invertironline.com"  # Same URL, sandbox mode via account

# Token storage
_iol_tokens = {
    "access_token": None,
    "refresh_token": None,
    "expires_at": None
}

# Cache for rates
_rates_cache = {
    "ccl": None,
    "mep": None,
    "oficial": None,
    "bcra_rate": None,
    "updated_at": None
}

# ============================================
# IOL API Authentication
# ============================================

def iol_login(username: str, password: str) -> bool:
    """
    Login to IOL API and get access token.
    Returns True if successful.
    """
    url = f"{IOL_API_BASE}/token"
    data = {
        "username": username,
        "password": password,
        "grant_type": "password"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    try:
        response = requests.post(url, data=data, headers=headers, timeout=10)
        if response.status_code == 200:
            token_data = response.json()
            _iol_tokens["access_token"] = token_data.get("access_token")
            _iol_tokens["refresh_token"] = token_data.get("refresh_token")
            # Token valid for 15 minutes
            _iol_tokens["expires_at"] = datetime.now() + timedelta(minutes=14)
            return True
        else:
            print(f"IOL login failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"IOL login error: {e}")
        return False


def iol_refresh_token() -> bool:
    """Refresh the access token using refresh token."""
    if not _iol_tokens["refresh_token"]:
        return False
    
    url = f"{IOL_API_BASE}/token"
    data = {
        "refresh_token": _iol_tokens["refresh_token"],
        "grant_type": "refresh_token"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    try:
        response = requests.post(url, data=data, headers=headers, timeout=10)
        if response.status_code == 200:
            token_data = response.json()
            _iol_tokens["access_token"] = token_data.get("access_token")
            _iol_tokens["refresh_token"] = token_data.get("refresh_token")
            _iol_tokens["expires_at"] = datetime.now() + timedelta(minutes=14)
            return True
    except Exception as e:
        print(f"IOL refresh error: {e}")
    return False


def get_iol_headers() -> Dict[str, str]:
    """Get headers with valid access token, refreshing if needed."""
    # Check if token is expired
    if _iol_tokens["expires_at"] and datetime.now() >= _iol_tokens["expires_at"]:
        iol_refresh_token()
    
    return {
        "Authorization": f"Bearer {_iol_tokens['access_token']}",
        "Content-Type": "application/json"
    }


def is_iol_authenticated() -> bool:
    """Check if we have a valid IOL token."""
    return _iol_tokens["access_token"] is not None


# ============================================
# IOL API - Market Data
# ============================================

def get_iol_quote(ticker: str, market: str = "bCBA") -> Optional[Dict]:
    """
    Get current quote for a ticker from IOL.
    market: 'bCBA' for BYMA, 'nYSE', 'nASDAQ' for US
    """
    if not is_iol_authenticated():
        return None
    
    url = f"{IOL_API_BASE}/api/v2/Cotizaciones/{market}/{ticker}"
    
    try:
        response = requests.get(url, headers=get_iol_headers(), timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"IOL quote error for {ticker}: {e}")
    return None


def get_iol_options(underlying: str) -> List[Dict]:
    """
    Get all options for an underlying asset.
    Returns list of option contracts with premium, strike, expiry.
    """
    if not is_iol_authenticated():
        return []
    
    # IOL endpoint for options panel
    url = f"{IOL_API_BASE}/api/v2/Cotizaciones/Opciones/{underlying}"
    
    try:
        response = requests.get(url, headers=get_iol_headers(), timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"IOL options error for {underlying}: {e}")
    return []


def get_iol_portfolio() -> Dict:
    """Get user's current portfolio from IOL."""
    if not is_iol_authenticated():
        return {}
    
    url = f"{IOL_API_BASE}/api/v2/portafolio/argentina"
    
    try:
        response = requests.get(url, headers=get_iol_headers(), timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"IOL portfolio error: {e}")
    return {}


# ============================================
# CCL / MEP / Oficial Rates
# ============================================

def get_dolar_rates() -> Dict[str, float]:
    """
    Get current CCL, MEP, and Oficial rates from DolarAPI.
    Returns dict with 'ccl', 'mep', 'oficial' keys.
    """
    global _rates_cache
    
    # Use cache if updated within last 5 minutes
    if _rates_cache["updated_at"]:
        if datetime.now() - _rates_cache["updated_at"] < timedelta(minutes=5):
            return {
                "ccl": _rates_cache["ccl"],
                "mep": _rates_cache["mep"],
                "oficial": _rates_cache["oficial"]
            }
    
    try:
        response = requests.get("https://dolarapi.com/v1/dolares", timeout=10)
        if response.status_code == 200:
            data = response.json()
            rates = {}
            for item in data:
                if item.get("casa") == "contadoconliqui":
                    rates["ccl"] = item.get("venta", 0)
                elif item.get("casa") == "bolsa":
                    rates["mep"] = item.get("venta", 0)
                elif item.get("casa") == "oficial":
                    rates["oficial"] = item.get("venta", 0)
            
            # Update cache
            _rates_cache["ccl"] = rates.get("ccl", 0)
            _rates_cache["mep"] = rates.get("mep", 0)
            _rates_cache["oficial"] = rates.get("oficial", 0)
            _rates_cache["updated_at"] = datetime.now()
            
            return rates
    except Exception as e:
        print(f"DolarAPI error: {e}")
    
    # Return cached values if API fails
    return {
        "ccl": _rates_cache.get("ccl", 1200),
        "mep": _rates_cache.get("mep", 1150),
        "oficial": _rates_cache.get("oficial", 1050)
    }


# ============================================
# BCRA Rate (Risk-Free Rate)
# ============================================

def get_bcra_rate() -> float:
    """
    Get current BCRA reference rate (Badlar or similar).
    Returns annual rate as decimal (e.g., 0.40 for 40%).
    """
    global _rates_cache
    
    # Use cache if updated within last hour
    if _rates_cache["bcra_rate"] and _rates_cache["updated_at"]:
        if datetime.now() - _rates_cache["updated_at"] < timedelta(hours=1):
            return _rates_cache["bcra_rate"]
    
    try:
        # Using BCRA API for Badlar rate
        # Alternative: scraping BCRA website or using estimated rate
        response = requests.get(
            "https://api.bcra.gob.ar/estadisticas/v2.0/principalesvariables",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            # Look for Badlar or similar rate
            for var in data.get("results", []):
                if "badlar" in var.get("descripcion", "").lower():
                    rate = float(var.get("valor", 40)) / 100
                    _rates_cache["bcra_rate"] = rate
                    return rate
    except Exception as e:
        print(f"BCRA API error: {e}")
    
    # Default to 40% annual if API fails
    return 0.40


# ============================================
# BYMA Price via Yahoo Finance (Fallback)
# ============================================

def get_byma_price_yf(ticker: str) -> Optional[float]:
    """
    Get BYMA stock price from Yahoo Finance as fallback.
    Ticker should include .BA suffix (e.g., GGAL.BA)
    """
    import yfinance as yf
    
    try:
        if not ticker.endswith(".BA"):
            ticker = f"{ticker}.BA"
        
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
    except Exception as e:
        print(f"Yahoo Finance error for {ticker}: {e}")
    return None


# ============================================
# Utility Functions
# ============================================

def convert_ars_to_usd(amount_ars: float, rate_type: str = "mep") -> float:
    """Convert ARS amount to USD using specified rate type."""
    rates = get_dolar_rates()
    rate = rates.get(rate_type, rates.get("mep", 1200))
    if rate <= 0:
        rate = 1200  # Fallback
    return round(amount_ars / rate, 2)


def convert_usd_to_ars(amount_usd: float, rate_type: str = "mep") -> float:
    """Convert USD amount to ARS using specified rate type."""
    rates = get_dolar_rates()
    rate = rates.get(rate_type, rates.get("mep", 1200))
    return round(amount_usd * rate, 2)


# ============================================
# Black-Scholes Options Pricing
# ============================================

def norm_cdf(x: float) -> float:
    """Cumulative distribution function for standard normal."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def norm_pdf(x: float) -> float:
    """Probability density function for standard normal."""
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def black_scholes_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Calculate Black-Scholes price for a European call option.
    S: Current stock price
    K: Strike price
    T: Time to expiration in years
    r: Risk-free rate (annual)
    sigma: Volatility (annual)
    """
    if T <= 0 or sigma <= 0:
        return max(0, S - K)  # Intrinsic value
    
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    call_price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    return round(call_price, 2)


def black_scholes_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Calculate Black-Scholes price for a European put option."""
    if T <= 0 or sigma <= 0:
        return max(0, K - S)  # Intrinsic value
    
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    put_price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
    return round(put_price, 2)


def calculate_greeks(S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call") -> Dict[str, float]:
    """
    Calculate option Greeks.
    Returns dict with delta, gamma, theta, vega, rho.
    """
    if T <= 0 or sigma <= 0:
        return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0, "rho": 0}
    
    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    
    # Delta
    if option_type == "call":
        delta = norm_cdf(d1)
    else:
        delta = norm_cdf(d1) - 1
    
    # Gamma (same for call and put)
    gamma = norm_pdf(d1) / (S * sigma * sqrt_T)
    
    # Theta (per day)
    theta_part1 = -(S * norm_pdf(d1) * sigma) / (2 * sqrt_T)
    if option_type == "call":
        theta = (theta_part1 - r * K * math.exp(-r * T) * norm_cdf(d2)) / 365
    else:
        theta = (theta_part1 + r * K * math.exp(-r * T) * norm_cdf(-d2)) / 365
    
    # Vega (per 1% change in volatility)
    vega = S * sqrt_T * norm_pdf(d1) / 100
    
    # Rho (per 1% change in rate)
    if option_type == "call":
        rho = K * T * math.exp(-r * T) * norm_cdf(d2) / 100
    else:
        rho = -K * T * math.exp(-r * T) * norm_cdf(-d2) / 100
    
    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 4),
        "theta": round(theta, 4),
        "vega": round(vega, 4),
        "rho": round(rho, 4)
    }


def calculate_implied_volatility(
    market_price: float, S: float, K: float, T: float, r: float, 
    option_type: str = "call", max_iterations: int = 100
) -> float:
    """
    Calculate implied volatility using Newton-Raphson method.
    Returns IV as decimal (e.g., 0.35 for 35%).
    """
    sigma = 0.3  # Initial guess
    
    for _ in range(max_iterations):
        if option_type == "call":
            price = black_scholes_call(S, K, T, r, sigma)
        else:
            price = black_scholes_put(S, K, T, r, sigma)
        
        diff = market_price - price
        
        if abs(diff) < 0.001:
            return round(sigma, 4)
        
        # Vega for Newton-Raphson
        sqrt_T = math.sqrt(T) if T > 0 else 0.001
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T) if sigma > 0 else 0
        vega = S * sqrt_T * norm_pdf(d1)
        
        if vega < 0.001:
            break
        
        sigma = sigma + diff / vega
        sigma = max(0.01, min(sigma, 5.0))  # Clamp between 1% and 500%
    
    return round(sigma, 4)


def calculate_historical_volatility(prices: List[float], window: int = 21) -> float:
    """
    Calculate historical volatility from price list.
    Returns annualized volatility as decimal.
    """
    if len(prices) < window + 1:
        return 0.30  # Default 30%
    
    # Calculate log returns
    returns = []
    for i in range(1, len(prices)):
        if prices[i-1] > 0:
            returns.append(math.log(prices[i] / prices[i-1]))
    
    if len(returns) < window:
        return 0.30
    
    # Use last 'window' returns
    recent_returns = returns[-window:]
    
    # Calculate standard deviation
    mean_return = sum(recent_returns) / len(recent_returns)
    variance = sum((r - mean_return) ** 2 for r in recent_returns) / len(recent_returns)
    std_dev = math.sqrt(variance)
    
    # Annualize (252 trading days)
    annual_vol = std_dev * math.sqrt(252)
    
    return round(annual_vol, 4)
