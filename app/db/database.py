import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Get database URL from environment variable - MUST BE SET!
DATABASE_URL = os.getenv("DATABASE_URL")

print("="*60)
print("DATABASE INITIALIZATION")
print("="*60)

if not DATABASE_URL:
    print("FATAL: DATABASE_URL environment variable NOT SET!")
    print("")
    print("Environment variables found:")
    for key in sorted(os.environ.keys()):
        # Don't print secrets
        if 'SECRET' not in key.upper() and 'PASSWORD' not in key.upper() and 'KEY' not in key.upper():
            val = os.environ.get(key, '')
            print(f"  {key} = {val[:80]}{'...' if len(val) > 80 else ''}")
    print("")
    raise RuntimeError("DATABASE_URL environment variable is required but not set!")

if 'sqlite' in DATABASE_URL.lower():
    raise RuntimeError(f"SQLite is NOT allowed in production! Got: {DATABASE_URL}")

# Mask password for logging
safe_url = DATABASE_URL
if '@' in DATABASE_URL:
    parts = DATABASE_URL.split('@')
    creds = parts[0].split('://')[-1]
    user = creds.split(':')[0] if ':' in creds else creds
    safe_url = DATABASE_URL.split('://')[0] + '://' + user + ':****@' + parts[1]

print(f"DATABASE_URL: {safe_url}")
print("="*60)

# Create PostgreSQL engine with proper settings
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    connect_args={"connect_timeout": 10}
)

# Test connection immediately
print("Testing database connection...")
try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("Database connection: SUCCESS")
except Exception as e:
    print(f"Database connection: FAILED")
    print(f"Error: {type(e).__name__}: {e}")
    raise RuntimeError(f"Cannot connect to database: {e}")

print("="*60)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()