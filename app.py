"""
Stage 8: The complete background app.

  python app.py       while developing (errors show in the terminal)
  python build.py     to package it as ClipboardHistory.exe

- Watches the clipboard every half second and saves new text.
- Press the HOTKEY anywhere to open the history popup (press again to close it).
- Lives in the system tray (bottom-right, maybe under the ^ arrow):
  left-click opens the history; right-click shows Pause recording,
  Start with Windows, and Quit.
- Skips copies that password managers mark as private (see privacy.py).

Do NOT also run watcher.py - this app already includes it.
"""

import os
import queue
import socket
import sys
import threading
import traceback

import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk
import keyboard
import pystray

import db
import export
from icon import make_tray_image
import popup
import startup
import watcher

# Change this if it clashes with a shortcut you use.
# Examples: "ctrl+alt+h", "ctrl+shift+space", "windows+shift+c"
HOTKEY = "alt+shift+v"

# Any unused port works; it's only used to stop two copies of the app running at once.
LOCK_PORT = 47653


def already_running():
    """
    Only one program can "own" a network port at a time. We grab one at startup;
    if a second copy of the app starts, its grab fails and we know to quit.
    """
    global _lock_socket
    _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _lock_socket.bind(("127.0.0.1", LOCK_PORT))
        return False
    except OSError:
        return True


class App:
    def __init__(self):
        ctk.set_appearance_mode("dark")  # dark only, matching the popup design
        # The root window is never shown. It exists so tkinter's event loop can run,
        # and so popups can open and close without ending the program.
        self.root = ctk.CTk()
        self.root.withdraw()

        self.panel = None
        self.startup_on = startup.is_enabled()
        self.conn = db.connect()
        self.watcher = watcher.Watcher(self.conn, verbose=False)
        self.exporting = False   # True while the Save As window is open (stops a second one opening)
        self.export_dir = None   # the folder you last exported to, so the next Save As starts there

        # IMPORTANT: the hotkey and the tray icon run in their own background threads.
        # tkinter only works safely from the main thread, so those threads never touch
        # the window. They just drop a message in this queue, and the main thread
        # checks the queue every 50ms (see poll_events).
        self.events = queue.Queue()

        keyboard.add_hotkey(HOTKEY, lambda: self.events.put("toggle"))

        self.tray = pystray.Icon(
            "clipboard-history",
            make_tray_image(),
            f"Clipboard History ({HOTKEY})",
            menu=pystray.Menu(
                pystray.MenuItem("Open history", lambda: self.events.put("open"), default=True),
                pystray.MenuItem("Pause recording", lambda: self.events.put("pause"),
                                 checked=lambda item: self.watcher.paused),
                pystray.MenuItem("Start with Windows", lambda: self.events.put("startup"),
                                 checked=lambda item: self.startup_on),
                pystray.MenuItem("Export saved items…", lambda: self.events.put("export")),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", lambda: self.events.put("quit")),
            ),
        )
        # Run the tray icon in its own background thread. daemon=True means this
        # thread won't keep the program alive by itself after we quit.
        threading.Thread(target=self._run_tray, daemon=True).start()

        self.root.after(500, self.poll_clipboard)
        self.root.after(50, self.poll_events)

    def _run_tray(self):
        try:
            self.tray.run(setup=self._tray_ready)
        except Exception:
            print("Tray icon failed to start:")
            traceback.print_exc()

    def _tray_ready(self, icon):
        icon.visible = True
        print("Tray icon is up (on Windows 11 it may be hidden under the ^ arrow).")

    # ---------- loops that run inside tkinter's event loop ----------

    def poll_clipboard(self):
        self.watcher.check()
        self.root.after(500, self.poll_clipboard)  # schedule the next check

    def poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event == "toggle":
                    self.close_panel() if self.panel else self.open_panel()
                elif event == "open":
                    self.open_panel()
                elif event == "pause":
                    self.toggle_pause()
                elif event == "startup":
                    self.toggle_startup()
                elif event == "export":
                    self.export_saved()
                elif event == "quit":
                    self.quit()
                    return
        except queue.Empty:
            pass
        self.root.after(50, self.poll_events)

    # ---------- actions ----------

    def open_panel(self):
        if self.panel:  # already open: just bring it to the front
            self.panel._grab_focus()
            return
        self.panel = popup.Popup(self.root, on_close=self._panel_closed)

    def toggle_pause(self):
        self.watcher.paused = not self.watcher.paused
        paused = self.watcher.paused
        self.tray.icon = make_tray_image(paused)
        self.tray.title = f"Clipboard History ({'PAUSED' if paused else HOTKEY})"

    def toggle_startup(self):
        try:
            startup.disable() if self.startup_on else startup.enable()
        except OSError:
            traceback.print_exc()
        self.startup_on = startup.is_enabled()  # re-read, so the tick shows what's really set
        self.tray.update_menu()

    def export_saved(self):
        """Tray > Export saved items…: ask where to save, then write the Markdown file."""
        if self.exporting:
            return
        rows = db.saved(self.conn)
        if not rows:
            show_message("Nothing to export yet.\n\nStar an item (☆) in the history to save it first.")
            return

        self.exporting = True
        # The real window is hidden, and a Save As window without a visible owner can open
        # behind other programs. So give it a tiny see-through owner that sits on top.
        owner = tk.Toplevel(self.root)
        try:
            owner.overrideredirect(True)
            owner.geometry("1x1+0+0")
            owner.attributes("-alpha", 0.0)
            owner.attributes("-topmost", True)
            owner.update()
            documents = os.path.join(os.path.expanduser("~"), "Documents")
            path = filedialog.asksaveasfilename(
                parent=owner,
                title="Export saved items",
                initialdir=self.export_dir or (documents if os.path.isdir(documents) else os.path.expanduser("~")),
                initialfile=export.default_filename(),
                defaultextension=".md",
                filetypes=[("Markdown file", "*.md"), ("All files", "*.*")],
            )
        finally:
            owner.destroy()
            self.exporting = False
        if not path:  # you pressed Cancel
            return

        try:
            count = export.write(path, rows)
        except OSError as error:
            traceback.print_exc()
            show_message(f"Couldn't save the file:\n\n{error}", error=True)
            return
        self.export_dir = os.path.dirname(path)
        show_message(f"Exported {count} saved item{'' if count == 1 else 's'} to:\n\n{path}")

    def close_panel(self):
        if self.panel:
            self.panel.close()

    def _panel_closed(self):
        self.panel = None

    def quit(self):
        keyboard.unhook_all()
        self.tray.stop()
        self.close_panel()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


LOG_PATH = os.path.join(db.APP_DIR, "app.log")
OLD_LOG_PATH = os.path.join(db.APP_DIR, "app.previous.log")


def show_message(text, error=False):
    """A plain Windows message box. Works even when there is no window or terminal."""
    print(text)
    if sys.platform == "win32":
        import ctypes
        icon = 0x10 if error else 0x40  # red X or blue (i)
        ctypes.windll.user32.MessageBoxW(0, text, "Clipboard History", icon | 0x40000)  # 0x40000 = on top


def send_output_to_log_file():
    """
    A --noconsole .exe has no terminal, so print() output and error messages
    would vanish. Send them to a log file instead:
      C:\\Users\\<you>\\AppData\\Roaming\\ClipboardHistory\\app.log
    The previous run's log is kept as app.previous.log.
    Only call this AFTER already_running() is False, so a second copy can
    never wipe the log of the copy that's really running.
    """
    os.makedirs(db.APP_DIR, exist_ok=True)
    if os.path.exists(LOG_PATH):
        os.replace(LOG_PATH, OLD_LOG_PATH)
    log = open(LOG_PATH, "w", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log


def main():
    no_console = sys.stdout is None  # true for the .exe and for pythonw

    if already_running():
        # Nothing touched yet: no log file opened, no hotkey, no tray icon.
        show_message(
            "Clipboard History is already running.\n\n"
            f"Press {HOTKEY.title()} to open it, or find its icon in the system tray "
            "(bottom-right, maybe under the ^ arrow)."
        )
        return

    if no_console:
        send_output_to_log_file()

    try:
        app = App()
    except Exception:
        traceback.print_exc()
        show_message(
            "Clipboard History couldn't start.\n\n"
            f"{traceback.format_exc(limit=1).strip().splitlines()[-1]}\n\n"
            f"Full details are in:\n{LOG_PATH}",
            error=True,
        )
        return

    print(f"Clipboard History running. Press {HOTKEY} to open. Quit from the tray icon.")
    app.run()


if __name__ == "__main__":
    main()
