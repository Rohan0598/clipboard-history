"""
Stage 8: Build ClipboardHistory.exe AND the installer.

  pip install pyinstaller
  (one time) install Inno Setup from https://jrsoftware.org/isdl.php
  python build.py

Results:
  dist\\ClipboardHistory\\ClipboardHistory.exe      the app itself
  installer\\ClipboardHistory-Setup.exe             the installer - this is what you run
"""

import glob
import os
import shutil
import subprocess

import PyInstaller.__main__

import db
from icon import make_tray_image

HERE = os.path.dirname(os.path.abspath(__file__))
ICON = os.path.join(HERE, "icon.ico")
ISS = os.path.join(HERE, "installer.iss")


def find_inno_compiler():
    """Look for ISCC.exe (Inno Setup's command-line compiler) in the usual places."""
    on_path = shutil.which("ISCC")
    if on_path:
        return on_path
    roots = [os.environ.get(v, "") for v in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
    patterns = []
    for root in filter(None, roots):
        patterns += [os.path.join(root, "Inno Setup *", "ISCC.exe"),
                     os.path.join(root, "Programs", "Inno Setup *", "ISCC.exe")]
    found = sorted(p for pattern in patterns for p in glob.glob(pattern))
    return found[-1] if found else None  # newest version wins ("Inno Setup 7" sorts after "6")


# 1. Make sure your existing history has moved to AppData before the .exe ever runs.
db.connect().close()
print(f"Database: {db.DB_PATH}")

# 2. Turn the tray drawing into a Windows .ico file (several sizes in one file).
make_tray_image().save(ICON, sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

# 3. Package the Python code into dist\ClipboardHistory with PyInstaller.
PyInstaller.__main__.run([
    os.path.join(HERE, "app.py"),
    "--name", "ClipboardHistory",
    "--icon", ICON,
    "--noconsole",                         # no black terminal window
    "--onedir",                            # a folder: starts faster than one big .exe, and customtkinter recommends it
    "--collect-data", "customtkinter",     # customtkinter's theme files aren't Python code, so list them explicitly
    "--hidden-import", "pystray._win32",   # pystray picks its Windows backend at runtime; PyInstaller can't see that
    "--noconfirm",                         # overwrite the previous build without asking
    "--clean",
])
print("\nApp built:", os.path.join(HERE, "dist", "ClipboardHistory", "ClipboardHistory.exe"))

# 4. Wrap it in an installer with Inno Setup.
iscc = find_inno_compiler()
if not iscc:
    print("\nInno Setup not found, so no installer was made.")
    print("Install it from https://jrsoftware.org/isdl.php, then run build.py again.")
else:
    subprocess.run([iscc, ISS], check=True, cwd=HERE)
    print("\nInstaller built:", os.path.join(HERE, "installer", "ClipboardHistory-Setup.exe"))
