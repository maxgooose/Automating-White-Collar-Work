import subprocess
import time

ADB = "/Users/hamza/Library/Android/sdk/platform-tools/adb"

def type_text(text):
    subprocess.run([ADB, "shell", "input", "text", text], capture_output=True)

def press_enter():
    subprocess.run([ADB, "shell", "input", "keyevent", "KEYCODE_ENTER"], capture_output=True)

with open("/Users/hamza/Desktop/Programma Uscita Pulita/previous_state.txt", "r") as f:
    previous_states = [line.strip() for line in f if line.strip()]


with open("/Users/hamza/Desktop/Programma Uscita Pulita/next_state.txt", "r") as f:
    next_states = [line.strip() for line in f if line.strip()]

print(f"Processing {len(previous_states, next_states)} being done")

for i, imei in enumerate(imeis, 1):
    print(f"[{i}/{len(imeis)}] {imei}")
    type_text(imei)
    time.sleep(0.1)
    press_enter()
    time.sleep(0.3)



    



