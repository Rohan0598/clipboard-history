# Backlog

Ideas agreed on but not built yet, roughly in priority order.

## Export saved items to Markdown
A tray menu item, **Export saved items…**, that writes every saved item to a
readable `.md` file (grouped by tag, with title, link, status and note) so it can
be kept in Google Drive as a backup. Saved items now hold things worth keeping
long-term, and the database is a single unencrypted file on one laptop.

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
