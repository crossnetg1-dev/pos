#!/usr/bin/env python3
"""
Windows Setup and Launch Script for Cid-POS

This script automates the entire setup process:
1. Checks for Python installation
2. Creates virtual environment if missing
3. Installs all dependencies
4. Initializes database if needed
5. Starts the Flask server
6. Opens browser automatically
"""

import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path


def print_header():
    """Print welcome header."""
    print("\n" + "="*60)
    print("  Cid-POS System - Windows Setup & Launch")
    print("="*60 + "\n")


def check_python():
    """Check if Python is installed and accessible."""
    print("🔍 Checking Python installation...")
    try:
        result = subprocess.run(
            [sys.executable, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"   ✅ {version}")
            return True
    except Exception as e:
        print(f"   ❌ Error checking Python: {e}")
    
    print("\n❌ Python not found!")
    print("   Please install Python 3.8+ from https://www.python.org/downloads/")
    print("   Make sure to check 'Add Python to PATH' during installation.")
    input("\nPress Enter to exit...")
    return False


def create_venv():
    """Create virtual environment if it doesn't exist."""
    venv_path = Path("venv")
    if venv_path.exists() and (venv_path / "Scripts" / "python.exe").exists():
        print("   ✅ Virtual environment already exists")
        return True
    
    print("📦 Creating virtual environment...")
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", "venv"],
            check=True,
            timeout=60
        )
        print("   ✅ Virtual environment created")
        return True
    except subprocess.CalledProcessError:
        print("   ❌ Failed to create virtual environment")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def get_venv_python():
    """Get the path to venv Python executable."""
    if sys.platform == "win32":
        return Path("venv") / "Scripts" / "python.exe"
    else:
        return Path("venv") / "bin" / "python"


def get_venv_pip():
    """Get the path to venv pip executable."""
    if sys.platform == "win32":
        return Path("venv") / "Scripts" / "pip.exe"
    else:
        return Path("venv") / "bin" / "pip"


def install_dependencies():
    """Install dependencies from requirements.txt."""
    venv_pip = get_venv_pip()
    if not venv_pip.exists():
        print("   ❌ Virtual environment pip not found")
        return False
    
    print("📥 Installing dependencies (this may take a few minutes)...")
    try:
        subprocess.run(
            [str(venv_pip), "install", "-r", "requirements.txt"],
            check=True,
            timeout=300  # 5 minutes timeout
        )
        print("   ✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("   ❌ Failed to install dependencies")
        print("   Please check your internet connection and try again.")
        return False
    except subprocess.TimeoutExpired:
        print("   ❌ Installation timed out")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def check_database():
    """Check if database exists, initialize if needed."""
    db_path = Path("app") / "pos.db"
    if db_path.exists():
        print("   ✅ Database already exists")
        return True
    
    print("🗄️  Initializing database...")
    venv_python = get_venv_python()
    if not venv_python.exists():
        print("   ❌ Virtual environment Python not found")
        return False
    
    try:
        # Run fix_db.py first to ensure schema is correct
        fix_db_path = Path("fix_db.py")
        if fix_db_path.exists():
            subprocess.run(
                [str(venv_python), "fix_db.py"],
                check=True,
                timeout=30
            )
        
        # Run setup.py to initialize database
        setup_path = Path("setup.py")
        if setup_path.exists():
            subprocess.run(
                [str(venv_python), "setup.py"],
                check=True,
                timeout=30
            )
            print("   ✅ Database initialized")
            return True
        else:
            # If setup.py doesn't exist, just create tables
            from app import create_app, db
            app = create_app()
            with app.app_context():
                db.create_all()
            print("   ✅ Database tables created")
            return True
    except Exception as e:
        print(f"   ⚠️  Database initialization warning: {e}")
        print("   The app will try to create tables on first run.")
        return True  # Continue anyway


def open_browser():
    """Open browser after a short delay."""
    print("\n🌐 Opening browser in 3 seconds...")
    time.sleep(3)
    try:
        webbrowser.open("http://127.0.0.1:5000")
        print("   ✅ Browser opened")
    except Exception as e:
        print(f"   ⚠️  Could not open browser automatically: {e}")
        print("   Please manually open: http://127.0.0.1:5000")


def run_server():
    """Start the Flask development server."""
    venv_python = get_venv_python()
    if not venv_python.exists():
        print("   ❌ Virtual environment Python not found")
        return False
    
    print("\n" + "="*60)
    print("  🚀 Starting Cid-POS Server...")
    print("="*60)
    print("\n📍 Server URL: http://127.0.0.1:5000")
    print("⚠️  Press Ctrl+C to stop the server\n")
    
    try:
        # Open browser in background thread
        import threading
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()
        
        # Run the Flask app
        subprocess.run([str(venv_python), "run.py"], check=True)
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
        return True
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        return False


def main():
    """Main setup and launch function."""
    print_header()
    
    # Step 1: Check Python
    if not check_python():
        sys.exit(1)
    
    # Step 2: Create venv
    print("\n📦 Setting up virtual environment...")
    if not create_venv():
        print("\n❌ Setup failed. Please check the errors above.")
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    # Step 3: Install dependencies
    print("\n📥 Installing dependencies...")
    if not install_dependencies():
        print("\n❌ Failed to install dependencies.")
        print("   You can try running manually:")
        print("   venv\\Scripts\\pip install -r requirements.txt")
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    # Step 4: Check database
    print("\n🗄️  Checking database...")
    check_database()
    
    # Step 5: Run server
    print("\n✅ Setup complete! Starting server...\n")
    run_server()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)
