#!/usr/bin/env python3
"""
Migration script for UmukoziHR Resume Tailor v1.3
Creates database tables if they don't exist and migrates v1.2 schema to v1.3.
"""
import os
import sys
from pathlib import Path

# Add the server directory to the path so we can import our modules
server_dir = Path(__file__).parent
sys.path.insert(0, str(server_dir))

from app.db.database import engine, Base
from app.db.models import User, Profile, Job, Run, UserEvent, GenerationMetric, SystemLog
from app.auth.auth import hash_password

def migrate_v1_2_to_v1_3(db):
    """Migrate v1.2 schema to v1.3 by adding new columns"""
    from sqlalchemy import text, inspect

    print("\n--- Checking for v1.3 schema migrations ---")

    inspector = inspect(engine)

    # Check profiles table for new columns
    profiles_columns = [col['name'] for col in inspector.get_columns('profiles')] if inspector.has_table('profiles') else []
    users_columns = [col['name'] for col in inspector.get_columns('users')] if inspector.has_table('users') else []

    migrations = []

    # User table enhancements for v1.3 final
    if 'users' in inspector.get_table_names():
        if 'is_admin' not in users_columns:
            if "postgresql" in str(engine.url):
                migrations.append("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE")
            else:
                migrations.append("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        
        if 'is_verified' not in users_columns:
            if "postgresql" in str(engine.url):
                migrations.append("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT FALSE")
            else:
                migrations.append("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0")
        
        if 'last_login_at' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP")
        
        if 'onboarding_completed' not in users_columns:
            if "postgresql" in str(engine.url):
                migrations.append("ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT FALSE")
            else:
                migrations.append("ALTER TABLE users ADD COLUMN onboarding_completed INTEGER DEFAULT 0")
        
        if 'onboarding_step' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN onboarding_step INTEGER DEFAULT 0")
        
        # Location tracking columns (v1.3.1)
        if 'country' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN country VARCHAR")
        
        if 'country_name' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN country_name VARCHAR")
        
        if 'city' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN city VARCHAR")
        
        if 'signup_ip' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN signup_ip VARCHAR")
        
        # Shareable profiles columns (v1.4)
        if 'username' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN username VARCHAR UNIQUE")
            migrations.append("CREATE INDEX IF NOT EXISTS ix_users_username ON users (username)")
        
        if 'is_public' not in users_columns:
            if "postgresql" in str(engine.url):
                migrations.append("ALTER TABLE users ADD COLUMN is_public BOOLEAN DEFAULT TRUE")
            else:
                migrations.append("ALTER TABLE users ADD COLUMN is_public INTEGER DEFAULT 1")
        
        if 'profile_views' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN profile_views INTEGER DEFAULT 0")
        
        # Subscription & Payment columns (v1.4 prep)
        if 'subscription_tier' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN subscription_tier VARCHAR DEFAULT 'free'")
        
        if 'subscription_status' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN subscription_status VARCHAR DEFAULT 'active'")
        
        if 'subscription_started_at' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN subscription_started_at TIMESTAMP")
        
        if 'subscription_expires_at' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN subscription_expires_at TIMESTAMP")
        
        if 'stripe_customer_id' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR")
        
        # v1.4 Paystack/Subscription columns
        if 'region_group' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN region_group VARCHAR DEFAULT 'global'")
        
        if 'paystack_customer_code' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN paystack_customer_code VARCHAR")
        
        if 'paystack_subscription_code' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN paystack_subscription_code VARCHAR")
        
        if 'monthly_generations_used' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN monthly_generations_used INTEGER DEFAULT 0")
        
        if 'monthly_generations_limit' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN monthly_generations_limit INTEGER DEFAULT 5")
        
        if 'usage_reset_at' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN usage_reset_at TIMESTAMP")
        
        # v1.5 Avatar column
        if 'avatar_url' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN avatar_url VARCHAR")
        
        # v1.6 OAuth auth_provider column
        if 'auth_provider' not in users_columns:
            migrations.append("ALTER TABLE users ADD COLUMN auth_provider VARCHAR DEFAULT 'email'")
        
        # v1.6 Make password_hash nullable for OAuth users
        # This always runs to ensure constraint is dropped
        if "postgresql" in str(engine.url):
            migrations.append("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL")

    if 'profiles' in inspector.get_table_names():
        # Add version column
        if 'version' not in profiles_columns:
            migrations.append("ALTER TABLE profiles ADD COLUMN version INTEGER DEFAULT 1")

        # Add completeness column
        if 'completeness' not in profiles_columns:
            if "postgresql" in str(engine.url):
                migrations.append("ALTER TABLE profiles ADD COLUMN completeness DOUBLE PRECISION DEFAULT 0.0")
            else:
                migrations.append("ALTER TABLE profiles ADD COLUMN completeness REAL DEFAULT 0.0")

        # Make user_id unique if not already
        if 'user_id' in profiles_columns:
            try:
                # Try to create unique constraint (may fail if already exists)
                if "postgresql" in str(engine.url):
                    migrations.append("ALTER TABLE profiles ADD CONSTRAINT profiles_user_id_key UNIQUE (user_id)")
                else:
                    # SQLite requires recreating table for constraints, skip for now
                    pass
            except:
                pass

    if 'jobs' in inspector.get_table_names():
        jobs_columns = [col['name'] for col in inspector.get_columns('jobs')]

        # Add url column
        if 'url' not in jobs_columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN url VARCHAR")

        # Add is_fetched column
        if 'is_fetched' not in jobs_columns:
            if "postgresql" in str(engine.url):
                migrations.append("ALTER TABLE jobs ADD COLUMN is_fetched BOOLEAN DEFAULT FALSE")
            else:
                migrations.append("ALTER TABLE jobs ADD COLUMN is_fetched INTEGER DEFAULT 0")

        # Add fetch_status column
        if 'fetch_status' not in jobs_columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN fetch_status VARCHAR")

    if 'runs' in inspector.get_table_names():
        runs_columns = [col['name'] for col in inspector.get_columns('runs')]

        # Add profile_version column
        if 'profile_version' not in runs_columns:
            migrations.append("ALTER TABLE runs ADD COLUMN profile_version INTEGER")

    # Execute migrations
    if migrations:
        print(f"Applying {len(migrations)} schema migrations...")
        for migration in migrations:
            try:
                print(f"  - {migration}")
                db.execute(text(migration))
                db.commit()
            except Exception as e:
                # May fail if column already exists (race condition)
                db.rollback()  # Rollback failed transaction
                err_str = str(e).lower()
                if "already exists" in err_str or "duplicate" in err_str or "does not exist" in err_str:
                    print(f"    (already applied, skipping)")
                else:
                    print(f"    [ERROR]: {e}")
        print("[OK] Migrations completed")
    else:
        print("[OK] Schema is up to date")


def create_tables():
    """Create all database tables"""
    try:
        print("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        print("Database tables created successfully!")

        # Test connection
        from app.db.database import SessionLocal
        db = SessionLocal()

        # Check if tables were created
        from sqlalchemy import text
        if "postgresql" in str(engine.url):
            # PostgreSQL
            result = db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
            tables = [row[0] for row in result.fetchall()]
        elif "sqlite" in str(engine.url):
            # SQLite
            result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
            tables = [row[0] for row in result.fetchall()]
        else:
            tables = []

        expected_tables = ['users', 'profiles', 'jobs', 'runs', 'user_events', 'generation_metrics', 'system_logs']
        created_tables = [table for table in expected_tables if table in tables]

        print(f"Created tables: {created_tables}")

        if len(created_tables) == len(expected_tables):
            print("All required tables (including analytics) created successfully!")
        else:
            missing = set(expected_tables) - set(created_tables)
            print(f"Missing tables: {missing}")

        # Run v1.2 → v1.3 migrations
        migrate_v1_2_to_v1_3(db)

        # Setup admin user
        setup_admin_user(db)

        db.close()

    except Exception as e:
        print(f"[ERROR] Error creating tables: {e}")
        print("Make sure PostgreSQL is running and the DATABASE_URL is correct.")
        sys.exit(1)

def check_connection():
    """Check if we can connect to the database"""
    try:
        from app.db.database import SessionLocal
        db = SessionLocal()
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db.close()
        print("Database connection successful!")
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        print("Please check your DATABASE_URL and ensure PostgreSQL is running.")
        return False

def setup_admin_user(db):
    """
    Set up the admin user account.
    Creates the admin user if they don't exist, or updates existing user to admin.
    """
    from sqlalchemy import text
    import uuid

    ADMIN_EMAIL = "team@umukozihr.com"
    # Secure password: UmukoziHR_Admin2026!
    ADMIN_PASSWORD = "UmukoziHR_Admin2026!"

    print("\n--- Setting up admin user ---")

    try:
        # Check if user exists
        result = db.execute(
            text("SELECT id, email, is_admin FROM users WHERE email = :email"),
            {"email": ADMIN_EMAIL}
        )
        existing_user = result.fetchone()

        if existing_user:
            user_id, email, is_admin = existing_user
            # Always update password and ensure onboarding completed
            new_password_hash = hash_password(ADMIN_PASSWORD)
            db.execute(
                text("UPDATE users SET password_hash = :password_hash, is_admin = TRUE, onboarding_completed = TRUE WHERE email = :email"),
                {"email": ADMIN_EMAIL, "password_hash": new_password_hash}
            )
            db.commit()
            print(f"[OK] Admin user {ADMIN_EMAIL} updated with new password")
        else:
            # Create new admin user
            user_id = str(uuid.uuid4())
            password_hash = hash_password(ADMIN_PASSWORD)

            db.execute(
                text("""
                    INSERT INTO users (id, email, password_hash, is_admin, is_verified, onboarding_completed, onboarding_step, created_at)
                    VALUES (:id, :email, :password_hash, TRUE, TRUE, TRUE, 0, NOW())
                """),
                {
                    "id": user_id,
                    "email": ADMIN_EMAIL,
                    "password_hash": password_hash
                }
            )
            db.commit()
            print(f"[OK] Created admin user: {ADMIN_EMAIL}")
            print(f"    Password: {ADMIN_PASSWORD}")

    except Exception as e:
        print(f"[WARN] Admin setup issue: {e}")
        # Don't fail migration for admin setup issues


if __name__ == "__main__":
    print("UmukoziHR Resume Tailor v1.3 Migration")
    print("=====================================")

    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    db_url = os.getenv("DATABASE_URL")
    print(f"Database URL: {db_url}")

    if check_connection():
        create_tables()
        print("\n[OK] Migration completed! You can now start the server.")
    else:
        print("\nTip: Make sure your database is running and your credentials are correct.")
        sys.exit(1)