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


if __name__ == '__main__':
    print("=" * 50)
    print("TRANSFERER SERVER")
    print("Open http://localhost:5000 in your browser")
    print("=" * 50)
    app.run(debug=True, port=5000, threaded=True)
