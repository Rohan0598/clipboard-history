# Backlog

Ideas agreed on but not built yet, roughly in priority order.

## Import saved items from the Markdown export
Export (v1.3.0) is a one-way copy: after a wipe you can read your links in Drive but
the app can't load them back. Import would make it a real backup. Agreed rules:
- Add only: never delete or overwrite. Items already saved (same link or text) are
  skipped, so the app's version wins. Report "Imported 12, skipped 2".
- Copy `clipboard.db` to `clipboard.db.before-import` first; import in one
  all-or-nothing step.
- Needs a stricter file format than today's: a `Tag:` line inside every item (headings
  are only decoration, since a tag like `Q3 (2)` is ambiguous), dates as `2026-10-03`,
  and multi-line notes indented so a line like `- Status: Done` inside a note can't
  be mistaken for a field.
- Skip lines it can't read and say how many; refuse files with no items, or over a cap
  (about 5,000 items / 10 MB).
- Test: export, import into an empty database, export again, and compare the two files.

## Automatic backup
Pick the backup file once (e.g. inside the Google Drive folder) and rewrite it whenever
the saved items change. Only worth building together with Import, and only with these
safeguards: never overwrite with an empty list, keep the previous file as
`…-previous.md`, write to a temporary file then swap it in, and if the folder is
missing show "Backup folder not found" instead of creating one. After a restore, import
first and only then switch it on, or an empty app can overwrite a full backup.

## Replace the `keyboard` library with Windows' RegisterHotKey
`keyboard` listens to every key press (like a keylogger) just to catch Alt+Shift+V.
RegisterHotKey only listens for the one shortcut: safer, and less likely to be
flagged by antivirus or store reviewers. Needed before any Microsoft Store release.

## Microsoft Store release (MSIX)
Free signing for individuals through the Store. Needs: RegisterHotKey (above),
a startup task instead of the registry Run entry, a privacy policy page,
screenshots, and a more distinctive app name.

## Mac version
Port the Python app (shared database, watcher and popup; Mac-specific menu bar
icon, hotkey, password markers, login item and .dmg). Needs a Mac to build and test.
