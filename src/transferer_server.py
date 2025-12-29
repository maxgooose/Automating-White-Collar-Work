"""
Transferer Server - Web interface for inventory transfers
"""
from flask import Flask, render_template, request, jsonify, Response
from openpyxl import load_workbook
import io
import json
import threading
import queue
import time

from android_controller import FinaleAutomator

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


def get_automator():
    """Get or create the FinaleAutomator instance"""
    global automator
    if automator is None:
        automator = FinaleAutomator()
    return automator


@app.route('/')
def index():
    """Serve the main transfer interface"""
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


# ============================================================
# CHANGE ITEM STATE ROUTES
# ============================================================

@app.route('/change-state')
def change_state_page():
    """Serve the Change Item State interface"""
    return render_template('changeItemState.html')


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
        receive_file = '/Users/hamza/Desktop/Programma Uscita Pulita/receive.txt'
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
    import subprocess
    
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
        change_state_status['message'] = 'Executing change item state...'
        
        # Write single item to receive.txt
        receive_file = '/Users/hamza/Desktop/Programma Uscita Pulita/receive.txt'
        with open(receive_file, 'w') as f:
            f.write(f"{imei}\n")
            f.write(f"{new_product_id}\n")
        
        # Run change_item_state_auto.py
        script_path = '/Users/hamza/Desktop/Programma Uscita Pulita/change_item_state_auto.py'
        result = subprocess.run(
            ['python3', script_path],
            capture_output=True,
            text=True,
            cwd='/Users/hamza/Desktop/Programma Uscita Pulita'
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
    import subprocess
    
    total = len(items)
    script_path = '/Users/hamza/Desktop/Programma Uscita Pulita/change_item_state_auto.py'
    
    try:
        change_state_status['current'] = 0
        change_state_status['total'] = total
        change_state_status['message'] = 'Starting change_item_state_auto.py...'
        
        # Run the automation script
        result = subprocess.run(
            ['python3', script_path],
            capture_output=True,
            text=True,
            cwd='/Users/hamza/Desktop/Programma Uscita Pulita'
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


if __name__ == '__main__':
    print("=" * 50)
    print("TRANSFERER SERVER")
    print("Open http://localhost:5000 in your browser")
    print("=" * 50)
    app.run(debug=True, port=5000, threaded=True)
