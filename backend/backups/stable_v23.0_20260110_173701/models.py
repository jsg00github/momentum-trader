from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    trades = relationship("Trade", back_populates="user")
    snapshots = relationship("PortfolioSnapshot", back_populates="user")
    argentina_positions = relationship("ArgentinaPosition", back_populates="user")
    crypto_positions = relationship("CryptoPosition", back_populates="user")

class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True) # Changed from String to FK
    
    ticker = Column(String, index=True)
    entry_date = Column(Date)
    exit_date = Column(Date, nullable=True)
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    shares = Column(Integer)
    direction = Column(String, default="LONG") 
    status = Column(String, default="OPEN")
    strategy = Column(String)
    notes = Column(String, nullable=True)
    
    # Analytics
    elliott_pattern = Column(String, nullable=True)
    risk_level = Column(String, nullable=True)
    stop_loss = Column(Float, nullable=True)
    target = Column(Float, nullable=True)
    target2 = Column(Float, nullable=True)
    target3 = Column(Float, nullable=True)
    external_id = Column(String, nullable=True)
    
    pnl = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="trades")

class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    date = Column(String, index=True) # Keeping as String YYYY-MM-DD for consistency with chart libs
    
    total_invested_usd = Column(Float, default=0)
    total_value_usd = Column(Float, default=0)
    total_pnl_usd = Column(Float, default=0)
    total_pnl_pct = Column(Float, default=0)
    
    # Regional Breakdown
    usa_invested_usd = Column(Float, default=0)
    usa_value_usd = Column(Float, default=0)
    usa_pnl_usd = Column(Float, default=0)
    
    argentina_invested_usd = Column(Float, default=0)
    argentina_value_usd = Column(Float, default=0)
    argentina_pnl_usd = Column(Float, default=0)
    
    crypto_invested_usd = Column(Float, default=0)
    crypto_value_usd = Column(Float, default=0)
    crypto_pnl_usd = Column(Float, default=0)
    
    # Time
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="snapshots")

class ArgentinaPosition(Base):
    __tablename__ = "argentina_positions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    ticker = Column(String)
    asset_type = Column(String) # stock, cedear, option
    entry_date = Column(String)
    entry_price = Column(Float)
    shares = Column(Float)
    
    # Option specifics
    option_strike = Column(Float, nullable=True)
    option_expiry = Column(String, nullable=True)
    option_type = Column(String, nullable=True)
    
    # Strategy & Outcome
    stop_loss = Column(Float, nullable=True)
    target = Column(Float, nullable=True)
    target2 = Column(Float, nullable=True)
    target3 = Column(Float, nullable=True)
    strategy = Column(String, nullable=True)
    hypothesis = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    
    status = Column(String, default="OPEN")
    exit_date = Column(String, nullable=True)
    exit_price = Column(Float, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="argentina_positions")

class CryptoPosition(Base):
    __tablename__ = "crypto_positions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    ticker = Column(String)
    amount = Column(Float)
    entry_price = Column(Float)
    current_price = Column(Float, nullable=True)
    source = Column(String, default="MANUAL")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="crypto_positions")

class BinanceConfig(Base):
    __tablename__ = "binance_config"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    api_key = Column(String)
    api_secret = Column(String)
    
    user = relationship("User", back_populates="binance_config")

# Update User relationship
User.binance_config = relationship("BinanceConfig", uselist=False, back_populates="user")
User.watchlist_items = relationship("Watchlist", back_populates="user")

class Watchlist(Base):
    __tablename__ = "watchlist"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    ticker = Column(String, index=True)
    entry_price = Column(Float, default=0.0)
    alert_price = Column(Float, nullable=True) # Buy Alert
    stop_alert = Column(Float, nullable=True) # SL Alert
    
    strategy = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    hypothesis = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="watchlist_items")
