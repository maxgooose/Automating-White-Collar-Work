#!/bin/bash
# ============================================================
# Finale Inventory Automation - Unix Launcher (macOS/Linux)
# ============================================================

set -e

echo "============================================================"
echo " FINALE INVENTORY AUTOMATION"
echo "============================================================"
echo ""

# Change to script directory
cd "$(dirname "$0")"
echo "Working directory: $(pwd)"

# Check for Python 3
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "ERROR: Python not found."
    echo ""
    echo "Please install Python 3.8+:"
    echo "  macOS: brew install python3"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo ""
    exit 1
fi

echo "Python: $($PYTHON --version)"

# Check/create virtual environment
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "No virtual environment found, using system Python."
    echo "To create one, run: $PYTHON -m venv venv"
fi

# Install dependencies if needed
if [ ! -f ".deps_installed" ]; then
    echo ""
    echo "Installing dependencies..."
    $PYTHON -m pip install -r requirements.txt
    touch .deps_installed
    echo "Dependencies installed successfully."
fi

# Check ADB
echo ""
echo "Checking ADB connection..."
$PYTHON -c "from src.adb_utils import verify_adb_connection; r=verify_adb_connection(); print('ADB:', r.get('adb_path', 'NOT FOUND')); print('Devices:', len(r.get('devices', [])))" || {
    echo ""
    echo "WARNING: ADB check failed. Make sure Android SDK is installed."
    echo "See SETUP_AND_LAUNCH.md for installation instructions."
    echo ""
}

# Start the server
echo ""
echo "============================================================"
echo " Starting server on http://localhost:5000"
echo " Press Ctrl+C to stop"
echo "============================================================"
echo ""

$PYTHON src/transferer_server.py
