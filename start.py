#!/usr/bin/env python3
"""
UmukoziHR Resume Tailor v1.2 - Startup Script
Handles database migration and starts the server
"""
import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description=""):
    """Run a command and handle errors"""
    try:
        print(f"🔄 {description}")
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        print(f"✅ {description} completed!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed!")
        print(f"Error: {e.stderr}")
        return False

def check_env_file():
    """Check if .env file exists"""
    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️  .env file not found!")
        print("📝 Creating .env from template...")
        
        example_file = Path(".env.example")
        if example_file.exists():
            import shutil
            shutil.copy(".env.example", ".env")
            print("✅ .env file created!")
            print("🔧 Please edit .env with your actual configuration values.")
            return True
        else:
            print("❌ .env.example not found either!")
            return False
    return True

def main():
    print("UmukoziHR Resume Tailor v1.2 Startup")
    print("=======================================")
    
    # Check environment file
    if not check_env_file():
        sys.exit(1)
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check if we have the required environment variables
    required_vars = ["DATABASE_URL", "SECRET_KEY", "GEMINI_API_KEY"]
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value or value.startswith("your-"):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"Missing or placeholder environment variables: {missing_vars}")
        print("Please update your .env file with actual values.")
        print("The server will start but some features may not work correctly.")
        
        response = input("\nContinue anyway? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    # Run migration
    print("\nRunning database migration...")
    if not run_command("python migrate.py", "Database migration"):
        print("Tip: Make sure your database is running and your DATABASE_URL is correct.")
        sys.exit(1)
    
    # Start the server
    print("\nStarting FastAPI server...")
    print("Server will be available at: http://localhost:8000")
    print("API docs will be available at: http://localhost:8000/docs")
    print("\nPress Ctrl+C to stop the server")
    
    try:
        # Start uvicorn server
        os.system("uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    except KeyboardInterrupt:
        print("\nServer stopped. Goodbye!")

if __name__ == "__main__":
    # Change to server directory
    server_dir = Path(__file__).parent
    os.chdir(server_dir)
    main()