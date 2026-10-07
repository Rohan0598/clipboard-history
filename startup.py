"""
Stage 8: "Start with Windows" on/off.

Windows runs every program listed in this registry key when you sign in:
  HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
("CURRENT_USER" = only your account, and no admin rights needed.)
You can see the result in Task Manager -> Startup apps.
"""

import os
import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "ClipboardHistory"

if sys.platform == "win32":
    import winreg  # built into Python on Windows


def launch_command():
    """The command Windows should run at sign-in."""
    if getattr(sys, "frozen", False):
        # Running as the packaged .exe: just start the .exe itself.
        return f'"{sys.executable}"'
    # Running from source: use pythonw.exe (no terminal window) + app.py.
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    app = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
    return f'"{pythonw}" "{app}"'


def is_enabled():
    """True only if the entry exists AND points at this copy of the app."""
    if sys.platform != "win32":
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, NAME)
            return value.lower() == launch_command().lower()  # Windows paths ignore case
    except OSError:
        return False  # entry doesn't exist


def enable():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, launch_command())


def disable():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, NAME)
    except OSError:
        pass  # already gone
