"""
Transferer Server - Web interface for inventory transfers
Cross-platform compatible (Windows, macOS, Linux).
"""
from flask import Flask, render_template, request, jsonify, Response
from openpyxl import load_workbook
import io
import json
import subprocess
import threading
import queue
import time
import os
import sys
from pathlib import Path

# Setup cross-platform imports
_script_dir = Path(__file__).parent
_project_root = _script_dir.parent

# Add paths for imports to work from any launch location
sys.path.insert(0, str(_script_dir))
sys.path.insert(0, str(_project_root))

from android_controller import FinaleAutomator
from adb_utils import get_data_file_path

app = Flask(__name__)

# Global state for batch execution
automator = None
execution_queue = queue.Queue()
execution_status = {
    'running': False,
    'current': 0,
    'total': 0,
    'current_item': None,
    'message': ''
}
# Store batch data: locations from row 1, all IMEIs from column C
pending_batch = {
    'from_loc': '',
    'to_loc': '',
    'imeis': []
}

# Change Item State specific state
change_state_status = {
    'running': False,
    'current': 0,
    'total': 0,
    'current_item': None,
    'message': ''
}
pending_change_state_items = []
change_state_process = None  # Store subprocess for stop functionality

# Receive specific state
receive_status = {
    'running': False,
    'current': 0,
    'total': 0,
    'current_item': None,
    'message': ''
}
pending_receive_items = []
receive_process = None  # Store subprocess for stop functionality


def get_automator():
    """Get or create the FinaleAutomator instance"""
    global automator
    if automator is None:
        automator = FinaleAutomator()
    return automator


@app.route('/')
def index():
    """Serve the home page with navigation"""
    return render_template('index.html')


@app.route('/transfer')
def transfer_page():
    """Serve the transfer interface"""
    return render_template('transferer.html')


@app.route('/transfer', methods=['POST'])
def transfer():
    """Handle single transfer request (queue only, no execution)"""
    data = request.json
    from_location = data.get('from_location', '')
    to_location = data.get('to_location', '')
    imei = data.get('imei', '')
    
    if not all([from_location, to_location, imei]):
        return jsonify({'success': False, 'message': 'All fields are required'})
    
    print(f"Transfer queued: {from_location} -> {to_location}, IMEI: {imei}")
    
    return jsonify({
        'success': True,
        'message': f'Transfer queued: {imei} from {from_location} to {to_location}'
    })


@app.route('/execute', methods=['POST'])
def execute_single():
    """Execute a single transfer immediately via ADB"""
    global execution_status
    
    if execution_status['running']:
        return jsonify({'success': False, 'message': 'Another execution is in progress'})
    
    data = request.json
    from_location = data.get('from_location', '')
    to_location = data.get('to_location', '')
    imei = data.get('imei', '')
    
    if not all([from_location, to_location, imei]):
        return jsonify({'success': False, 'message': 'All fields are required'})
    
    try:
        execution_status['running'] = True
        execution_status['current'] = 1
        execution_status['total'] = 1
        execution_status['message'] = 'Executing transfer...'
        
        auto = get_automator()
        result = auto.execute_transfer(from_location, to_location, imei)
        
        execution_status['running'] = False
        execution_status['message'] = result['message']
        
        return jsonify(result)
        
    except Exception as e:
        execution_status['running'] = False
        execution_status['message'] = f'Error: {str(e)}'
        return jsonify({'success': False, 'message': str(e)})

# NOTE: Change Item State upload at /change-state/upload writes to receive.txt and runs change_item_state_auto.py
# This /upload route is for Transfer: reads col A=from, B=to, C=imei starting from row 2

# Transfer specific state
transfer_status = {
    'running': False,
    'current': 0,
    'total': 0,
    'current_item': None,
    'message': ''
}
pending_transfer_items = []
transfer_process = None  # Store subprocess for stop functionality


@app.route('/upload', methods=['POST'])
def upload_excel():
    """
    Handle Excel file upload for Transfer.
    
    Excel format:
    - Row 1: Header (ignored)
    - Row 2+: Column A = From sublocation, Column B = To sublocation, Column C = IMEI
    - From/To are read from first data row (row 2) and apply to all IMEIs
    """
    global pending_batch, pending_transfer_items
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'message': 'File must be .xlsx or .xls'})
    
    try:
        # Read Excel file
        wb = load_workbook(filename=io.BytesIO(file.read()))
        ws = wb.active
        
        # Read from row 2 (skip header in row 1)
        # Get from/to from first data row, collect all IMEIs from column C
        from_loc = None
        to_loc = None
        imeis = []
        
        for row in ws.iter_rows(min_row=2, values_only=True):
            # Ensure row has at least 3 columns (A, B, C)
            if not row or len(row) < 3:
                continue
            
            # Get from/to from first data row
            if from_loc is None and row[0] is not None:
                from_loc = str(row[0]).strip()
            if to_loc is None and row[1] is not None:
                to_loc = str(row[1]).strip()
            
            # Collect IMEI from column C
            if row[2] is not None:
                # Handle numeric IMEIs (Excel may read as float)
                imei_val = row[2]
                if isinstance(imei_val, float):
                    imei_val = int(imei_val)
                imei_str = str(imei_val).strip()
                if imei_str:
                    imeis.append(imei_str)
        
        if not from_loc or not to_loc:
            return jsonify({'success': False, 'message': 'Row 2 must have From (A) and To (B) sublocations'})
        
        if not imeis:
            return jsonify({'success': False, 'message': 'No IMEIs found in column C (starting row 2)'})
        
        # Store batch data for execution
        pending_batch = {
            'from_loc': from_loc,
            'to_loc': to_loc,
            'imeis': imeis
        }
        pending_transfer_items = imeis
        
        # Write to transfer_data.txt for transfer_auto.py
        transfer_data_file = get_data_file_path('transfer_data.txt')
        with open(transfer_data_file, 'w') as f:
            f.write(f"{from_loc}\n")
            f.write(f"{to_loc}\n")
            for imei in imeis:
                f.write(f"{imei}\n")
        
        print(f"Loaded transfer batch: {from_loc} -> {to_loc}, {len(imeis)} IMEIs")
        print(f"Saved to {transfer_data_file}")
        for imei in imeis[:5]:
            print(f"  IMEI: {imei}")
        if len(imeis) > 5:
            print(f"  ... and {len(imeis) - 5} more")
        
        # Return in format compatible with frontend
        transfers = [{'from': from_loc, 'to': to_loc, 'imei': imei} for imei in imeis]
        
        return jsonify({
            'success': True,
            'message': f'Loaded {len(imeis)} IMEIs ({from_loc} → {to_loc})',
            'transfers': transfers
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error reading file: {str(e)}'})


def execute_batch_worker(from_loc, to_loc, imeis):
    """Background worker for batch execution - same locations for all IMEIs"""
    global execution_status
    
    auto = get_automator()
    
    def progress_callback(current, total, status, imei):
        execution_status['current'] = current
        execution_status['total'] = total
        execution_status['current_item'] = {'from': from_loc, 'to': to_loc, 'imei': imei}
        execution_status['message'] = f'{status}: {imei}'
    
    result = auto.execute_same_location_batch(from_loc, to_loc, imeis, progress_callback)
    
    execution_status['running'] = False
    execution_status['message'] = result['message']
    execution_status['result'] = result


@app.route('/execute-batch', methods=['POST'])
def execute_batch():
    """Start batch execution of pending transfers"""
    global execution_status, pending_batch
    
    if execution_status['running']:
        return jsonify({'success': False, 'message': 'Another execution is in progress'})
    
    # Use pending batch data
    from_loc = pending_batch.get('from_loc', '')
    to_loc = pending_batch.get('to_loc', '')
    imeis = pending_batch.get('imeis', [])
    
    if not imeis:
        return jsonify({'success': False, 'message': 'No IMEIs to execute'})
    
    if not from_loc or not to_loc:
        return jsonify({'success': False, 'message': 'Missing from/to locations'})
    
    # Reset status
    execution_status = {
        'running': True,
        'current': 0,
        'total': len(imeis),
        'current_item': None,
        'message': 'Starting batch execution...',
        'result': None
    }
    
    # Start background thread
    thread = threading.Thread(target=execute_batch_worker, args=(from_loc, to_loc, imeis))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': f'Started batch: {len(imeis)} IMEIs ({from_loc} → {to_loc})'
    })


def read_progress_file(filename):
    """Read progress from a progress file. Returns (current, total) or None."""
    try:
        progress_file = get_data_file_path(filename)
        if os.path.exists(progress_file):
            with open(progress_file, 'r') as f:
                content = f.read().strip()
                if ',' in content:
                    current, total = content.split(',')
                    return int(current), int(total)
    except:
        pass
    return None


def execute_transfer_batch_worker(total):
    """Background worker for batch Transfer execution - runs transfer_auto.py"""
    global transfer_status, transfer_process
    
    script_path = str(_project_root / 'transfer_auto.py')
    progress_file = 'transfer_progress.txt'
    
    try:
        transfer_status['current'] = 0
        transfer_status['total'] = total
        transfer_status['message'] = 'Starting transfer_auto.py...'
        
        # Start the process (non-blocking)
        transfer_process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(_project_root)
        )
        
        # Poll for progress while process is running
        while transfer_process.poll() is None:
            progress = read_progress_file(progress_file)
            if progress:
                current, _ = progress
                transfer_status['current'] = current
                transfer_status['message'] = f'Processing {current}/{total}...'
            time.sleep(0.3)
        
        # Process finished
        stdout, stderr = transfer_process.communicate()
        
        # Check if it was terminated (stopped by user)
        if transfer_process.returncode == -9 or transfer_process.returncode == -15:
            transfer_status['running'] = False
            transfer_status['message'] = f'Stopped at {transfer_status["current"]}/{total}'
            transfer_status['result'] = {
                'success': False,
                'completed': transfer_status['current'],
                'total': total,
                'message': f'Stopped at {transfer_status["current"]}/{total}'
            }
        elif transfer_process.returncode == 0:
            transfer_status['running'] = False
            transfer_status['current'] = total
            transfer_status['message'] = f'Completed all {total} transfers'
            transfer_status['result'] = {
                'success': True,
                'completed': total,
                'total': total,
                'message': f'Completed all {total} transfers'
            }
        else:
            transfer_status['running'] = False
            transfer_status['message'] = f'Script error: {stderr.decode() if stderr else "Unknown error"}'
            transfer_status['result'] = {
                'success': False,
                'completed': transfer_status['current'],
                'total': total,
                'message': f'Script error: {stderr.decode() if stderr else "Unknown error"}'
            }
            
    except Exception as e:
        transfer_status['running'] = False
        transfer_status['message'] = f'Error: {str(e)}'
        transfer_status['result'] = {
            'success': False,
            'completed': 0,
            'total': total,
            'message': f'Error: {str(e)}'
        }
    finally:
        transfer_process = None


@app.route('/execute-transfer-batch', methods=['POST'])
def execute_transfer_batch():
    """Start batch execution of Transfer operations using transfer_auto.py"""
    global transfer_status, pending_transfer_items
    
    if transfer_status['running']:
        return jsonify({'success': False, 'message': 'Another execution is in progress'})
    
    if not pending_transfer_items:
        return jsonify({'success': False, 'message': 'No items to execute. Upload Excel file first.'})
    
    total = len(pending_transfer_items)
    
    # Reset status
    transfer_status = {
        'running': True,
        'current': 0,
        'total': total,
        'current_item': None,
        'message': 'Starting batch execution...',
        'result': None
    }
    
    # Start background thread to run transfer_auto.py
    thread = threading.Thread(target=execute_transfer_batch_worker, args=(total,))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': f'Started batch: {total} transfers'
    })


@app.route('/transfer-status-stream')
def transfer_status_stream():
    """Server-Sent Events stream for real-time Transfer status updates"""
    def generate():
        last_status = None
        while True:
            current = json.dumps(transfer_status)
            if current != last_status:
                yield f"data: {current}\n\n"
                last_status = current
            time.sleep(0.3)  # Poll every 300ms
            
            # Stop streaming if not running and we've sent the final status
            if not transfer_status['running'] and last_status == current:
                yield f"data: {current}\n\n"
                break
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/stop', methods=['POST'])
def stop_execution():
    """Stop the current batch execution (supports both automator and script-based)"""
    global execution_status, transfer_status, transfer_process
    
    # Check if transfer script is running
    if transfer_status['running'] and transfer_process is not None:
        try:
            transfer_process.terminate()
            transfer_status['message'] = 'Stopping...'
            return jsonify({'success': True, 'message': 'Stop requested'})
        except:
            pass
    
    # Check if automator-based execution is running
    if execution_status['running']:
        auto = get_automator()
        auto.request_stop()
        return jsonify({'success': True, 'message': 'Stop requested'})
    
    return jsonify({'success': False, 'message': 'No execution in progress'})


@app.route('/pause', methods=['POST'])
def pause_execution():
    """Pause the current batch execution"""
    global execution_status
    
    if not execution_status['running']:
        return jsonify({'success': False, 'message': 'No execution in progress'})
    
    auto = get_automator()
    auto.request_pause()
    execution_status['message'] = 'Paused'
    
    return jsonify({'success': True, 'message': 'Paused'})


@app.route('/resume', methods=['POST'])
def resume_execution():
    """Resume a paused batch execution"""
    global execution_status
    
    if not execution_status['running']:
        return jsonify({'success': False, 'message': 'No execution in progress'})
    
    auto = get_automator()
    auto.request_resume()
    execution_status['message'] = 'Resumed'
    
    return jsonify({'success': True, 'message': 'Resumed'})


@app.route('/status')
def get_status():
    """Get current execution status"""
    return jsonify(execution_status)


@app.route('/status-stream')
def status_stream():
    """Server-Sent Events stream for real-time status updates"""
    def generate():
        last_status = None
        while True:
            current = json.dumps(execution_status)
            if current != last_status:
                yield f"data: {current}\n\n"
                last_status = current
            time.sleep(0.3)  # Poll every 300ms
            
            # Stop streaming if not running and we've sent the final status
            if not execution_status['running'] and last_status == current:
                # Send one more to ensure client gets final state
                yield f"data: {current}\n\n"
                break
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/device-status')
def device_status():
    """Check if Android device is connected"""
    try:
        auto = get_automator()
        devices = auto.get_devices()
        connected = any(d['status'] == 'device' for d in devices)
        return jsonify({
            'connected': connected,
            'devices': devices
        })
    except Exception as e:
        return jsonify({
            'connected': False,
            'devices': [],
            'error': str(e)
        })


@app.route('/bulk-stock')
def bulk_stock_page():
    """Serve the Bulk Stock interface"""
    return render_template('bulkStock.html')


# ============================================================
# CHANGE ITEM STATE ROUTES
# ============================================================

@app.route('/change-state')
def change_state_page():
    """Serve the Change Item State interface"""
    return render_template('changeItemState.html')

@app.route('/demo')
def demo_page():
    """Serve the demo page"""
    return render_template('demo.html')


@app.route('/change-state/upload', methods=['POST'])
def upload_change_state_excel():
    """
    Handle Excel file upload for Change Item State.
    
    Excel format:
    - Column A: IMEI (starting from row 2)
    - Column B: New Product ID (starting from row 2)
    - Row 1 is header row (ignored)
    """
    global pending_change_state_items
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'message': 'File must be .xlsx or .xls'})
    
    try:
        # Read Excel file
        wb = load_workbook(filename=io.BytesIO(file.read()))
        ws = wb.active
        
        # Collect IMEI (column A) and Product ID (column B) pairs
        # Starting from row 2 (row 1 is header)
        items = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            # Ensure row has at least 2 columns
            if not row or len(row) < 2:
                continue
            
            # Column A = IMEI, Column B = Product ID
            imei_val = row[0]
            product_id_val = row[1]
            
            # Skip if either value is empty
            if imei_val is None or product_id_val is None:
                continue
            
            # Handle numeric IMEIs (Excel may read as float)
            if isinstance(imei_val, float):
                imei_val = int(imei_val)
            imei_str = str(imei_val).strip()
            product_id_str = str(product_id_val).strip()
            
            if imei_str and product_id_str:
                items.append({
                    'imei': imei_str,
                    'new_product_id': product_id_str
                })
        
        if not items:
            return jsonify({'success': False, 'message': 'No valid IMEI/Product ID pairs found (check columns A and B, starting from row 2)'})
        
        # Store items for execution
        pending_change_state_items = items
        
        # Write to receive.txt in format expected by change_item_state_auto.py
        # Format: imei\nproductID\nimei\nproductID\n...
        receive_file = get_data_file_path('receive.txt')
        with open(receive_file, 'w') as f:
            for item in items:
                f.write(f"{item['imei']}\n")
                f.write(f"{item['new_product_id']}\n")
        
        print(f"Loaded {len(items)} Change Item State pairs and wrote to receive.txt:")
        for item in items[:5]:  # Show first 5
            print(f"  {item['imei']} -> {item['new_product_id']}")
        if len(items) > 5:
            print(f"  ... and {len(items) - 5} more")
        
        return jsonify({
            'success': True,
            'message': f'Loaded {len(items)} IMEI/Product ID pairs (saved to receive.txt)',
            'items': items
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error reading file: {str(e)}'})


@app.route('/change-state/execute', methods=['POST'])
def execute_single_change_state():
    """Execute a single Change Item State operation - writes to receive.txt and runs script"""
    global change_state_status
    
    if change_state_status['running']:
        return jsonify({'success': False, 'message': 'Another execution is in progress'})
    
    data = request.json
    imei = data.get('imei', '')
    new_product_id = data.get('new_product_id', '')
    
    if not imei or not new_product_id:
        return jsonify({'success': False, 'message': 'IMEI and Product ID are required'})
    
    try:
        change_state_status['running'] = True
        change_state_status['current'] = 1
        change_state_status['total'] = 1
        change_state_status['message'] = 'running change_item_state_auto.py'
        
        # Write single item to receive.txt
        receive_file = get_data_file_path('receive.txt')
        with open(receive_file, 'w') as f:
            f.write(f"{imei}\n")
            f.write(f"{new_product_id}\n")
        
        # Run change_item_state_auto.py
        script_path = str(_project_root / 'change_item_state_auto.py')
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            cwd=str(_project_root)
        )
        
        change_state_status['running'] = False
        
        if result.returncode == 0:
            change_state_status['message'] = f'Changed {imei} to {new_product_id}'
            return jsonify({'success': True, 'message': f'Changed {imei} to {new_product_id}'})
        else:
            change_state_status['message'] = f'Script error: {result.stderr}'
            return jsonify({'success': False, 'message': f'Script error: {result.stderr}'})
        
    except Exception as e:
        change_state_status['running'] = False
        change_state_status['message'] = f'Error: {str(e)}'
        return jsonify({'success': False, 'message': str(e)})


def execute_change_state_batch_worker(items):
    """Background worker for batch Change Item State execution - runs change_item_state_auto.py"""
    global change_state_status, change_state_process
    
    total = len(items)
    script_path = str(_project_root / 'change_item_state_auto.py')
    progress_file = 'change_state_progress.txt'
    
    try:
        change_state_status['current'] = 0
        change_state_status['total'] = total
        change_state_status['message'] = 'Starting change_item_state_auto.py...'
        
        # Start the process (non-blocking)
        change_state_process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(_project_root)
        )
        
        # Poll for progress while process is running
        while change_state_process.poll() is None:
            progress = read_progress_file(progress_file)
            if progress:
                current, _ = progress
                change_state_status['current'] = current
                change_state_status['message'] = f'Processing {current}/{total}...'
            time.sleep(0.3)
        
        # Process finished
        stdout, stderr = change_state_process.communicate()
        
        # Check if it was terminated (stopped by user)
        if change_state_process.returncode == -9 or change_state_process.returncode == -15:
            change_state_status['running'] = False
            change_state_status['message'] = f'Stopped at {change_state_status["current"]}/{total}'
            change_state_status['result'] = {
                'success': False,
                'completed': change_state_status['current'],
                'total': total,
                'message': f'Stopped at {change_state_status["current"]}/{total}'
            }
        elif change_state_process.returncode == 0:
            change_state_status['running'] = False
            change_state_status['current'] = total
            change_state_status['message'] = f'Completed all {total} items'
            change_state_status['result'] = {
                'success': True,
                'completed': total,
                'total': total,
                'message': f'Completed all {total} item state changes'
            }
        else:
            change_state_status['running'] = False
            change_state_status['message'] = f'Script error: {stderr.decode() if stderr else "Unknown error"}'
            change_state_status['result'] = {
                'success': False,
                'completed': change_state_status['current'],
                'total': total,
                'message': f'Script error: {stderr.decode() if stderr else "Unknown error"}'
            }
            
    except Exception as e:
        change_state_status['running'] = False
        change_state_status['message'] = f'Error: {str(e)}'
        change_state_status['result'] = {
            'success': False,
            'completed': 0,
            'total': total,
            'message': f'Error: {str(e)}'
        }
    finally:
        change_state_process = None


@app.route('/change-state/execute-batch', methods=['POST'])
def execute_change_state_batch():
    """Start batch execution of Change Item State"""
    global change_state_status, pending_change_state_items
    
    if change_state_status['running']:
        return jsonify({'success': False, 'message': 'Another execution is in progress'})
    
    # Use items from request or pending items
    data = request.json or {}
    items = data.get('items', pending_change_state_items)
    
    if not items:
        return jsonify({'success': False, 'message': 'No items to execute'})
    
    # Reset status
    change_state_status = {
        'running': True,
        'current': 0,
        'total': len(items),
        'current_item': None,
        'message': 'Starting batch execution...',
        'result': None
    }
    
    # Start background thread
    thread = threading.Thread(target=execute_change_state_batch_worker, args=(items,))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': f'Started batch: {len(items)} items'
    })


@app.route('/change-state/stop', methods=['POST'])
def stop_change_state():
    """Stop the current Change Item State batch execution"""
    global change_state_status, change_state_process
    
    if not change_state_status['running']:
        return jsonify({'success': False, 'message': 'No execution in progress'})
    
    # Terminate the subprocess if running
    if change_state_process is not None:
        try:
            change_state_process.terminate()
            change_state_status['message'] = 'Stopping...'
        except:
            pass
    
    return jsonify({'success': True, 'message': 'Stop requested'})


@app.route('/change-state/pause', methods=['POST'])
def pause_change_state():
    """Pause the current Change Item State batch execution"""
    global change_state_status
    
    if not change_state_status['running']:
        return jsonify({'success': False, 'message': 'No execution in progress'})
    
    auto = get_automator()
    auto.request_pause()
    change_state_status['message'] = 'Paused'
    
    return jsonify({'success': True, 'message': 'Paused'})


@app.route('/change-state/resume', methods=['POST'])
def resume_change_state():
    """Resume a paused Change Item State batch execution"""
    global change_state_status
    
    if not change_state_status['running']:
        return jsonify({'success': False, 'message': 'No execution in progress'})
    
    auto = get_automator()
    auto.request_resume()
    change_state_status['message'] = 'Resumed'
    
    return jsonify({'success': True, 'message': 'Resumed'})


@app.route('/change-state/status')
def get_change_state_status():
    """Get current Change Item State execution status"""
    return jsonify(change_state_status)


@app.route('/change-state/status-stream')
def change_state_status_stream():
    """Server-Sent Events stream for real-time Change Item State status updates"""
    def generate():
        last_status = None
        while True:
            current = json.dumps(change_state_status)
            if current != last_status:
                yield f"data: {current}\n\n"
                last_status = current
            time.sleep(0.3)  # Poll every 300ms
            
            # Stop streaming if not running and we've sent the final status
            if not change_state_status['running'] and last_status == current:
                yield f"data: {current}\n\n"
                break
    
    return Response(generate(), mimetype='text/event-stream')


# ============================================================
# RECEIVE ROUTES
# ============================================================

@app.route('/receive')
def receive_page():
    """Serve the Receive interface"""
    return render_template('receive.html')


@app.route('/receive', methods=['POST'])
def execute_single_receive():
    """Execute a single receive operation"""
    data = request.json
    order_id = data.get('order_id', '')
    sublocation = data.get('sublocation', '')
    product_id = data.get('product_id', '')
    imei = data.get('imei', '')
    
    if not all([order_id, sublocation, product_id, imei]):
        return jsonify({'success': False, 'message': 'All fields are required'})
    
    try:
        # For single receive, we can write to receive_data.txt and execute receive_typing.py
        # Format: product name (from product_id), then IMEI
        receive_data_file = get_data_file_path('receive_data.txt')
        with open(receive_data_file, 'w') as f:
            f.write(f"{product_id}\n")
            f.write(f"{imei}\n")
        
        # Execute receive_typing.py in background
        script_path = str(_project_root / 'receive_typing.py')
        subprocess.Popen(
            [sys.executable, script_path],
            cwd=str(_project_root)
        )
        
        return jsonify({
            'success': True,
            'message': f'Received {imei} for {product_id} (executing receive_typing.py)'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/upload-receive', methods=['POST'])
def upload_receive_excel():
    """
    Handle Excel file upload for Receive.
    
    Excel format:
    - Fixed start: D7
    - QTY header: E6
    - Data rows: Starting from row 7
    - Product name: B7+C7 (concatenated)
    - IMEIs: Column D (D7, D8, D9, etc.)
    - Quantity: Column E (E7, E8, etc.)
    - When E7 contains quantity N (e.g., 5), it means:
      - Product name from B7+C7 applies to rows 7 through (7+N-1) = rows 7-11
      - IMEIs are in D7, D8, D9, D10, D11
      - Next item starts when a new quantity appears in column E (e.g., E12)
    
    Returns products for user to assign custom Product IDs before saving.
    """
    global pending_receive_items
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'message': 'File must be .xlsx or .xls'})
    
    try:
        # Read Excel file
        wb = load_workbook(filename=io.BytesIO(file.read()))
        ws = wb.active
        
        # Parse Excel according to specification
        items = []
        row = 7  # Fixed start at row 7
        
        # Get max row
        max_row = ws.max_row
        
        while row <= max_row:
            # Check quantity cell in column E
            qty_cell = ws[f'E{row}'].value
            
            # If quantity cell is empty, we're done
            if qty_cell is None or qty_cell == '':
                break
            
            # Convert quantity to int
            try:
                qty = int(qty_cell)
            except (ValueError, TypeError):
                # If not a valid number, skip this row
                row += 1
                continue
            
            # Get product name from B+C (concatenated)
            b_val = ws[f'B{row}'].value
            c_val = ws[f'C{row}'].value
            product_name = str(b_val or '') + str(c_val or '')
            product_name = product_name.strip()
            
            if not product_name:
                # Skip if no product name
                row += qty
                continue
            
            # Collect IMEIs from column D for the quantity range
            imeis = []
            for i in range(qty):
                imei_cell = ws[f'D{row + i}'].value
                if imei_cell is not None:
                    # Handle numeric IMEIs (Excel may read as float)
                    if isinstance(imei_cell, float):
                        imei_cell = int(imei_cell)
                    imei_str = str(imei_cell).strip()
                    if imei_str:
                        imeis.append(imei_str)
            
            if imeis:
                items.append({
                    'product_name': product_name,
                    'imeis': imeis
                })
            
            # Move to next quantity group
            row += qty
        
        if not items:
            return jsonify({'success': False, 'message': 'No valid items found in Excel file (check format: QTY in column E starting at row 7, IMEIs in column D, product name in B+C)'})
        
        # Store items for later (user needs to confirm product IDs first)
        pending_receive_items = items
        
        total_imeis = sum(len(item['imeis']) for item in items)
        print(f"Loaded {len(items)} products with {total_imeis} IMEIs (awaiting product ID confirmation):")
        for item in items[:3]:
            print(f"  {item['product_name']}: {len(item['imeis'])} IMEIs")
        if len(items) > 3:
            print(f"  ... and {len(items) - 3} more products")
        
        # Return products for user to assign custom Product IDs
        # Do NOT write to receive_data.txt yet - wait for user confirmation
        products_for_mapping = []
        for i, item in enumerate(items):
            products_for_mapping.append({
                'index': i,
                'detected_name': item['product_name'],
                'imei_count': len(item['imeis']),
                'custom_product_id': ''  # User will fill this in
            })
        
        return jsonify({
            'success': True,
            'message': f'Loaded {len(items)} products with {total_imeis} IMEIs',
            'needs_product_mapping': True,
            'products': products_for_mapping,
            'total_imeis': total_imeis
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error reading file: {str(e)}'})


@app.route('/confirm-receive-products', methods=['POST'])
def confirm_receive_products():
    """
    Confirm product ID mappings and save to receive_data.txt.
    
    Expects JSON:
    {
        "products": [
            {"index": 0, "custom_product_id": "IPHONE 14 128GB BLACK"},
            {"index": 1, "custom_product_id": "IPHONE 15 256GB WHITE"},
            ...
        ]
    }
    """
    global pending_receive_items
    
    if not pending_receive_items:
        return jsonify({'success': False, 'message': 'No pending items. Upload Excel file first.'})
    
    data = request.json
    if not data or 'products' not in data:
        return jsonify({'success': False, 'message': 'Missing product mappings'})
    
    product_mappings = data['products']
    
    # Validate all products have a custom_product_id
    for mapping in product_mappings:
        idx = mapping.get('index')
        custom_id = mapping.get('custom_product_id', '').strip()
        
        if idx is None or idx >= len(pending_receive_items):
            return jsonify({'success': False, 'message': f'Invalid product index: {idx}'})
        
        if not custom_id:
            return jsonify({'success': False, 'message': f'Product {idx + 1} is missing a Product ID'})
    
    # Build the final items with user-provided product IDs
    final_items = []
    for mapping in product_mappings:
        idx = mapping['index']
        custom_id = mapping['custom_product_id'].strip()
        original_item = pending_receive_items[idx]
        
        final_items.append({
            'product_name': custom_id,  # Use user's custom product ID
            'imeis': original_item['imeis']
        })
    
    # Write to receive_data.txt with user-provided product IDs
    receive_data_file = get_data_file_path('receive_data.txt')
    with open(receive_data_file, 'w') as f:
        for item in final_items:
            f.write(f"{item['product_name']}\n")
            for imei in item['imeis']:
                f.write(f"{imei}\n")
    
    total_imeis = sum(len(item['imeis']) for item in final_items)
    print(f"Saved {len(final_items)} products with {total_imeis} IMEIs to receive_data.txt:")
    for item in final_items:
        print(f"  {item['product_name']}: {len(item['imeis'])} IMEIs")
    
    # Update pending_receive_items with final product IDs
    pending_receive_items = final_items
    
    # Prepare flattened items list for frontend display
    display_items = []
    for item in final_items:
        for imei in item['imeis']:
            display_items.append({
                'imei': imei,
                'product_name': item['product_name']
            })
    
    return jsonify({
        'success': True,
        'message': f'Saved {len(final_items)} products with {total_imeis} IMEIs',
        'items': display_items
    })


def execute_receive_batch_worker(items):
    """Background worker for batch Receive execution - runs receive_typing.py"""
    global receive_status, receive_process
    
    total = len(items)
    script_path = str(_project_root / 'receive_typing.py')
    progress_file = 'receive_progress.txt'
    
    try:
        receive_status['current'] = 0
        receive_status['total'] = total
        receive_status['message'] = 'Starting receive_typing.py...'
        
        # Start the process (non-blocking)
        receive_process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(_project_root)
        )
        
        # Poll for progress while process is running
        while receive_process.poll() is None:
            progress = read_progress_file(progress_file)
            if progress:
                current, _ = progress
                receive_status['current'] = current
                receive_status['message'] = f'Processing {current}/{total}...'
            time.sleep(0.3)
        
        # Process finished
        stdout, stderr = receive_process.communicate()
        
        # Check if it was terminated (stopped by user)
        if receive_process.returncode == -9 or receive_process.returncode == -15:
            receive_status['running'] = False
            receive_status['message'] = f'Stopped at {receive_status["current"]}/{total}'
            receive_status['result'] = {
                'success': False,
                'completed': receive_status['current'],
                'total': total,
                'message': f'Stopped at {receive_status["current"]}/{total}'
            }
        elif receive_process.returncode == 0:
            receive_status['running'] = False
            receive_status['current'] = total
            receive_status['message'] = f'Completed all {total} items'
            receive_status['result'] = {
                'success': True,
                'completed': total,
                'total': total,
                'message': f'Completed all {total} receive operations'
            }
        else:
            receive_status['running'] = False
            receive_status['message'] = f'Script error: {stderr.decode() if stderr else "Unknown error"}'
            receive_status['result'] = {
                'success': False,
                'completed': receive_status['current'],
                'total': total,
                'message': f'Script error: {stderr.decode() if stderr else "Unknown error"}'
            }
            
    except Exception as e:
        receive_status['running'] = False
        receive_status['message'] = f'Error: {str(e)}'
        receive_status['result'] = {
            'success': False,
            'completed': 0,
            'total': total,
            'message': f'Error: {str(e)}'
        }
    finally:
        receive_process = None


@app.route('/execute-receive-batch', methods=['POST'])
def execute_receive_batch():
    """Start batch execution of Receive operations"""
    global receive_status, pending_receive_items
    
    if receive_status['running']:
        return jsonify({'success': False, 'message': 'Another execution is in progress'})
    
    # Use items from request or pending items
    data = request.json or {}
    items = data.get('items', pending_receive_items)
    sublocation = data.get('sublocation', '').strip()
    
    if not items:
        return jsonify({'success': False, 'message': 'No items to execute'})
    
    if not sublocation:
        return jsonify({'success': False, 'message': 'Sublocation is required'})
    
    # Write sublocation to file for receive_typing.py to read
    sublocation_file = get_data_file_path('receive_sublocation.txt')
    with open(sublocation_file, 'w') as f:
        f.write(sublocation)
    
    print(f"Receive batch: sublocation={sublocation}, {len(items)} items")
    
    # Reset status
    receive_status = {
        'running': True,
        'current': 0,
        'total': len(items),
        'current_item': None,
        'message': 'Starting batch execution...',
        'result': None
    }
    
    # Start background thread to run receive_typing.py
    thread = threading.Thread(target=execute_receive_batch_worker, args=(items,))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': f'Started batch: {len(items)} items to {sublocation}'
    })


@app.route('/receive-status-stream')
def receive_status_stream():
    """Server-Sent Events stream for real-time Receive status updates"""
    def generate():
        last_status = None
        while True:
            current = json.dumps(receive_status)
            if current != last_status:
                yield f"data: {current}\n\n"
                last_status = current
            time.sleep(0.3)  # Poll every 300ms
            
            # Stop streaming if not running and we've sent the final status
            if not receive_status['running'] and last_status == current:
                yield f"data: {current}\n\n"
                break
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/receive-pause', methods=['POST'])
def pause_receive():
    """Pause the current Receive batch execution"""
    global receive_status
    
    if not receive_status['running']:
        return jsonify({'success': False, 'message': 'No execution in progress'})
    
    auto = get_automator()
    auto.request_pause()
    receive_status['message'] = 'Paused'
    
    return jsonify({'success': True, 'message': 'Paused'})


@app.route('/receive-resume', methods=['POST'])
def resume_receive():
    """Resume a paused Receive batch execution"""
    global receive_status
    
    if not receive_status['running']:
        return jsonify({'success': False, 'message': 'No execution in progress'})
    
    auto = get_automator()
    auto.request_resume()
    receive_status['message'] = 'Resumed'
    
    return jsonify({'success': True, 'message': 'Resumed'})


@app.route('/receive-stop', methods=['POST'])
def stop_receive():
    """Stop the current Receive batch execution"""
    global receive_status, receive_process
    
    if not receive_status['running']:
        return jsonify({'success': False, 'message': 'No execution in progress'})
    
    # Terminate the subprocess if running
    if receive_process is not None:
        try:
            receive_process.terminate()
            receive_status['message'] = 'Stopping...'
        except:
            pass
    
    return jsonify({'success': True, 'message': 'Stop requested'})


if __name__ == '__main__':
    print("=" * 50)
    print("TRANSFERER SERVER")
    print("Open http://localhost:5000 in your browser")
    print("=" * 50)
    app.run(debug=False, host='127.0.0.1', port=5000, threaded=True)
