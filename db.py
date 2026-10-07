"""
Stage 10: Database layer (clipboard history, saved items, 24-hour cleanup).

A "saved" item is a row with favourite = 1. It never expires, and can have a
title (the label column), a note, one tag and a status:
  "reference"  keep it handy (the default, and what old favourites become)
  "to_read"    saved to read or study later
  "done"       read
Everything that touches the SQLite file lives here, so the watcher
and the popup window can just call these functions.
"""

import os
import shutil
import sqlite3
import time

# The data lives in your user's AppData folder: C:\Users\<you>\AppData\Roaming\ClipboardHistory
# (Next to the script was fine while developing, but a packaged .exe unpacks its
# code into a temporary folder, and anything saved there would be lost.)
APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ClipboardHistory")
DB_PATH = os.path.join(APP_DIR, "clipboard.db")

# Where stages 2-6 kept it. If a database is found there, it's moved over once.
OLD_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clipboard.db")

# Skip gigantic copies (e.g. a whole log file). 100,000 characters is ~100 KB.
MAX_LENGTH = 100_000

# Non-favourite items older than this are deleted. 24 hours, in seconds.
MAX_AGE = 24 * 60 * 60


def connect():
    """Open the database and create the table the first time."""
    os.makedirs(APP_DIR, exist_ok=True)
    if not os.path.exists(DB_PATH) and os.path.exists(OLD_DB_PATH):
        shutil.move(OLD_DB_PATH, DB_PATH)  # one-time move from the old location
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us use row["text"] instead of row[1]
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            text      TEXT    NOT NULL UNIQUE,  -- same text is never stored twice
            copied_at REAL    NOT NULL,         -- Unix time in seconds
            favourite INTEGER NOT NULL DEFAULT 0, -- 0 = normal, 1 = saved
            label     TEXT,                        -- title of a saved item
            note      TEXT,                        -- why you saved it
            tag       TEXT,                        -- one tag, e.g. "AI for PMs"
            status    TEXT,                        -- reference / to_read / done
            saved_at  REAL                         -- when it was saved (Saved tab order)
        )
        """
    )
    # Older databases are missing some of these columns: add them.
    # (ALTER TABLE keeps every existing row; the new columns just start empty.)
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(items)")]
    for name in ("label", "note", "tag", "status", "saved_at"):
        if name not in columns:
            conn.execute(f"ALTER TABLE items ADD COLUMN {name} {'REAL' if name == 'saved_at' else 'TEXT'}")
    conn.commit()
    return conn


def save(conn, text):
    """
    Save a copied item. If the exact text is already stored, just refresh
    its time so it jumps back to the top (and keeps its favourite star).
    Returns False if the text was too big to store.
    """
    if len(text) > MAX_LENGTH:
        return False
    conn.execute(
        """
        INSERT INTO items (text, copied_at) VALUES (?, ?)
        ON CONFLICT(text) DO UPDATE SET copied_at = excluded.copied_at
        """,
        (text, time.time()),
    )
    conn.commit()
    return True


COLUMNS = "id, text, copied_at, favourite, label, note, tag, COALESCE(status, 'reference') AS status, saved_at"
STATUSES = ("reference", "to_read", "done")


def recent(conn, limit=50):
    """Clipboard history (not saved items), newest first."""
    return conn.execute(
        f"SELECT {COLUMNS} FROM items WHERE favourite = 0 ORDER BY copied_at DESC LIMIT ?",
        (limit,),
    ).fetchall()


def favourites(conn):
    """Saved items, most recently saved first. These never expire."""
    return conn.execute(
        f"SELECT {COLUMNS} FROM items WHERE favourite = 1 "
        "ORDER BY COALESCE(saved_at, copied_at) DESC"
    ).fetchall()


saved = favourites  # the popup calls them "saved"; history.py still says favourites


def get(conn, item_id):
    return conn.execute(f"SELECT {COLUMNS} FROM items WHERE id = ?", (item_id,)).fetchone()


def tags(conn):
    """Tags used on saved items, most recently used first."""
    rows = conn.execute(
        "SELECT tag, MAX(COALESCE(saved_at, copied_at)) AS latest FROM items "
        "WHERE favourite = 1 AND tag IS NOT NULL AND tag != '' GROUP BY tag ORDER BY latest DESC"
    ).fetchall()
    return [row["tag"] for row in rows]


def save_item(conn, text, title=None, note=None, tag=None, status="reference", item_id=None):
    """
    Save an item for later (or update a saved one). Returns its id.
    item_id given: update that item. Otherwise the text is added, or, if it's
    already in the history, that row is turned into a saved item.
    """
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    clean = lambda value: (value or "").strip() or None  # empty strings are stored as "nothing"
    values = (clean(title), clean(note), clean(tag), status)
    now = time.time()
    if item_id is not None:
        conn.execute(
            "UPDATE items SET favourite = 1, label = ?, note = ?, tag = ?, status = ?, "
            "saved_at = COALESCE(saved_at, ?) WHERE id = ?",
            (*values, now, item_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO items (text, copied_at, favourite, label, note, tag, status, saved_at)
            VALUES (?, ?, 1, ?, ?, ?, ?, ?)
            ON CONFLICT(text) DO UPDATE SET favourite = 1, label = excluded.label,
                note = excluded.note, tag = excluded.tag, status = excluded.status,
                saved_at = excluded.saved_at
            """,
            (text, now, *values, now),
        )
        item_id = conn.execute("SELECT id FROM items WHERE text = ?", (text,)).fetchone()["id"]
    conn.commit()
    return item_id


def set_status(conn, item_id, status):
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    conn.execute("UPDATE items SET status = ? WHERE id = ?", (status, item_id))
    conn.commit()


def set_favourite(conn, item_id, on=True):
    """Star (on=True) or unstar (on=False) an item. Returns False if the id doesn't exist."""
    cur = conn.execute(
        "UPDATE items SET favourite = ? WHERE id = ?", (1 if on else 0, item_id)
    )
    conn.commit()
    return cur.rowcount > 0


def set_label(conn, item_id, label):
    """Give an item a name (or None to remove it). The name is kept even if you unstar it."""
    conn.execute("UPDATE items SET label = ? WHERE id = ?", (label, item_id))
    conn.commit()


def cleanup(conn, max_age=MAX_AGE):
    """Delete non-favourite items older than max_age seconds. Returns how many were deleted."""
    cutoff = time.time() - max_age
    cur = conn.execute(
        "DELETE FROM items WHERE favourite = 0 AND copied_at < ?", (cutoff,)
    )
    conn.commit()
    return cur.rowcount


def delete(conn, item_id):
    """Remove one item, favourite or not."""
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()


def backdate(conn, item_id, hours):
    """TESTING ONLY: pretend an item was copied `hours` ago."""
    cur = conn.execute(
        "UPDATE items SET copied_at = ? WHERE id = ?",
        (time.time() - hours * 3600, item_id),
    )
    conn.commit()
    return cur.rowcount > 0


def count(conn):
    return conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
