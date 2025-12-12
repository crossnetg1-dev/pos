# Smart POS - Quick Start Guide

This project includes automation scripts to make it portable between Windows and Linux systems.

## Prerequisites

- **Python 3.8 or higher** must be installed on your system
- Internet connection (for downloading dependencies)

## Quick Start

### On Windows:

1. Open Command Prompt or PowerShell in the project directory
2. Run:
   ```cmd
   python run_windows.py
   ```

### On Linux:

1. Open Terminal in the project directory
2. Run:
   ```bash
   python3 run_linux.py
   ```
   Or make it executable and run directly:
   ```bash
   chmod +x run_linux.py
   ./run_linux.py
   ```

## What the Scripts Do

Both automation scripts perform the following steps automatically:

1. ✅ **Check Python Installation** - Verifies Python 3.8+ is installed
2. ✅ **Create Virtual Environment** - Sets up an isolated Python environment (`venv/`)
3. ✅ **Install Dependencies** - Installs all required packages from `requirements.txt`
4. ✅ **Setup Database** - Runs `setup.py` if database doesn't exist (creates tables, admin user, sample data)
5. ✅ **Start Flask Server** - Launches the application at `http://127.0.0.1:5000`

## Default Login Credentials

After first setup, you can login with:


⚠️ **Important:** Change the default password after first login!

## Manual Setup (Alternative)

If you prefer to set up manually:

### Windows:
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python setup.py
python run.py
```

### Linux:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 setup.py
python3 run.py
```

## Troubleshooting

### "Python not found"
- Make sure Python 3.8+ is installed
- On Windows: Download from [python.org](https://www.python.org/downloads/)
- On Linux: `sudo apt-get install python3` (Debian/Ubuntu)

### "venv module not found" (Linux)
- Install python3-venv: `sudo apt-get install python3-venv`

### "Permission denied" (Linux)
- Make script executable: `chmod +x run_linux.py`

### Port 5000 already in use
- Stop other applications using port 5000
- Or modify `run.py` to use a different port

## Project Structure

```
pos/
├── run_windows.py      # Windows automation script
├── run_linux.py        # Linux automation script
├── run.py              # Flask application entry point
├── setup.py            # Database initialization script
├── requirements.txt    # Python dependencies
├── config.py           # Application configuration
└── app/                # Application code
    ├── models.py       # Database models
    ├── blueprints/     # Route modules
    └── templates/       # HTML templates
```

## Notes

- The virtual environment (`venv/`) is created in the project directory
- Database file is located at `app/pos.db`
- All dependencies are installed in the virtual environment (not system-wide)
- The scripts are idempotent - safe to run multiple times
