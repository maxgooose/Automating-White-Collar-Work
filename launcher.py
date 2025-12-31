#!/usr/bin/env python3
"""
Finale Inventory Automation - Cross-Platform Launcher
Works on Windows, macOS, and Linux.

Usage:
    python launcher.py           # Start web server
    python launcher.py --check   # Check system requirements
    python launcher.py --install # Install dependencies
"""
import os
import sys
import subprocess
import webbrowser
import time
import argparse
from pathlib import Path


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent


def check_python_version():
    """Check Python version is 3.8+."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"ERROR: Python 3.8+ required. Current: {version.major}.{version.minor}")
        return False
    print(f"Python version: {version.major}.{version.minor}.{version.micro} - OK")
    return True


def check_dependencies():
    """Check if required packages are installed."""
    required = ['flask', 'openpyxl']
    missing = []
    
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"Missing packages: {', '.join(missing)}")
        return False
    
    print("Dependencies: All installed - OK")
    return True


def install_dependencies():
    """Install required dependencies."""
    requirements_file = get_project_root() / 'requirements.txt'
    
    print("Installing dependencies...")
    result = subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '-r', str(requirements_file)],
        capture_output=False
    )
    
    if result.returncode == 0:
        print("Dependencies installed successfully.")
        # Create marker file
        marker = get_project_root() / '.deps_installed'
        marker.touch()
        return True
    else:
        print("ERROR: Failed to install dependencies.")
        return False


def check_adb():
    """Check ADB installation and device connection."""
    sys.path.insert(0, str(get_project_root() / 'src'))
    
    try:
        from adb_utils import verify_adb_connection
        result = verify_adb_connection()
        
        if result.get('error'):
            print(f"ADB: ERROR - {result['error']}")
            return False
        
        print(f"ADB path: {result['adb_path']} - OK")
        
        devices = result.get('devices', [])
        if devices:
            print(f"Connected devices: {len(devices)}")
            for d in devices:
                status = "Ready" if d['status'] == 'device' else d['status']
                print(f"  - {d['id']} ({status})")
        else:
            print("Connected devices: None")
            print("  NOTE: Connect an Android device or start an emulator.")
        
        return True
        
    except Exception as e:
        print(f"ADB: ERROR - {e}")
        return False


def run_system_check():
    """Run full system check."""
    print("=" * 60)
    print(" SYSTEM CHECK")
    print("=" * 60)
    print()
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("ADB Connection", check_adb),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n{name}:")
        print("-" * 40)
        results.append(check_func())
    
    print()
    print("=" * 60)
    if all(results):
        print(" All checks passed. Ready to run.")
    else:
        print(" Some checks failed. See details above.")
    print("=" * 60)
    
    return all(results)


def start_server(open_browser=True):
    """Start the Flask server."""
    project_root = get_project_root()
    server_script = project_root / 'src' / 'transferer_server.py'
    
    print("=" * 60)
    print(" FINALE INVENTORY AUTOMATION")
    print("=" * 60)
    print()
    print(f"Project: {project_root}")
    print()
    
    # Quick dependency check
    if not check_dependencies():
        print()
        print("Installing missing dependencies...")
        if not install_dependencies():
            print("ERROR: Could not install dependencies.")
            print("Run manually: pip install -r requirements.txt")
            sys.exit(1)
        print()
    
    # Quick ADB check
    print("Checking ADB...")
    check_adb()
    print()
    
    print("=" * 60)
    print(" Starting server on http://localhost:5000")
    print(" Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    # Open browser after short delay
    if open_browser:
        def open_browser_delayed():
            time.sleep(1.5)
            webbrowser.open('http://localhost:5000')
        
        import threading
        browser_thread = threading.Thread(target=open_browser_delayed, daemon=True)
        browser_thread.start()
    
    # Start the server
    os.chdir(project_root)
    sys.path.insert(0, str(project_root / 'src'))
    
    try:
        # Import and run Flask app
        from transferer_server import app
        app.run(debug=False, port=5000, threaded=True)
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except Exception as e:
        print(f"\nERROR: {e}")
        print("\nTrying alternative launch method...")
        subprocess.run([sys.executable, str(server_script)])


def main():
    parser = argparse.ArgumentParser(
        description='Finale Inventory Automation Launcher',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python launcher.py           Start the web server
  python launcher.py --check   Check system requirements
  python launcher.py --install Install dependencies only
  python launcher.py --no-browser  Start without opening browser
        """
    )
    
    parser.add_argument('--check', action='store_true',
                        help='Check system requirements')
    parser.add_argument('--install', action='store_true',
                        help='Install dependencies only')
    parser.add_argument('--no-browser', action='store_true',
                        help='Do not open browser automatically')
    
    args = parser.parse_args()
    
    if args.check:
        success = run_system_check()
        sys.exit(0 if success else 1)
    
    if args.install:
        success = install_dependencies()
        sys.exit(0 if success else 1)
    
    # Default: start server
    start_server(open_browser=not args.no_browser)


if __name__ == '__main__':
    main()
