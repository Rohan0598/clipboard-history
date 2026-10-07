"""
Stage 6 test helper: copies fake passwords the same way a password manager does.

  python test_private_copy.py

Run it while app.py is running. Neither fake password should show up in the popup.
(Windows' own Win+V history should skip them too - it reads the same tags.)
"""

import struct
import time

import win32clipboard

import privacy


def copy_tagged(text, tag_format, tag_value):
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        win32clipboard.SetClipboardData(tag_format, tag_value)
    finally:
        win32clipboard.CloseClipboard()


print("1) Copying 'FAKE-PASSWORD-one' tagged 'ExcludeClipboardContentFromMonitorProcessing'")
copy_tagged("FAKE-PASSWORD-one", privacy.EXCLUDE, b"")
print("   is_private() says:", privacy.is_private())
time.sleep(1.5)  # give the app time to notice (it checks every 0.5s)

print("2) Copying 'FAKE-PASSWORD-two' tagged 'CanIncludeInClipboardHistory = 0'")
copy_tagged("FAKE-PASSWORD-two", privacy.CAN_HISTORY, struct.pack("<I", 0))
print("   is_private() says:", privacy.is_private())
time.sleep(1.5)

print("\nNow press Alt+Shift+V. Neither FAKE-PASSWORD should be in the list.")
