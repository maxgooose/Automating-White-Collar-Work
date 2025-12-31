"""
Cross-platform ADB path detection and utilities.
Supports Windows, macOS, and Linux.
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path


def get_adb_path() -> str:
    """
    Detect ADB path across different operating systems.
    
    Search order:
    1. ADB_PATH environment variable (if set)
    2. System PATH (adb/adb.exe)
    3. Standard SDK locations per OS
    4. Common installation directories
    
    Returns:
        str: Path to adb executable
        
    Raises:
        FileNotFoundError: If ADB cannot be found
    """
    # Check environment variable first
    env_path = os.environ.get('ADB_PATH')
    if env_path and os.path.isfile(env_path):
        return env_path
    
    # Check if adb is in system PATH
    adb_in_path = shutil.which('adb')
    if adb_in_path:
        return adb_in_path
    
    # OS-specific default locations
    is_windows = sys.platform == 'win32'
    home = Path.home()
    
    if is_windows:
        # Windows locations
        candidates = [
            home / 'AppData' / 'Local' / 'Android' / 'Sdk' / 'platform-tools' / 'adb.exe',
            Path('C:/Users') / os.environ.get('USERNAME', '') / 'AppData' / 'Local' / 'Android' / 'Sdk' / 'platform-tools' / 'adb.exe',
            Path('C:/Android/sdk/platform-tools/adb.exe'),
            Path('C:/Program Files/Android/sdk/platform-tools/adb.exe'),
            Path('C:/Program Files (x86)/Android/sdk/platform-tools/adb.exe'),
        ]
    elif sys.platform == 'darwin':
        # macOS locations
        candidates = [
            home / 'Library' / 'Android' / 'sdk' / 'platform-tools' / 'adb',
            Path('/usr/local/bin/adb'),
            Path('/opt/homebrew/bin/adb'),
        ]
    else:
        # Linux locations
        candidates = [
            home / 'Android' / 'Sdk' / 'platform-tools' / 'adb',
            home / 'android-sdk' / 'platform-tools' / 'adb',
            Path('/usr/bin/adb'),
            Path('/usr/local/bin/adb'),
            Path('/opt/android-sdk/platform-tools/adb'),
        ]
    
    for path in candidates:
        if path.exists():
            return str(path)
    
    raise FileNotFoundError(
        "ADB not found. Please install Android SDK Platform Tools.\n"
        "Options:\n"
        "  1. Install Android Studio (includes SDK)\n"
        "  2. Download platform-tools: https://developer.android.com/studio/releases/platform-tools\n"
        "  3. Set ADB_PATH environment variable to your adb executable path"
    )


def get_project_root() -> Path:
    """Get the project root directory."""
    # This file is in src/, so parent is project root
    return Path(__file__).parent.parent


def get_data_file_path(filename: str) -> str:
    """
    Get cross-platform path to a data file in project root.
    
    Args:
        filename: Name of the file (e.g., 'receive.txt')
        
    Returns:
        str: Absolute path to the file
    """
    return str(get_project_root() / filename)


def verify_adb_connection() -> dict:
    """
    Verify ADB is working and check for connected devices.
    
    Returns:
        dict: {
            'adb_path': str,
            'connected': bool,
            'devices': list of {'id': str, 'status': str}
        }
    """
    try:
        adb_path = get_adb_path()
    except FileNotFoundError as e:
        return {
            'adb_path': None,
            'connected': False,
            'devices': [],
            'error': str(e)
        }
    
    try:
        result = subprocess.run(
            [adb_path, 'devices'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        devices = []
        for line in result.stdout.split('\n')[1:]:
            if '\t' in line:
                device_id, status = line.split('\t')
                devices.append({'id': device_id.strip(), 'status': status.strip()})
        
        connected = any(d['status'] == 'device' for d in devices)
        
        return {
            'adb_path': adb_path,
            'connected': connected,
            'devices': devices,
            'error': None
        }
        
    except subprocess.TimeoutExpired:
        return {
            'adb_path': adb_path,
            'connected': False,
            'devices': [],
            'error': 'ADB command timed out'
        }
    except Exception as e:
        return {
            'adb_path': adb_path,
            'connected': False,
            'devices': [],
            'error': str(e)
        }


def run_adb_command(*args, timeout: int = 30) -> tuple:
    """
    Run an ADB command with cross-platform support.
    
    Args:
        *args: ADB command arguments (e.g., 'shell', 'input', 'text', 'hello')
        timeout: Command timeout in seconds
        
    Returns:
        tuple: (stdout: str, stderr: str, return_code: int)
    """
    adb_path = get_adb_path()
    cmd = [adb_path] + list(args)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return '', 'Command timed out', 1
    except Exception as e:
        return '', str(e), 1


if __name__ == '__main__':
    # Self-test
    print("ADB Path Detection Test")
    print("=" * 40)
    
    try:
        adb = get_adb_path()
        print(f"ADB found: {adb}")
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    
    print("\nVerifying connection...")
    status = verify_adb_connection()
    
    if status['error']:
        print(f"Error: {status['error']}")
    else:
        print(f"Connected: {status['connected']}")
        if status['devices']:
            print("Devices:")
            for d in status['devices']:
                print(f"  - {d['id']} ({d['status']})")
        else:
            print("No devices connected")
