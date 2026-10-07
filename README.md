# Clipboard History

A small Windows app that remembers what you copy for 24 hours, lets you star
favourites that are kept forever, and puts any old item back on your clipboard
with one click.

**Download:** get `ClipboardHistory-Setup.exe` from the
[latest release](../../releases/latest).

## Features

- Press **Alt+Shift+V** anywhere to open your history
- Click an item, then **Ctrl+V** to paste it anywhere
- **Saved tab**: star anything to keep it forever, with a title, a note, a tag and a
  status (*Reference*, *To read*, *Done*). Great for links you want to study later
- Links get a readable title automatically, open in your browser with one click,
  and can be ticked off once read
- Search by text, title, note or tag
- **Export saved items** from the tray menu to a readable Markdown file, grouped by
  tag, to keep a copy in Google Drive or anywhere else (a one-way copy: the app can't
  load it back in yet)
- Icons show what each item is: link, email, code, number or text
- Skips passwords copied from password managers (Bitwarden, KeePass, 1Password and others)
- **Pause recording** from the tray icon when you're copying something private
- Starts with Windows, lives in the system tray

Text only for now: images and files are not saved.

## Install

1. Download `ClipboardHistory-Setup.exe` from the [latest release](../../releases/latest).
2. Run it. Windows will probably show **"Windows protected your PC"**, because the
   app isn't signed with a paid certificate. Click **More info → Run anyway**.
3. Press **Alt+Shift+V** to open the history.

No admin rights are needed. Requires 64-bit Windows 10 or 11.

To uninstall: **Settings → Apps → Installed apps → Clipboard History → Uninstall**.

### Check your download (optional)

Each release lists the installer's SHA-256 fingerprint. To check yours matches,
open PowerShell in your Downloads folder and run:

```powershell
Get-FileHash .\ClipboardHistory-Setup.exe
```

If the result doesn't match the one in the release notes, don't run the file.

## Privacy

- Everything stays on your computer, in `%APPDATA%\ClipboardHistory\clipboard.db`.
  Nothing is sent anywhere; the app makes no internet connections.
- Items older than 24 hours are deleted, unless you saved them.
- The database is **not encrypted**. Anyone who can use your Windows account can read it.
- Passwords are skipped only when the app you copy from marks them as private
  (password managers do). A password copied from a note or a chat is saved like
  any other text: use **Pause recording** or the ✕ button for those.
- An exported file is plain text: anyone who can open it can read your saved items,
  so think before putting it in a shared folder.
- Uninstalling keeps your history. To remove it too, delete the
  `%APPDATA%\ClipboardHistory` folder.

## Build it yourself

Needs Python 3.12+ on Windows, and [Inno Setup](https://jrsoftware.org/isdl.php) for the installer.

```
pip install -r requirements.txt pyinstaller
python app.py          # run from source
python build.py        # build dist\ and installer\ClipboardHistory-Setup.exe
```

| File | What it does |
|---|---|
| `app.py` | Background app: tray icon, hotkey, ties everything together |
| `watcher.py` | Checks the clipboard every half second and saves new text |
| `popup.py` | The history window |
| `db.py` | SQLite storage, favourites, names, 24-hour cleanup |
| `cliptype.py` | Detects links, emails, code and numbers |
| `privacy.py` | Detects passwords marked private by password managers |
| `export.py` | Writes the saved items to a Markdown file |
| `icon.py` | All icons, drawn in code |
| `startup.py` | "Start with Windows" on/off |
| `build.py`, `installer.iss` | Packaging into an .exe and a Windows installer |

## License

MIT - see [LICENSE](LICENSE).
