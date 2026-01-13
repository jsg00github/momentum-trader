from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import sys

# Get DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///trades.db")

# Log connection attempt (redacted)
safe_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else "local/sqlite"
print(f"[DATABASE] Connecting to: ...@{safe_url}")

# Railway fix: handle postgres:// -> postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Ensure no leading/trailing whitespace
if DATABASE_URL:
    DATABASE_URL = DATABASE_URL.strip()

# Check for empty URL
if not DATABASE_URL:
    print("[CRITICAL] DATABASE_URL is empty!")
    sys.exit(1)

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
except Exception as e:
    print(f"[CRITICAL] Error creating engine: {e}")
    # Force exit to show log
    sys.exit(1)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
