"""
Stage 6: Password safety.

Password managers (Bitwarden, KeePass, KeePassXC, 1Password and others) attach
hidden "tags" to the clipboard when they copy a password. Windows' own Win+V
history reads the same tags. We check for two of them:

  ExcludeClipboardContentFromMonitorProcessing
      If present at all: "clipboard tools, please ignore this copy".

  CanIncludeInClipboardHistory
      Holds a number. 0 means "don't keep this in any clipboard history".

is_private() returns:
  True   the copy is tagged as private -> don't save it
  False  normal copy -> save it
  None   couldn't check right now (another app had the clipboard open) -> try again next time
"""

import struct
import sys

if sys.platform == "win32":
    import win32clipboard

    # Windows gives each named clipboard "format" a number; ask for the numbers of our two tags.
    EXCLUDE = win32clipboard.RegisterClipboardFormat("ExcludeClipboardContentFromMonitorProcessing")
    CAN_HISTORY = win32clipboard.RegisterClipboardFormat("CanIncludeInClipboardHistory")


def is_private():
    if sys.platform != "win32":
        return False  # these tags only exist on Windows

    try:
        # Checking whether a tag exists doesn't need the clipboard to be opened.
        if win32clipboard.IsClipboardFormatAvailable(EXCLUDE):
            return True

        if win32clipboard.IsClipboardFormatAvailable(CAN_HISTORY):
            # This tag holds a value, so we have to open the clipboard to read it.
            win32clipboard.OpenClipboard()
            try:
                data = win32clipboard.GetClipboardData(CAN_HISTORY)
            finally:
                win32clipboard.CloseClipboard()  # ALWAYS close it, or every other app gets stuck
            # The value is a 4-byte number ("DWORD"). 0 means "don't keep in history".
            if len(data) >= 4 and struct.unpack("<I", data[:4])[0] == 0:
                return True

        return False
    except Exception:
        return None  # clipboard busy or unreadable; the watcher will retry
