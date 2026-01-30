"""
Configuration module for Momentum Trader.
Manages API keys and data provider settings.
"""
import os

# =============================================================================
# FINNHUB CONFIGURATION
# =============================================================================
# Get API key from environment variable, or use hardcoded fallback
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "cvmo1npr01ql90pv62e0cvmo1npr01ql90pv62eg")

# Rate limiting: Finnhub free tier = 60 calls per minute
FINNHUB_RATE_LIMIT = 60  # calls per minute
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

# =============================================================================
# DATA PROVIDER CONFIGURATION
# =============================================================================
# Order of fallback: try Yahoo first (more history), then Finnhub
DATA_PROVIDERS = ["yahoo", "finnhub"]

# Enable/disable Finnhub fallback
FINNHUB_ENABLED = bool(FINNHUB_API_KEY)
