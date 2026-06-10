#!/usr/bin/env python3
"""
Tests for the device lock, resume-from-progress trimming, and /active-batch.
Run directly (no pytest needed):

    python tests/test_server_logic.py

Safe by design: the only batch actually launched runs against a missing data
file, so the worker subprocess exits before it ever touches ADB.
"""
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

import transferer_server as srv
from adb_utils import get_data_file_path, PRODUCT_MARKER

PASS = 0


def ok(name, condition, detail=""):
    global PASS
    assert condition, f"FAIL: {name} {detail}"
    PASS += 1
    print(f"  ok - {name}")


DATA_FILES = [
    'transfer_data.txt', 'transfer_progress.txt',
    'pick_data.txt', 'pick_progress.txt',
    'receive_data.txt', 'receive_progress.txt', 'receive_sublocation.txt',
    'receive.txt', 'change_state_progress.txt', 'receive_skipped.txt',
]


@contextmanager
def sandboxed_data_files():
    """Back up the real project-root data files, restore them afterwards."""
    backups = {}
    for name in DATA_FILES:
        path = get_data_file_path(name)
        if os.path.exists(path):
            with open(path, 'r') as f:
                backups[name] = f.read()
            os.remove(path)
    try:
        yield
    finally:
        for name in DATA_FILES:
            path = get_data_file_path(name)
            if name in backups:
                with open(path, 'w') as f:
                    f.write(backups[name])
            elif os.path.exists(path):
                os.remove(path)


def write(name, content):
    with open(get_data_file_path(name), 'w') as f:
        f.write(content)


def clean_data_files():
    """Remove all flow data files so no test inherits another's fixtures.

    CRITICAL for the worker test: if a receive_data.txt leaks in, the spawned
    receive_typing.py would actually type into a connected device.
    """
    for name in DATA_FILES:
        path = get_data_file_path(name)
        if os.path.exists(path):
            os.remove(path)


def test_device_lock():
    print("Device lock:")
    srv.force_release_device()
    ok("acquire when free", srv.try_acquire_device('receive') is None)
    ok("second flow rejected with owner", srv.try_acquire_device('transfer') == 'receive')
    ok("same flow also rejected (no re-entry)", srv.try_acquire_device('receive') == 'receive')
    srv.release_device('transfer')
    ok("release by non-owner is a no-op", srv.try_acquire_device('pick') == 'receive')
    srv.release_device('receive')
    ok("release by owner frees it", srv.try_acquire_device('pick') is None)
    srv.force_release_device()
    ok("force release frees it", srv.try_acquire_device('transfer') is None)
    srv.force_release_device()


def test_resume_transfer():
    print("Resume trim - transfer:")
    clean_data_files()
    write('transfer_data.txt', "LOC-A\nLOC-B\n111\n222\n333\n444\n")
    write('transfer_progress.txt', "2,4")
    r = srv.compute_resume_remainder('transfer')
    ok("trims completed IMEIs, keeps header",
       r and r['content'] == "LOC-A\nLOC-B\n333\n444\n", f"got {r}")
    ok("done/remaining", r['done'] == 2 and r['remaining'] == 2)

    write('transfer_progress.txt', "0,4")
    ok("done=0 -> no resume", srv.compute_resume_remainder('transfer') is None)
    write('transfer_progress.txt', "4,4")
    ok("finished -> no resume", srv.compute_resume_remainder('transfer') is None)
    write('transfer_progress.txt', "2,9")
    ok("progress/file mismatch -> no resume", srv.compute_resume_remainder('transfer') is None)


def test_resume_pick():
    print("Resume trim - pick:")
    clean_data_files()
    write('pick_data.txt', "111\n\n222\n333\n")
    write('pick_progress.txt', "2,4")
    r = srv.compute_resume_remainder('pick')
    ok("keeps meaningful empty lines", r and r['content'] == "222\n333\n", f"got {r}")
    write('pick_progress.txt', "1,4")
    r = srv.compute_resume_remainder('pick')
    ok("empty line can lead the remainder", r and r['content'] == "\n222\n333\n", f"got {r}")


def test_resume_receive():
    print("Resume trim - receive:")
    clean_data_files()
    content = (
        f"{PRODUCT_MARKER}PIXEL 8 128GB\n"
        "111\n222\n"
        f"{PRODUCT_MARKER}IPAD MINI 4\n"
        "333\n"
    )
    write('receive_data.txt', content)
    write('receive_progress.txt', "2,5")  # stopped mid-group of PIXEL 8
    r = srv.compute_resume_remainder('receive')
    expected = (
        f"{PRODUCT_MARKER}PIXEL 8 128GB\n"
        "222\n"
        f"{PRODUCT_MARKER}IPAD MINI 4\n"
        "333\n"
    )
    ok("mid-group resume re-prepends the product marker",
       r and r['content'] == expected, f"got {r}")
    ok("remaining counts the re-typed product line", r['remaining'] == 4)

    write('receive_progress.txt', "3,5")  # stopped exactly at a product boundary
    r = srv.compute_resume_remainder('receive')
    ok("boundary resume starts at next product",
       r and r['content'] == f"{PRODUCT_MARKER}IPAD MINI 4\n333\n", f"got {r}")

    write('receive_data.txt', "IPAD MINI 4\n111\n222\n333\n444\n")  # legacy, no markers
    write('receive_progress.txt', "2,5")
    ok("legacy unmarked file -> no resume (full run fallback)",
       srv.compute_resume_remainder('receive') is None)


def test_resume_change_state():
    print("Resume trim - change_state:")
    clean_data_files()
    write('receive.txt', "111\nPID-A\n222\nPID-B\n333\nPID-C\n")
    write('change_state_progress.txt', "1,3")
    r = srv.compute_resume_remainder('change_state')
    ok("trims completed pairs", r and r['content'] == "222\nPID-B\n333\nPID-C\n", f"got {r}")
    ok("pair counts", r['done'] == 1 and r['remaining'] == 2)


def test_active_batch_and_worker_release():
    print("/active-batch + lock release by worker:")
    client = srv.app.test_client()

    # Safety gate: with no data file, the spawned script exits on its
    # data-file check before any ADB command can reach a device.
    clean_data_files()
    ok("no receive data file before worker test",
       not os.path.exists(get_data_file_path('receive_data.txt')))

    srv.force_release_device()
    data = client.get('/active-batch').get_json()
    ok("idle: no flow", data['flow'] is None and data['status'] is None)

    # Simulate another flow holding the device -> execute endpoints reject
    srv.try_acquire_device('transfer')
    resp = client.post('/execute-receive-batch', json={
        'items': [{'imei': '111'}], 'sublocation': 'X'
    }).get_json()
    ok("busy rejection names the owner", not resp['success'] and 'Transfer' in resp['message'],
       f"got {resp}")
    data = client.get('/active-batch').get_json()
    ok("active-batch reports owner", data['flow'] == 'transfer')
    srv.force_release_device()

    # Real worker run with a MISSING data file: the script exits on the
    # data-file check before touching ADB; the worker must release the lock.
    resp = client.post('/execute-receive-batch', json={
        'items': [{'imei': '111'}], 'sublocation': 'TEST-SUBLOC'
    }).get_json()
    ok("receive batch accepted", resp['success'], f"got {resp}")

    # While the worker is booting the (doomed) script, other flows are locked out
    resp2 = client.post('/execute-pick-batch', json={}).get_json()
    ok("pick rejected while receive runs",
       not resp2['success'] and 'Receive' in resp2['message'], f"got {resp2}")

    # Wait for the script to die and the worker to clean up. The worker's
    # finally block stops the error detector first (joins its thread, up to
    # ~2s), so poll for the lock release rather than sleeping a fixed time.
    deadline = time.time() + 20
    while time.time() < deadline and srv.receive_status['running']:
        time.sleep(0.2)
    ok("receive worker finished", not srv.receive_status['running'])
    while time.time() < deadline and srv.device_owner is not None:
        time.sleep(0.2)
    data = client.get('/active-batch').get_json()
    ok("lock released after worker death", data['flow'] is None, f"got {data}")
    ok("missing data file surfaced as script error",
       'data file not found' in (srv.receive_status.get('message') or '').lower(),
       f"got {srv.receive_status.get('message')!r}")


if __name__ == "__main__":
    with sandboxed_data_files():
        test_device_lock()
        test_resume_transfer()
        test_resume_pick()
        test_resume_receive()
        test_resume_change_state()
        test_active_batch_and_worker_release()
    print(f"\nALL {PASS} CHECKS PASSED")
