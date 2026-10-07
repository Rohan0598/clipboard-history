"""
Stage 3: View history and manage favourites from the terminal.

  python history.py              show favourites + recent items
  python history.py fav 3        star item #3 (it will never be deleted)
  python history.py unfav 3      remove the star from item #3
  python history.py cleanup      delete non-favourites older than 24h right now

  python history.py age 3 25     TESTING: pretend item #3 was copied 25 hours ago
"""

import sys
import time

import db


def time_ago(seconds):
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    return f"{int(seconds // 86400)} d ago"


def print_rows(rows, now):
    for row in rows:
        text = " ".join(row["text"].split())
        if len(text) > 60:
            text = text[:60] + "..."
        print(f"  #{row['id']:<4} {time_ago(now - row['copied_at']):>10}   {text}")


def show(conn):
    now = time.time()
    favs = db.favourites(conn)
    rows = db.recent(conn, limit=20)

    print(f"* FAVOURITES ({len(favs)})")
    print_rows(favs, now) if favs else print("  (none - star one with: python history.py fav <id>)")

    print(f"\nRECENT - last 24h (showing {len(rows)})")
    print_rows(rows, now) if rows else print("  (nothing yet)")


def get_id(args):
    if len(args) < 1 or not args[0].isdigit():
        sys.exit("Give an item number, e.g.  python history.py fav 3")
    return int(args[0])


def main():
    conn = db.connect()
    command = sys.argv[1] if len(sys.argv) > 1 else "show"
    args = sys.argv[2:]

    if command == "show":
        show(conn)

    elif command in ("fav", "unfav"):
        item_id = get_id(args)
        if db.set_favourite(conn, item_id, on=(command == "fav")):
            print(f"#{item_id} {'starred' if command == 'fav' else 'unstarred'}.\n")
            show(conn)
        else:
            print(f"No item #{item_id}.")

    elif command == "cleanup":
        print(f"Deleted {db.cleanup(conn)} item(s).\n")
        show(conn)

    elif command == "age":
        item_id = get_id(args)
        hours = float(args[1]) if len(args) > 1 else 25
        if db.backdate(conn, item_id, hours):
            print(f"#{item_id} now looks {hours:g}h old.\n")
            show(conn)
        else:
            print(f"No item #{item_id}.")

    else:
        print(__doc__)


if __name__ == "__main__":
    main()
