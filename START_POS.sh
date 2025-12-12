#!/bin/bash
# Cid-POS System - Linux Launcher
# Double-click or run this file to start the POS system

echo ""
echo "========================================"
echo "  Cid-POS System - Starting..."
echo "========================================"
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed!"
    echo ""
    echo "Please install Python 3.8+ using:"
    echo "  sudo apt-get install python3 python3-pip python3-venv  (Debian/Ubuntu)"
    echo "  sudo yum install python3 python3-pip  (CentOS/RHEL)"
    echo "  sudo pacman -S python python-pip  (Arch)"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Make run_linux.py executable
chmod +x run_linux.py

# Run the setup and launch script
python3 run_linux.py

# Keep window open if there was an error
if [ $? -ne 0 ]; then
    echo ""
    echo "Setup or launch failed. Please check the errors above."
    read -p "Press Enter to exit..."
fi
