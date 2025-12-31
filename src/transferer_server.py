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

# Receive specific state
receive_status = {
    'running': False,
    'current': 0,
    'total': 0,
    'current_item': None,
    'message': ''
}
pending_receive_items = []


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
# This /upload route is for Transfer: reads col A,B,C = from, to, imei



@app.route('/upload', methods=['POST'])
def upload_excel():
    """Handle Excel file upload - reads from/to from row 1, IMEIs from column C"""
    global pending_batch
    
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
        
        # Read from/to locations from first row only
        first_row = None
        for row in ws.iter_rows(min_row=1, max_row=1, values_only=True):
            first_row = row
            break
        
        if not first_row or not first_row[0] or not first_row[1]:
            return jsonify({'success': False, 'message': 'First row must have From and To locations'})
        
        from_loc = str(first_row[0]).strip()
        to_loc = str(first_row[1]).strip()
        
        # Collect all IMEIs from column C (handle numeric values from Excel)
        imeis = []
        for row in ws.iter_rows(min_row=1, values_only=True):
            # Ensure row has at least 3 columns (A, B, C)
            if not row or len(row) < 3:
                continue
            if row[2] is not None:
                # Handle numeric IMEIs (Excel may read as float)
                imei_val = row[2]
                if isinstance(imei_val, float):
                    imei_val = int(imei_val)
                imei_str = str(imei_val).strip()
                if imei_str:
                    imeis.append(imei_str)
        
        if not imeis:
            return jsonify({'success': False, 'message': 'No IMEIs found in column C'})
        
        # Store batch data for execution
        pending_batch = {
            'from_loc': from_loc,
            'to_loc': to_loc,
            'imeis': imeis
        }
        
        print(f"Loaded batch: {from_loc} -> {to_loc}, {len(imeis)} IMEIs")
        for imei in imeis:
            print(f"  IMEI: {imei}")
        
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


@app.route('/stop', methods=['POST'])
def stop_execution():
    """Stop the current batch execution"""
    global execution_status
    
    if not execution_status['running']:
        return jsonify({'success': False, 'message': 'No execution in progress'})
    
    auto = get_automator()
    auto.request_stop()
    
    return jsonify({'success': True, 'message': 'Stop requested'})


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
    global change_state_status
    
    total = len(items)
    script_path = str(_project_root / 'change_item_state_auto.py')
    
    try:
        change_state_status['current'] = 0
        change_state_status['total'] = total
        change_state_status['message'] = 'Starting change_item_state_auto.py...'
        
        # Run the automation script
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            cwd=str(_project_root)
        )
        
        if result.returncode == 0:
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
            change_state_status['message'] = f'Script error: {result.stderr}'
            change_state_status['result'] = {
                'success': False,
                'completed': 0,
                'total': total,
                'message': f'Script error: {result.stderr}'
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
    global change_state_status
    
    if not change_state_status['running']:
        return jsonify({'success': False, 'message': 'No execution in progress'})
    
    auto = get_automator()
    auto.request_stop()
    
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
        
        # Store items for execution
        pending_receive_items = items
        
        # Write to receive_data.txt in format expected by receive_typing.py
        # Format: Product name on one line, followed by IMEIs (one per line)
        receive_data_file = get_data_file_path('receive_data.txt')
        with open(receive_data_file, 'w') as f:
            for item in items:
                f.write(f"{item['product_name']}\n")
                for imei in item['imeis']:
                    f.write(f"{imei}\n")
        
        print(f"Loaded {len(items)} Receive items and wrote to receive_data.txt:")
        total_imeis = sum(len(item['imeis']) for item in items)
        print(f"  Total: {len(items)} products, {total_imeis} IMEIs")
        for item in items[:3]:  # Show first 3
            print(f"  {item['product_name']}: {len(item['imeis'])} IMEIs")
        if len(items) > 3:
            print(f"  ... and {len(items) - 3} more products")
        
        # Execute receive_typing.py in background
        # Currently commented out - no execution needed until user presses receive all
        # script_path = str(_project_root / 'receive_typing.py')
        # subprocess.Popen([sys.executable, script_path], cwd=str(_project_root))
        
        # Prepare items list for frontend (flatten for display)
        display_items = []
        for item in items:
            for imei in item['imeis']:
                display_items.append({
                    'imei': imei,
                    'product_name': item['product_name']
                })
        
        # Extract order metadata if available (from first row or other location)
        # For now, return empty strings - can be enhanced later
        return jsonify({
            'success': True,
            'message': f'Loaded {len(items)} products with {total_imeis} IMEIs (saved to receive_data.txt, executing receive_typing.py)',
            'items': display_items,
            'order_id': '',
            'sublocation': '',
            'product_id': ''
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error reading file: {str(e)}'})


@app.route('/execute-receive-batch', methods=['POST'])
def execute_receive_batch():
    """Start batch execution of Receive operations"""
    global receive_status, pending_receive_items
    
    if receive_status['running']:
        return jsonify({'success': False, 'message': 'Another execution is in progress'})
    
    # Use items from request or pending items
    data = request.json or {}
    items = data.get('items', pending_receive_items)
    
    if not items:
        return jsonify({'success': False, 'message': 'No items to execute'})
    
    # For receive batch, we already wrote to receive_data.txt and executed receive_typing.py
    # So we just need to track the status
    receive_status = {
        'running': True,
        'current': 0,
        'total': len(items),
        'current_item': None,
        'message': 'Processing receive batch...',
        'result': None
    }
    
    # The actual execution is handled by receive_typing.py which is already running
    # We'll update status as we can track it
    
    return jsonify({
        'success': True,
        'message': f'Started batch: {len(items)} items'
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
    global receive_status
    
    if not receive_status['running']:
        return jsonify({'success': False, 'message': 'No execution in progress'})
    
    auto = get_automator()
    auto.request_stop()
    
    return jsonify({'success': True, 'message': 'Stop requested'})


if __name__ == '__main__':
    print("=" * 50)
    print("TRANSFERER SERVER")
    print("Open http://localhost:5000 in your browser")
    print("=" * 50)
    app.run(debug=True, port=5000, threaded=True)
