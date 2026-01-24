"""Quick script to manually upgrade a user to Pro"""
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

# AWS RDS connection
DATABASE_URL = "postgresql://postgres:lRpyQ2D6wukqDqQvEVhj@umukozihr-rds.cpqy0ug0yn34.eu-west-1.rds.amazonaws.com:5432/tailor"

EMAIL = "jasonquist.ssh@gmail.com"

def upgrade_user():
    engine = create_engine(DATABASE_URL)
    
    now = datetime.utcnow()
    expires_at = now + timedelta(days=30)
    
    with engine.connect() as conn:
        # Check if user exists
        result = conn.execute(
            text("SELECT id, email, subscription_tier FROM users WHERE email = :email"),
            {"email": EMAIL}
        )
        user = result.fetchone()
        
        if not user:
            print(f"User {EMAIL} not found!")
            return
        
        print(f"Found user: {user}")
        print(f"Current tier: {user[2]}")
        
        # Upgrade to Pro
        conn.execute(
            text("""
                UPDATE users SET 
                    subscription_tier = 'pro',
                    subscription_status = 'active',
                    subscription_started_at = :started,
                    subscription_expires_at = :expires,
                    monthly_generations_limit = -1,
                    monthly_generations_used = 0
                WHERE email = :email
            """),
            {"email": EMAIL, "started": now, "expires": expires_at}
        )
        conn.commit()
        
        print(f"\n✅ User {EMAIL} upgraded to Pro!")
        print(f"   Expires: {expires_at}")

if __name__ == "__main__":
    upgrade_user()
