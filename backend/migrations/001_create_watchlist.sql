-- Create watchlist table for storing tickers with alerts
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,
    entry_price REAL NOT NULL,
    alert_price REAL,
    stop_alert REAL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster ticker lookups
CREATE INDEX IF NOT EXISTS idx_watchlist_ticker ON watchlist(ticker);
