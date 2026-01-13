import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Get database URL from environment variable - NO FALLBACK!
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("\n" + "="*60)
    print("FATAL ERROR: DATABASE_URL environment variable not set!")
    print("="*60)
    print("Please set DATABASE_URL to your PostgreSQL connection string.")
    print("Example: postgresql://user:pass@host:5432/dbname")
    print("="*60 + "\n")
    sys.exit(1)

print(f"Connecting to database: {DATABASE_URL[:20]}... (type: {'PostgreSQL' if 'postgresql' in DATABASE_URL else 'SQLite' if 'sqlite' in DATABASE_URL else 'Unknown'})")

# Create engine
engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()