import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Get database URL from environment variable - NO FALLBACK!
DATABASE_URL = os.getenv("DATABASE_URL")

print("="*60)
print("DATABASE INITIALIZATION")
print("="*60)

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set!")
    print("All environment variables:")
    for key in sorted(os.environ.keys()):
        if 'SECRET' not in key.upper() and 'PASSWORD' not in key.upper() and 'KEY' not in key.upper():
            print(f"  {key}={os.environ[key][:50]}..." if len(os.environ.get(key, '')) > 50 else f"  {key}={os.environ.get(key)}")
    # Use a dummy SQLite to let the app start (will fail on actual queries)
    DATABASE_URL = "sqlite:///./fallback_error.db"
    print(f"FALLING BACK TO: {DATABASE_URL}")
else:
    # Mask password in logs
    safe_url = DATABASE_URL
    if '@' in DATABASE_URL:
        parts = DATABASE_URL.split('@')
        safe_url = parts[0].split(':')[0] + ':****@' + parts[1]
    print(f"DATABASE_URL: {safe_url}")
    print(f"Database type: {'PostgreSQL' if 'postgresql' in DATABASE_URL else 'SQLite' if 'sqlite' in DATABASE_URL else 'Unknown'}")

print("="*60)

# Create engine with connection pool settings for production
if 'postgresql' in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Test connections before using
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        connect_args={
            "connect_timeout": 10,  # 10 second connection timeout
        }
    )
else:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Test connection on startup
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("Database connection: SUCCESS")
except Exception as e:
    print(f"Database connection: FAILED - {type(e).__name__}: {e}")
    logger.error(f"Database connection failed: {e}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()