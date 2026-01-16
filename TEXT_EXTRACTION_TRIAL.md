# Text Extraction Trial and Error - Summary

## Objective
Attempt to extract visible text from Finale Inventory app screens using the fastest method possible (without screenshots).

## Approach
Used Android's `uiautomator dump` command to get UI hierarchy XML and extract text attributes from UI nodes.

## Findings

### Initial Implementation
- Created `extract_all_text()` method in `AndroidController` class
- Used `uiautomator dump` to get UI hierarchy as XML
- Parsed XML to extract `text`, `content-desc`, and `resource-id` attributes
- Created `extract_screen_text.py` script to automate emulator startup, app launch, and text extraction

### Results
- **UI dump successful**: Retrieved XML with 6 nodes in the hierarchy
- **Text extraction failed**: All nodes had empty text attributes
- **Root cause identified**: Finale Inventory app uses `SurfaceView` for custom rendering
  - SurfaceView renders directly to screen buffer, bypassing Android's view hierarchy
  - uiautomator cannot see text rendered in SurfaceView
  - The main display is a SurfaceView with resource-id: `com.finaleinventory.denali:id/display`

### Attempted Solutions

1. **Enhanced Text Extraction**
   - Added checks for multiple text attributes: `text`, `content-desc`, `accessibility-text`, `hint`, `pane-title`, `state-description`, `tooltip`
   - Checked all attributes containing keywords: "text", "label", "desc", "title", "name", "content"
   - Result: No text found in any attribute

2. **Accessibility Services Check**
   - Added `check_accessibility_services()` method
   - Found TalkBack is installed but not enabled
   - Attempted to check if enabling TalkBack would help
   - Result: TalkBack cannot be enabled programmatically (requires manual device setup)
   - Even if enabled, SurfaceView content typically isn't accessible via accessibility services

3. **Alternative Methods**
   - Tried `dumpsys window` to get window content
   - Tried alternative accessibility dump methods
   - Result: No text found through any alternative method

### Node Structure Discovered
The UI hierarchy contains 6 nodes:
1. FrameLayout (root container)
2. LinearLayout (layout container)
3. FrameLayout with `android:id/content` (content container)
4. **SurfaceView** with `com.finaleinventory.denali:id/display` (main display - where all text is rendered)
5. View with `android:id/statusBarBackground` (status bar)
6. View with `android:id/navigationBarBackground` (navigation bar)

### Conclusion
**Text extraction via uiautomator is not possible** for Finale Inventory app due to SurfaceView usage.

**Alternatives:**
1. OCR (screenshot + text recognition) - slower (~2-5 seconds) but can read SurfaceView content
2. Coordinate-based navigation - already implemented in the codebase
3. Manual TalkBack enablement - unlikely to help with SurfaceView, but could be tested

## Files Modified
- `src/android_controller.py` - Added `extract_all_text()`, `check_accessibility_services()`, `get_accessibility_node_info()`, `try_accessibility_dump()`, `get_window_content()`, `try_enable_talkback()` methods
- `extract_screen_text.py` - Created script for automated text extraction testing

## Key Learnings
- SurfaceView apps cannot be automated via uiautomator text extraction
- Node structure is visible but contains no text attributes
- Accessibility services don't help with SurfaceView content
- Coordinate-based navigation remains the only reliable automation method for this app
