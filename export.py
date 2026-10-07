"""
Stage 11: Export saved items to a Markdown file.

The file is a readable copy of your Saved tab (grouped by tag, newest first) that you
can keep in Google Drive. It is one-way: the app cannot read it back in (see BACKLOG.md).

  to_markdown(rows)      the file's text, from the rows db.saved() returns
  write(path, rows)      writes it, returns how many items it contains
  default_filename()     ClipboardHistory-saved-2026-10-07.md

Nothing here touches the window or the database, so it is easy to test on its own.
"""

import datetime
import re

import cliptype

# Spelled out here (not strftime) so the file is the same on every Windows language setting.
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
STATUS_NAMES = {"reference": "Reference", "to_read": "To read", "done": "Done"}
NO_TAG = "No tag"


def nice_date(timestamp):
    d = datetime.datetime.fromtimestamp(timestamp)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def default_filename(now=None):
    now = now or datetime.datetime.now()
    return f"ClipboardHistory-saved-{now:%Y-%m-%d}.md"


def _one_line(text, limit):
    """Squash text onto one line and cut it short."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _title(row):
    """Your title; otherwise one made from the link; otherwise the start of the text."""
    label = _one_line(row["label"] or "", 200)
    if label:
        return label
    text = row["text"].strip()
    if cliptype.detect(text) == "link":
        return cliptype.title_from_url(text)
    return _one_line(text, 70)


def _code_block(text):
    """Text in a fenced block. The fence is longer than any run of backticks inside, so it can't break out."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return [fence, text, fence]


def _item(row):
    text = row["text"].replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    is_link = cliptype.detect(text) == "link"
    lines = [f"### {_title(row)}"]
    if is_link:
        lines.append(f"- Link: {text.strip()}")
    lines.append(f"- Status: {STATUS_NAMES.get(row['status'], 'Reference')}")
    lines.append(f"- Saved: {nice_date(row['saved_at'] or row['copied_at'])}")
    note = (row["note"] or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if note:
        first, *rest = note.split("\n")
        lines.append(f"- Note: {first}")
        lines.extend(f"  {line}" if line.strip() else "" for line in rest)  # indented = still part of the note
    if not is_link:
        lines.append("")
        lines.extend(_code_block(text))
    return lines


def to_markdown(rows, now=None):
    rows = list(rows)
    now = now or datetime.datetime.now()
    to_read = sum(1 for row in rows if row["status"] == "to_read")
    summary = [f"Exported {now.day} {MONTHS[now.month - 1]} {now.year}",
               f"{len(rows)} item" + ("" if len(rows) == 1 else "s")]
    if to_read:
        summary.append(f"{to_read} to read")

    # Group by tag, alphabetically, with untagged items last. Rows arrive newest first
    # and keep that order inside each group.
    groups = {}
    for row in rows:
        groups.setdefault((row["tag"] or "").strip(), []).append(row)
    names = sorted((name for name in groups if name), key=lambda name: (name.casefold(), name))
    if "" in groups:
        names.append("")

    out = ["# Clipboard History · Saved items", "", " · ".join(summary)]
    for name in names:
        out += ["", f"## {name or NO_TAG} ({len(groups[name])})"]
        for row in groups[name]:
            out += [""] + _item(row)
    return "\n".join(out) + "\n"


def write(path, rows):
    """Write the file (UTF-8, \\n line endings). Returns the number of items."""
    rows = list(rows)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(to_markdown(rows))
    return len(rows)
