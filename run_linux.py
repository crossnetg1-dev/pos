#!/usr/bin/env python3
"""
Linux Automation Script for Smart POS
This script automates the setup and running of the Flask POS application on Linux.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

# Colors for terminal
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(text):
    """Print a formatted header."""
    print(f"\n{BLUE}{BOLD}{'='*60}{RESET}")
    print(f"{BLUE}{BOLD}{text.center(60)}{RESET}")
    print(f"{BLUE}{BOLD}{'='*60}{RESET}\n")

def print_success(text):
    """Print success message."""
    print(f"{GREEN}✅ {text}{RESET}")

def print_warning(text):
    """Print warning message."""
    print(f"{YELLOW}⚠️  {text}{RESET}")

def print_error(text):
    """Print error message."""
    print(f"{RED}❌ {text}{RESET}")

def print_info(text):
    """Print info message."""
    print(f"{BLUE}ℹ️  {text}{RESET}")

def check_python():
    """Check if Python is installed."""
    print_info("Checking Python installation...")
    try:
        version = sys.version_info
        if version.major >= 3 and version.minor >= 8:
            print_success(f"Python {version.major}.{version.minor}.{version.micro} found")
            return True
        else:
            print_error(f"Python 3.8+ required. Found {version.major}.{version.minor}")
            return False
    except Exception as e:
        print_error(f"Error checking Python: {e}")
        return False

def check_venv_module():
    """Check if venv module is available."""
    print_info("Checking venv module...")
    try:
        import venv
        print_success("venv module available")
        return True
    except ImportError:
        print_warning("venv module not found. Attempting to install python3-venv...")
        try:
            # Try to install python3-venv (Debian/Ubuntu)
            subprocess.run(["sudo", "apt-get", "install", "-y", "python3-venv"], check=True)
            print_success("python3-venv installed")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print_error("Please install python3-venv manually:")
            print("  Debian/Ubuntu: sudo apt-get install python3-venv")
            print("  Fedora/RHEL: sudo dnf install python3-venv")
            print("  Arch: sudo pacman -S python-venv")
            return False

def check_virtualenv():
    """Check if virtual environment exists, create if not."""
    venv_path = Path("venv")
    print_info("Checking virtual environment...")
    
    if venv_path.exists() and (venv_path / "bin" / "python3").exists():
        print_success("Virtual environment found")
        return True
    else:
        print_warning("Virtual environment not found. Creating one...")
        try:
            subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
            print_success("Virtual environment created")
            return True
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to create virtual environment: {e}")
            return False

def get_venv_python():
    """Get the path to the virtual environment Python executable."""
    return Path("venv") / "bin" / "python3"

def get_venv_pip():
    """Get the path to the virtual environment pip executable."""
    return Path("venv") / "bin" / "pip3"

def install_dependencies():
    """Install or upgrade dependencies from requirements.txt."""
    print_info("Installing dependencies...")
    venv_pip = get_venv_pip()
    
    if not venv_pip.exists():
        print_error("Virtual environment pip not found")
        return False
    
    try:
        # Upgrade pip first
        print_info("Upgrading pip...")
        subprocess.run([str(venv_pip), "install", "--upgrade", "pip"], check=True)
        
        # Install requirements
        if Path("requirements.txt").exists():
            print_info("Installing packages from requirements.txt...")
            subprocess.run([str(venv_pip), "install", "-r", "requirements.txt"], check=True)
            print_success("Dependencies installed successfully")
            return True
        else:
            print_warning("requirements.txt not found")
            return False
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install dependencies: {e}")
        return False

def run_setup():
    """Run setup.py to initialize the database."""
    print_info("Checking if database setup is needed...")
    venv_python = get_venv_python()
    
    if not venv_python.exists():
        print_error("Virtual environment Python not found")
        return False
    
    db_path = Path("app") / "pos.db"
    
    # Ask user if they want to run setup
    if not db_path.exists():
        print_warning("Database not found. Running setup...")
        try:
            subprocess.run([str(venv_python), "setup.py"], check=True)
            print_success("Database setup completed")
            return True
        except subprocess.CalledProcessError as e:
            print_error(f"Setup failed: {e}")
            return False
    else:
        print_success("Database already exists. Skipping setup.")
        return True

def run_app():
    """Run the Flask application."""
    print_info("Starting Flask application...")
    venv_python = get_venv_python()
    
    if not venv_python.exists():
        print_error("Virtual environment Python not found")
        return False
    
    print_header("Smart POS is starting...")
    print_info("The application will be available at: http://127.0.0.1:5000")
    print_info("Press Ctrl+C to stop the server\n")
    
    try:
        # Set environment variables for Flask
        env = os.environ.copy()
        env["FLASK_APP"] = "run.py"
        env["FLASK_ENV"] = "development"
        
        # Run the Flask app
        subprocess.run([str(venv_python), "run.py"], env=env, check=True)
    except KeyboardInterrupt:
        print_warning("\n\nServer stopped by user")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to start application: {e}")
        return False

def main():
    """Main execution function."""
    print_header("Smart POS - Linux Setup & Run Script")
    
    # Check Python
    if not check_python():
        print_error("Please install Python 3.8 or higher")
        sys.exit(1)
    
    # Check venv module
    if not check_venv_module():
        print_warning("Continuing anyway...")
    
    # Check/Create virtual environment
    if not check_virtualenv():
        print_error("Failed to set up virtual environment")
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print_warning("Some dependencies may not be installed correctly")
        response = input("Continue anyway? (y/n): ").lower()
        if response != 'y':
            sys.exit(1)
    
    # Run setup if needed
    run_setup()
    
    # Run the application
    print_header("Starting Application")
    run_app()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("\n\nScript interrupted by user")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
