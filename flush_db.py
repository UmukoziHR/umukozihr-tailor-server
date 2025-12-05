#!/usr/bin/env python3
"""
Database flush script - Carefully deletes all data from tables while preserving schema
"""
import os
import sys
from pathlib import Path

# Add the server directory to the path so we can import our modules
server_dir = Path(__file__).parent
sys.path.insert(0, str(server_dir))

from dotenv import load_dotenv
load_dotenv()

from app.db.database import SessionLocal, engine
from app.db.models import User, Profile, Job, Run
from sqlalchemy import text

def flush_database():
    """Carefully delete all data from all tables in the correct order"""
    print("UmukoziHR Resume Tailor - Database Flush")
    print("=======================================")
    
    db_url = os.getenv("DATABASE_URL", "sqlite:///./umukozihr.db")
    print(f"Database URL: {db_url}")
    
    db = SessionLocal()
    
    try:
        # Check if tables exist
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if not tables:
            print("No tables found in database. Nothing to flush.")
            db.close()
            return True
        
        print(f"\nFound tables: {tables}")
        
        # Count records before deletion
        counts = {}
        if 'runs' in tables:
            counts['runs'] = db.query(Run).count()
        if 'jobs' in tables:
            counts['jobs'] = db.query(Job).count()
        if 'profiles' in tables:
            counts['profiles'] = db.query(Profile).count()
        if 'users' in tables:
            counts['users'] = db.query(User).count()
        
        print("\nCurrent record counts:")
        for table, count in counts.items():
            print(f"  {table}: {count} records")
        
        if sum(counts.values()) == 0:
            print("\nDatabase is already empty. Nothing to flush.")
            db.close()
            return True
        
        print("\n⚠️  WARNING: This will delete ALL data from the database!")
        print("   Schema will be preserved, but all records will be removed.")
        
        # Delete in correct order to respect foreign key constraints
        # Order: runs -> jobs -> profiles -> users
        deleted_counts = {}
        
        # Delete runs first (has foreign keys to jobs and users)
        if 'runs' in tables:
            runs_count = db.query(Run).count()
            if runs_count > 0:
                db.query(Run).delete()
                deleted_counts['runs'] = runs_count
                print(f"  ✓ Deleted {runs_count} records from 'runs' table")
        
        # Delete jobs (has foreign key to users)
        if 'jobs' in tables:
            jobs_count = db.query(Job).count()
            if jobs_count > 0:
                db.query(Job).delete()
                deleted_counts['jobs'] = jobs_count
                print(f"  ✓ Deleted {jobs_count} records from 'jobs' table")
        
        # Delete profiles (has foreign key to users)
        if 'profiles' in tables:
            profiles_count = db.query(Profile).count()
            if profiles_count > 0:
                db.query(Profile).delete()
                deleted_counts['profiles'] = profiles_count
                print(f"  ✓ Deleted {profiles_count} records from 'profiles' table")
        
        # Delete users last
        if 'users' in tables:
            users_count = db.query(User).count()
            if users_count > 0:
                db.query(User).delete()
                deleted_counts['users'] = users_count
                print(f"  ✓ Deleted {users_count} records from 'users' table")
        
        # Commit all deletions
        db.commit()
        
        print("\n✅ Database flush completed successfully!")
        print(f"   Total records deleted: {sum(deleted_counts.values())}")
        
        # Verify deletion
        print("\nVerifying deletion...")
        final_counts = {}
        if 'runs' in tables:
            final_counts['runs'] = db.query(Run).count()
        if 'jobs' in tables:
            final_counts['jobs'] = db.query(Job).count()
        if 'profiles' in tables:
            final_counts['profiles'] = db.query(Profile).count()
        if 'users' in tables:
            final_counts['users'] = db.query(User).count()
        
        if sum(final_counts.values()) == 0:
            print("✅ All tables are now empty!")
        else:
            print("⚠️  Warning: Some records may still exist")
            for table, count in final_counts.items():
                if count > 0:
                    print(f"  {table}: {count} records remain")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Error flushing database: {e}")
        db.rollback()
        db.close()
        return False

if __name__ == "__main__":
    success = flush_database()
    if success:
        print("\n[OK] Database flush completed. You can now run migrations and start the server.")
        sys.exit(0)
    else:
        print("\n[ERROR] Database flush failed. Please check the error messages above.")
        sys.exit(1)
















