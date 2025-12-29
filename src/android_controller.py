"""
Android Controller - Base automation utilities for Android via ADB
Uses text-based element finding for reliable navigation.
"""
import subprocess
import time
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path


class AndroidController:
    """Control Android device/emulator via ADB"""
    
    def __init__(self, device_id: str = None):
        self.device_id = device_id
        self.adb_path = os.path.expanduser("~/Library/Android/sdk/platform-tools/adb")
        
    def _run_adb(self, *args) -> str:
        """Run an ADB command and return output"""
        cmd = [self.adb_path]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(args)
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 and result.stderr:
            print(f"ADB Error: {result.stderr}")
        return result.stdout.strip()
    
    def _run_shell(self, *args) -> str:
        """Run a shell command on device"""
        return self._run_adb("shell", *args)
    
    # ========== DEVICE INFO ==========
    
    def get_devices(self) -> list:
        """List connected devices"""
        output = self._run_adb("devices")
        devices = []
        for line in output.split("\n")[1:]:
            if "\t" in line:
                device_id, status = line.split("\t")
                devices.append({"id": device_id, "status": status})
        return devices
    
    def get_screen_size(self) -> tuple:
        """Get screen dimensions (width, height)"""
        output = self._run_shell("wm", "size")
        # Output: "Physical size: 1080x2400"
        size = output.split(": ")[1]
        w, h = size.split("x")
        return int(w), int(h)
    
    # ========== INTERACTIONS ==========
    
    def tap(self, x: int, y: int):
        """Tap at coordinates"""
        self._run_shell("input", "tap", str(x), str(y))
        time.sleep(0.3)
        
    def long_press(self, x: int, y: int, duration_ms: int = 1000):
        """Long press at coordinates"""
        self._run_shell("input", "swipe", str(x), str(y), str(x), str(y), str(duration_ms))
        time.sleep(0.3)
    
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300):
        """Swipe from (x1,y1) to (x2,y2)"""
        self._run_shell("input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))
        time.sleep(0.3)
    
    def scroll_down(self):
        """Scroll down on screen"""
        w, h = self.get_screen_size()
        self.swipe(w // 2, h * 3 // 4, w // 2, h // 4, 500)
        
    def scroll_up(self):
        """Scroll up on screen"""
        w, h = self.get_screen_size()
        self.swipe(w // 2, h // 4, w // 2, h * 3 // 4, 500)
    
    def type_text(self, text: str):
        """Type text (escapes special characters)"""
        # Escape special shell characters
        escaped = text.replace(" ", "%s").replace("'", "\\'").replace('"', '\\"')
        self._run_shell("input", "text", escaped)
        time.sleep(0.2)
    
    def press_key(self, keycode: str):
        """Press a key by keycode (e.g., 'KEYCODE_BACK', 'KEYCODE_HOME')"""
        self._run_shell("input", "keyevent", keycode)
        time.sleep(0.2)
    
    def press_back(self):
        """Press back button"""
        self.press_key("KEYCODE_BACK")
        
    def press_home(self):
        """Press home button"""
        self.press_key("KEYCODE_HOME")
        
    def press_enter(self):
        """Press enter/return"""
        self.press_key("KEYCODE_ENTER")
    
    # ========== APPS ==========
    
    def launch_app(self, package_name: str, activity: str = None):
        """Launch an app by package name"""
        if activity:
            self._run_shell("am", "start", "-n", f"{package_name}/{activity}")
        else:
            self._run_shell("monkey", "-p", package_name, "-c", 
                          "android.intent.category.LAUNCHER", "1")
        time.sleep(2)
        
    def close_app(self, package_name: str):
        """Force stop an app"""
        self._run_shell("am", "force-stop", package_name)
        
    def is_app_installed(self, package_name: str) -> bool:
        """Check if app is installed"""
        output = self._run_shell("pm", "list", "packages", package_name)
        return package_name in output
    
    def get_current_activity(self) -> str:
        """Get the current foreground activity"""
        output = self._run_shell("dumpsys", "activity", "activities", "|", "grep", "mResumedActivity")
        return output
    
    def list_packages(self, filter_text: str = "") -> list:
        """List installed packages"""
        output = self._run_shell("pm", "list", "packages")
        packages = [line.replace("package:", "") for line in output.split("\n") if line]
        if filter_text:
            packages = [p for p in packages if filter_text.lower() in p.lower()]
        return packages
    
    # ========== SCREENSHOTS ==========
    
    def screenshot(self, local_path: str = "screenshot.png") -> str:
        """Take a screenshot and save locally"""
        remote_path = "/sdcard/screenshot.png"
        self._run_shell("screencap", "-p", remote_path)
        self._run_adb("pull", remote_path, local_path)
        self._run_shell("rm", remote_path)
        return local_path
    
    # ========== UI INSPECTION ==========
    
    def dump_ui(self, local_path: str = "ui_dump.xml") -> str:
        """Dump the current UI hierarchy to XML"""
        remote_path = "/sdcard/ui_dump.xml"
        self._run_shell("uiautomator", "dump", remote_path)
        self._run_adb("pull", remote_path, local_path)
        self._run_shell("rm", remote_path)
        return local_path
    
    def get_ui_elements(self) -> str:
        """Get UI dump as string"""
        remote_path = "/sdcard/ui_dump.xml"
        self._run_shell("uiautomator", "dump", remote_path)
        output = self._run_shell("cat", remote_path)
        self._run_shell("rm", remote_path)
        return output
    
    def find_element_by_text(self, text: str, partial: bool = False) -> dict:
        """
        Find an element by its text attribute using UI dump with proper XML parsing.
        
        Args:
            text: The text to search for
            partial: If True, match partial text (contains). If False, exact match.
        
        Returns:
            dict with keys: found, x, y, bounds (or None if not found)
        """
        ui_xml = self.get_ui_elements()
        
        if not ui_xml:
            print("ERROR: UI dump is empty!")
            return {'found': False, 'x': None, 'y': None, 'bounds': None}
        
        try:
            root = ET.fromstring(ui_xml)
        except ET.ParseError as e:
            print(f"ERROR: XML parse error: {e}")
            return {'found': False, 'x': None, 'y': None, 'bounds': None}
        
        # Iterate through ALL nodes in the XML tree
        for elem in root.iter('node'):
            node_text = elem.attrib.get('text', '')
            
            if not node_text:
                continue
            
            # Check if text matches
            matched = False
            if partial:
                # Partial match (case-insensitive)
                matched = text.lower() in node_text.lower()
            else:
                # Exact match OR numbered menu item (e.g., "5. More", "6. Transfer")
                matched = (node_text.lower() == text.lower() or 
                          node_text.lower().endswith('. ' + text.lower()) or
                          node_text.lower() == text.lower().rstrip())
            
            if matched:
                # Extract bounds "[x1,y1][x2,y2]"
                bounds = elem.attrib.get('bounds', '')
                bounds_match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                if bounds_match:
                    x1, y1, x2, y2 = map(int, bounds_match.groups())
                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2
                    print(f"Found '{node_text}' at ({center_x}, {center_y})")
                    return {
                        'found': True,
                        'x': center_x,
                        'y': center_y,
                        'bounds': (x1, y1, x2, y2)
                    }
        
        # Debug: show what texts ARE on screen
        all_texts = [e.attrib.get('text', '') for e in root.iter('node') if e.attrib.get('text')]
        print(f"DEBUG: Element '{text}' not found. Texts on screen: {all_texts}")
        
        return {'found': False, 'x': None, 'y': None, 'bounds': None}
    
    def tap_element_by_text(self, text: str, partial: bool = False, retry: int = 3) -> bool:
        """
        Find and tap an element by its text.
        
        Args:
            text: The text to find
            partial: If True, match partial text
            retry: Number of retries if element not found
        
        Returns:
            True if element was found and tapped, False otherwise
        """
        for attempt in range(retry):
            element = self.find_element_by_text(text, partial)
            if element['found']:
                print(f"Found '{text}' at ({element['x']}, {element['y']})")
                self.tap(element['x'], element['y'])
                return True
            print(f"Element '{text}' not found, attempt {attempt + 1}/{retry}")
            time.sleep(0.5)
        
        print(f"ERROR: Could not find element with text '{text}'")
        return False


class FinaleAutomator(AndroidController):
    """
    Automate Finale Inventory app transfers.
    
    NOTE: This app uses a SurfaceView for custom rendering, so uiautomator
    cannot see text elements. We MUST use fixed screen coordinates.
    
    Screen layout (2400x1080 landscape):
    - Bottom button row at Y ≈ 950
    - Left button (Back/Clear/Prev) at X ≈ 120
    - Center button (Enter) at X ≈ 390
    - Right button (More/Menu/Subloc) at X ≈ 660
    - Menu items are in the middle area, stacked vertically
    """
    
    PACKAGE_NAME = "com.finaleinventory.denali"
    
    # ========== SCREEN COORDINATES (2400x1080 landscape) ==========
    # Bottom button row (main app screens)
    BTN_Y = 950
    BTN_LEFT_X = 120      # Back / Clear / Prev
    BTN_CENTER_X = 390    # Enter
    BTN_RIGHT_X = 660     # More / Menu / Subloc
    
    # Menu items (1-4 visible at a time, vertically stacked)
    MENU_X = 400          # Center of menu items
    MENU_ITEM_1_Y = 185   # Item 1 or 5
    MENU_ITEM_2_Y = 280   # Item 2 or 6
    MENU_ITEM_3_Y = 375   # Item 3 or 7
    MENU_ITEM_4_Y = 470   # Item 4 or 8
    
    # Confirmation dialog buttons (Change item state screen)
    CONFIRM_DIALOG_Y = 580         # Y position for both buttons
    CONFIRM_DIALOG_BACK_X = 245    # Back button (left)
    CONFIRM_DIALOG_CONFIRM_X = 1310  # Confirm button (right)
    
    # ========== TIMING CONSTANTS ==========
    DELAY_AFTER_TAP = 1.0       # Wait after tapping a button
    DELAY_AFTER_TYPE = 0.5      # Wait after typing text
    DELAY_SCREEN_TRANSITION = 1.5  # Wait for screen to change
    DELAY_AFTER_IMEI = 2.0      # Wait after IMEI entry (server sync)
    
    def __init__(self, device_id: str = None):
        super().__init__(device_id)
        self._stop_requested = False
        self._pause_requested = False
        self._current_from = None
        self._current_to = None
    
    def request_stop(self):
        """Request to stop batch execution"""
        self._stop_requested = True
    
    def request_pause(self):
        """Request to pause batch execution"""
        self._pause_requested = True
    
    def request_resume(self):
        """Resume batch execution"""
        self._pause_requested = False
    
    def _wait_if_paused(self):
        """Wait while paused, return True if should continue, False if stopped"""
        while self._pause_requested and not self._stop_requested:
            time.sleep(0.5)
        return not self._stop_requested
    
    # ========== COORDINATE-BASED TAPPING ==========
    # The app uses SurfaceView rendering, so we MUST use coordinates
    
    def tap_more_button(self):
        """Tap the More button (bottom-right)"""
        print(f"Tapping MORE button at ({self.BTN_RIGHT_X}, {self.BTN_Y})")
        self.tap(self.BTN_RIGHT_X, self.BTN_Y)
        time.sleep(self.DELAY_AFTER_TAP)
    
    def tap_enter_button(self):
        """Tap the Enter button (bottom-center)"""
        print(f"Tapping ENTER button at ({self.BTN_CENTER_X}, {self.BTN_Y})")
        self.tap(self.BTN_CENTER_X, self.BTN_Y)
        time.sleep(self.DELAY_AFTER_TAP)
    
    def tap_back_button(self):
        """Tap the Back/Clear/Prev button (bottom-left)"""
        print(f"Tapping BACK button at ({self.BTN_LEFT_X}, {self.BTN_Y})")
        self.tap(self.BTN_LEFT_X, self.BTN_Y)
        time.sleep(self.DELAY_AFTER_TAP)
    
    def tap_menu_item(self, item_num: int):
        """
        Tap a menu item by number (1-4 on current page).
        Item 1 is at top, Item 4 is at bottom.
        """
        y_positions = {
            1: self.MENU_ITEM_1_Y,
            2: self.MENU_ITEM_2_Y,
            3: self.MENU_ITEM_3_Y,
            4: self.MENU_ITEM_4_Y,
        }
        y = y_positions.get(item_num, self.MENU_ITEM_1_Y)
        print(f"Tapping menu item {item_num} at ({self.MENU_X}, {y})")
        self.tap(self.MENU_X, y)
        time.sleep(self.DELAY_AFTER_TAP)
    
    def tap_confirm_button(self):
        """Tap the Confirm button on confirmation dialogs (right side)"""
        print(f"Tapping CONFIRM button at ({self.CONFIRM_DIALOG_CONFIRM_X}, {self.CONFIRM_DIALOG_Y})")
        self.tap(self.CONFIRM_DIALOG_CONFIRM_X, self.CONFIRM_DIALOG_Y)
        time.sleep(self.DELAY_AFTER_TAP)
    
    def tap_confirm_back_button(self):
        """Tap the Back button on confirmation dialogs (left side)"""
        print(f"Tapping BACK button at ({self.CONFIRM_DIALOG_BACK_X}, {self.CONFIRM_DIALOG_Y})")
        self.tap(self.CONFIRM_DIALOG_BACK_X, self.CONFIRM_DIALOG_Y)
        time.sleep(self.DELAY_AFTER_TAP)
    
    def navigate_to_transfer_from(self) -> bool:
        """
        Navigate from Main Menu to Transfer From screen using COORDINATES.
        
        Flow:
        1. Start at Main Menu (items 1-4: Sync, Pick, Receive, Stock change)
        2. Tap MORE button → shows items 5-8
        3. Tap item 2 on this page (which is "6. Transfer")
        4. Tap item 3 ("3. Transfer from")
        """
        print("\n=== NAVIGATING TO TRANSFER FROM ===")
        
        # Step 1: Tap "More" button to go to page 2 (items 5-8)
        print("Step 1: Tap MORE button...")
        self.tap_more_button()
        time.sleep(self.DELAY_SCREEN_TRANSITION)
        
        # Step 2: Tap item 2 on page 2 (this is "6. Transfer")
        print("Step 2: Tap menu item 2 (6. Transfer)...")
        self.tap_menu_item(2)
        time.sleep(self.DELAY_SCREEN_TRANSITION)
        
        # Step 3: Tap item 3 ("3. Transfer from")
        print("Step 3: Tap menu item 3 (3. Transfer from)...")
        self.tap_menu_item(3)
        time.sleep(self.DELAY_SCREEN_TRANSITION)
        
        print("=== NAVIGATION COMPLETE ===\n")
        return True
    
    def enter_sublocation(self, sublocation: str) -> bool:
        """Enter a sublocation name and submit"""
        print(f"Typing sublocation: {sublocation}")
        # Type the sublocation (escape spaces for ADB)
        escaped = sublocation.replace(' ', '%s')
        self._run_shell('input', 'text', escaped)
        time.sleep(self.DELAY_AFTER_TYPE)
        
        # Tap Enter button to submit
        print("Pressing ENTER...")
        self.tap_enter_button()
        time.sleep(self.DELAY_SCREEN_TRANSITION)
        return True
    
    def scan_imei(self, imei: str) -> bool:
        """Enter IMEI and submit"""
        print(f"Typing IMEI: {imei}")
        # Type the IMEI
        self._run_shell('input', 'text', imei)
        time.sleep(self.DELAY_AFTER_TYPE)
        
        # Tap Enter button to submit
        print("Pressing ENTER...")
        self.tap_enter_button()
        time.sleep(self.DELAY_AFTER_IMEI)  # Wait for server sync
        return True
    
    def navigate_back_to_main_menu(self) -> bool:
        """
        Navigate back to main menu from scan screen using COORDINATES.
        
        Flow:
        1. Tap Menu button (right button, same position as More)
        2. Tap item 1 ("1. Exit to main menu")
        """
        print("\n=== NAVIGATING BACK TO MAIN MENU ===")
        
        # Step 1: Tap Menu button (same position as More button)
        print("Step 1: Tap MENU button...")
        self.tap_more_button()  # Menu is in same position as More
        time.sleep(self.DELAY_AFTER_TAP)
        
        # Step 2: Tap item 1 ("1. Exit to main menu")
        print("Step 2: Tap menu item 1 (Exit to main menu)...")
        self.tap_menu_item(1)
        time.sleep(self.DELAY_SCREEN_TRANSITION)
        
        print("=== BACK TO MAIN MENU ===\n")
        return True
    
    def execute_transfer(self, from_loc: str, to_loc: str, imei: str) -> dict:
        """
        Execute a single transfer operation.
        
        Flow (using coordinates):
        1. Start at Main Menu
        2. Tap MORE → shows page 2
        3. Tap item 2 (6. Transfer)
        4. Tap item 3 (3. Transfer from)
        5. Type From location, tap ENTER
        6. Type To location, tap ENTER
        7. Type IMEI, tap ENTER
        8. Tap MENU
        9. Tap item 1 (Exit to main menu)
        """
        try:
            print(f"\n{'='*60}")
            print(f"TRANSFER: {imei}")
            print(f"FROM: {from_loc}")
            print(f"TO: {to_loc}")
            print(f"{'='*60}")
            
            # Navigate to Transfer From screen
            self.navigate_to_transfer_from()
            
            # Enter From sublocation
            self.enter_sublocation(from_loc)
            
            # Enter To sublocation
            self.enter_sublocation(to_loc)
            
            # Enter the IMEI
            self.scan_imei(imei)
            
            # Navigate back to main menu
            self.navigate_back_to_main_menu()
            
            print(f"{'='*60}")
            print("TRANSFER COMPLETE!")
            print(f"{'='*60}\n")
            
            return {
                'success': True,
                'message': f'Transferred {imei} from {from_loc} to {to_loc}'
            }
            
        except Exception as e:
            print(f"ERROR: {str(e)}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def execute_same_location_batch(self, from_loc: str, to_loc: str, imeis: list, progress_callback=None) -> dict:
        """
        Execute batch transfer for multiple IMEIs with same from/to locations.
        Sets up locations once, then enters each IMEI sequentially.
        """
        self._stop_requested = False
        self._pause_requested = False
        
        # Filter out empty/None IMEIs
        valid_imeis = [imei for imei in imeis if imei and str(imei).strip()]
        total = len(valid_imeis)
        completed = 0
        
        if total == 0:
            return {
                'success': False, 'completed': 0, 'total': 0,
                'failed_at': None, 'message': 'No valid IMEIs provided'
            }
        
        try:
            print(f"\n{'='*60}")
            print(f"BATCH TRANSFER: {total} items")
            print(f"FROM: {from_loc}")
            print(f"TO: {to_loc}")
            print(f"{'='*60}")
            
            # Navigate to Transfer From screen ONCE
            self.navigate_to_transfer_from()
            
            # Enter From sublocation ONCE
            self.enter_sublocation(from_loc)
            
            # Enter To sublocation ONCE
            self.enter_sublocation(to_loc)
            
            # Loop through all valid IMEIs
            for i, imei in enumerate(valid_imeis):
                imei_str = str(imei).strip()
                
                if self._stop_requested:
                    self.navigate_back_to_main_menu()
                    return {
                        'success': False, 'completed': completed, 'total': total,
                        'failed_at': None, 'message': f'Stopped after {completed}/{total}'
                    }
                
                if not self._wait_if_paused():
                    self.navigate_back_to_main_menu()
                    return {
                        'success': False, 'completed': completed, 'total': total,
                        'failed_at': None, 'message': f'Stopped after {completed}/{total}'
                    }
                
                if progress_callback:
                    progress_callback(i + 1, total, 'processing', imei_str)
                
                print(f"IMEI {i + 1}/{total}: {imei_str}")
                self.scan_imei(imei_str)
                completed += 1
                
                if progress_callback:
                    progress_callback(i + 1, total, 'completed', imei_str)
            
            # All done - navigate back to main menu
            print("Batch complete!")
            self.navigate_back_to_main_menu()
            
            return {
                'success': True, 'completed': completed, 'total': total,
                'failed_at': None, 'message': f'Completed all {total} transfers'
            }
            
        except Exception as e:
            self.navigate_back_to_main_menu()
            return {
                'success': False, 'completed': completed, 'total': total,
                'failed_at': valid_imeis[completed] if completed < total else None,
                'message': f'Error: {str(e)}'
            }
    
    def reset_state(self):
        """Reset automator state"""
        self._current_from = None
        self._current_to = None
        self._stop_requested = False
        self._pause_requested = False
    
    # ========== CHANGE ITEM STATE ==========
    
    def navigate_to_change_item_state(self) -> bool:
        """
        Navigate from Main Menu to Change Item State screen using COORDINATES.
        
        Flow:
        1. Start at Main Menu (items 1-4: Sync, Pick, Receive, Stock change)
        2. Tap MORE button → shows items 5-8
        3. Tap MORE button → shows items 9-12
        4. Tap item 1 on this page ("9. Change item state")
        """
        print("\n=== NAVIGATING TO CHANGE ITEM STATE ===")
        
        # Step 1: Tap "More" button to go to page 2 (items 5-8)
        print("Step 1: Tap MORE button (page 2)...")
        self.tap_more_button()
        time.sleep(self.DELAY_SCREEN_TRANSITION)
        
        # Step 2: Tap "More" button again to go to page 3 (items 9-12)
        print("Step 2: Tap MORE button (page 3)...")
        self.tap_more_button()
        time.sleep(self.DELAY_SCREEN_TRANSITION)
        
        # Step 3: Tap item 1 on page 3 ("9. Change item state")
        print("Step 3: Tap menu item 1 (9. Change item state)...")
        self.tap_menu_item(1)
        time.sleep(self.DELAY_SCREEN_TRANSITION)
        
        print("=== NAVIGATION COMPLETE ===\n")
        return True
    
    def execute_change_item_state(self, imei: str, new_product_id: str) -> dict:
        """
        Execute a single Change Item State operation.
        
        Flow:
        1. Navigate to Change Item State screen
        2. Type IMEI, press ENTER
        3. Type new Product ID, press ENTER
        4. Tap CONFIRM button
        5. Navigate back to main menu
        """
        try:
            print(f"\n{'='*60}")
            print(f"CHANGE ITEM STATE")
            print(f"IMEI: {imei}")
            print(f"NEW PRODUCT ID: {new_product_id}")
            print(f"{'='*60}")
            
            # Navigate to Change Item State screen
            self.navigate_to_change_item_state()
            
            # Enter IMEI
            print(f"Typing IMEI: {imei}")
            self._run_shell('input', 'text', imei)
            time.sleep(self.DELAY_AFTER_TYPE)
            self.tap_enter_button()
            time.sleep(self.DELAY_SCREEN_TRANSITION)
            
            # Enter new Product ID
            escaped_pid = new_product_id.replace(' ', '%s')
            print(f"Typing Product ID: {new_product_id}")
            self._run_shell('input', 'text', escaped_pid)
            time.sleep(self.DELAY_AFTER_TYPE)
            self.tap_enter_button()
            time.sleep(self.DELAY_SCREEN_TRANSITION)
            
            # Tap Confirm
            self.tap_confirm_button()
            time.sleep(self.DELAY_SCREEN_TRANSITION)
            
            # Navigate back to main menu
            self.navigate_back_to_main_menu()
            
            print(f"{'='*60}")
            print("CHANGE ITEM STATE COMPLETE!")
            print(f"{'='*60}\n")
            
            return {
                'success': True,
                'message': f'Changed {imei} to {new_product_id}'
            }
            
        except Exception as e:
            print(f"ERROR: {str(e)}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def execute_change_item_state_batch(self, items: list, progress_callback=None) -> dict:
        """
        Execute batch Change Item State for multiple IMEI/Product ID pairs.
        
        Args:
            items: List of dicts with 'imei' and 'new_product_id' keys
            progress_callback: Function(current, total, status, imei) for progress updates
        
        Flow:
        1. Navigate to Change Item State screen ONCE
        2. For each item:
           - Type IMEI, ENTER
           - Type Product ID, ENTER
           - Tap CONFIRM
        3. Navigate back to main menu
        """
        self._stop_requested = False
        self._pause_requested = False
        
        # Filter out invalid items
        valid_items = [item for item in items 
                       if item.get('imei') and item.get('new_product_id')]
        total = len(valid_items)
        completed = 0
        
        if total == 0:
            return {
                'success': False, 'completed': 0, 'total': 0,
                'failed_at': None, 'message': 'No valid IMEI/Product ID pairs provided'
            }
        
        try:
            print(f"\n{'='*60}")
            print(f"BATCH CHANGE ITEM STATE: {total} items")
            print(f"{'='*60}")
            
            # Navigate to Change Item State screen ONCE
            self.navigate_to_change_item_state()
            
            # Loop through all items
            for i, item in enumerate(valid_items):
                imei = str(item['imei']).strip()
                new_product_id = str(item['new_product_id']).strip()
                
                if self._stop_requested:
                    self.navigate_back_to_main_menu()
                    return {
                        'success': False, 'completed': completed, 'total': total,
                        'failed_at': item, 'message': f'Stopped after {completed}/{total}'
                    }
                
                if not self._wait_if_paused():
                    self.navigate_back_to_main_menu()
                    return {
                        'success': False, 'completed': completed, 'total': total,
                        'failed_at': item, 'message': f'Stopped after {completed}/{total}'
                    }
                
                if progress_callback:
                    progress_callback(i + 1, total, 'processing', imei)
                
                print(f"\n[{i + 1}/{total}] {imei} -> {new_product_id}")
                
                # Type IMEI and press ENTER
                self._run_shell('input', 'text', imei)
                time.sleep(self.DELAY_AFTER_TYPE)
                self.tap_enter_button()
                time.sleep(self.DELAY_SCREEN_TRANSITION)
                
                # Type Product ID and press ENTER
                escaped_pid = new_product_id.replace(' ', '%s')
                self._run_shell('input', 'text', escaped_pid)
                time.sleep(self.DELAY_AFTER_TYPE)
                self.tap_enter_button()
                time.sleep(self.DELAY_SCREEN_TRANSITION)
                
                # Tap Confirm
                self.tap_confirm_button()
                time.sleep(self.DELAY_AFTER_TAP)
                
                completed += 1
                
                if progress_callback:
                    progress_callback(i + 1, total, 'completed', imei)
            
            # All done - navigate back to main menu
            print("\nBatch complete!")
            self.navigate_back_to_main_menu()
            
            return {
                'success': True, 'completed': completed, 'total': total,
                'failed_at': None, 'message': f'Completed all {total} item state changes'
            }
            
        except Exception as e:
            self.navigate_back_to_main_menu()
            current_item = valid_items[completed] if completed < total else None
            return {
                'success': False, 'completed': completed, 'total': total,
                'failed_at': current_item,
                'message': f'Error: {str(e)}'
            }


# Quick test
if __name__ == "__main__":
    controller = AndroidController()
    
    print("Connected devices:")
    for device in controller.get_devices():
        print(f"  - {device['id']} ({device['status']})")
    
    print(f"\nScreen size: {controller.get_screen_size()}")
    
    print("\nSearching for Finale Inventory...")
    packages = controller.list_packages("finale")
    if packages:
        print(f"Found: {packages}")
    else:
        print("Finale Inventory not installed yet")

