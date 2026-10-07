"""
Stage 6: Clipboard watcher (now skips passwords, and can be paused).

The Watcher class does one check each time check() is called. app.py calls it
every half second from inside the window's event loop. You can still run this
file alone to see what gets saved:
  python watcher.py
"""

import time
import pyperclip

import db
import privacy

CHECK_EVERY = 0.5        # seconds between clipboard checks
CLEANUP_EVERY = 10 * 60  # run the 24-hour cleanup every 10 minutes


def preview(text, limit=60):
    """Squash text onto one line and cut it short, so long copies print neatly."""
    one_line = " ".join(text.split())
    return one_line if len(one_line) <= limit else one_line[:limit] + "..."


class Watcher:
    def __init__(self, conn, verbose=True):
        self.conn = conn
        self.verbose = verbose  # print what happens? (off inside the background app)
        self.last = None        # None, so whatever is on the clipboard at start gets saved
        self.last_cleanup = 0   # 0, so the first check() also runs a cleanup
        self.paused = False     # True = look but don't save (tray menu "Pause recording")

    def log(self, message):
        if self.verbose:
            print(f"[{time.strftime('%H:%M:%S')}] {message}")

    def check(self):
        """Look at the clipboard once; save it if it changed. Also cleans up now and then."""
        try:
            current = pyperclip.paste()
        except pyperclip.PyperclipException:
            return  # another app is holding the clipboard for a moment; try next time
        except Exception:
            return  # never let one bad read kill the background app

        # New text, and not just empty/whitespace (copying an image gives "")
        if current != self.last and current.strip():
            if self.paused:
                self.last = current  # remember it, so it isn't saved later when we resume
                return
            private = privacy.is_private()
            if private is None:
                return  # couldn't check yet; self.last is unchanged, so we retry next time
            if private:
                self.log("Skipped (marked private, e.g. a password)")
            elif db.save(self.conn, current):
                self.log(f"Saved: {preview(current)}")
            else:
                self.log(f"Skipped (too long: {len(current):,} characters)")
            self.last = current

        if time.time() - self.last_cleanup >= CLEANUP_EVERY:
            removed = db.cleanup(self.conn)
            if removed:
                self.log(f"Cleanup: deleted {removed} item(s) older than 24h")
            self.last_cleanup = time.time()


def main():
    conn = db.connect()
    print(f"Database: {db.DB_PATH}  ({db.count(conn)} items stored)")
    print("Watching clipboard... copy something! (press Ctrl+C in this window to stop)")
    watcher = Watcher(conn)
    while True:
        watcher.check()
        time.sleep(CHECK_EVERY)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
