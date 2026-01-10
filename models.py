from sqlalchemy import Column, Integer, String, Float, Date, DateTime
from sqlalchemy.sql import func
from database import Base

class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, default="default_user")
    ticker = Column(String, index=True)
    entry_date = Column(Date)
    exit_date = Column(Date, nullable=True)
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    shares = Column(Integer)
    direction = Column(String, default="LONG") # Added direction support
    status = Column(String, default="OPEN")
    strategy = Column(String)
    notes = Column(String, nullable=True)
    
    # Optional analytics columns (nullable for flexibility)
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
