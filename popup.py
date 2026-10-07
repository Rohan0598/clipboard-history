"""
Stage 10: The popup window, with two tabs.

  Clipboard  everything you copied in the last 24 hours
  Saved      things you chose to keep: a title, a status (Reference / To read / Done),
             one tag and a note. Saved items never expire.

app.py opens this when you press the hotkey. You can still test it alone:
  python popup.py

- Click a row to put it on your clipboard (the window closes; press Ctrl+V anywhere).
- Clipboard tab: the star opens the "Save for later" form.
- Saved tab: arrow opens a link in your browser, tick marks it as read, pencil edits it
  (delete is inside the edit form). New adds something you didn't copy.
- Search matches text, titles, notes and tags. Enter copies the top result.
- Esc closes the form, or the popup. Clicking another app closes the popup.
"""

import sys
import time
import tkinter as tk
import webbrowser

import customtkinter as ctk
import pyperclip

import cliptype
import db
import icon

WIDTH, HEIGHT = 440, 560
MAX_RECENT_SHOWN = 30  # drawing hundreds of rows makes typing in search feel slow
MAX_SAVED_SHOWN = 60

# ---------- dark theme colours (from the mockup) ----------
BG = "#202020"
ROW = "#272727"
ROW_HOVER = "#303030"
FIELD = "#2b2b2b"
BORDER = "#3a3a3a"
DIVIDER = "#2c2c2c"
TEXT = "#e8e8e8"
SOFT = "#c8c8c8"
MUTED = "#a3a3a3"
FAINT = "#8f8f8f"
ACCENT = "#4cc2ff"
BLUE_BG = "#1f3848"
BLUE_TEXT = "#6cc8ff"
GOLD = "#f5c542"
DANGER = "#ff8a80"
FONT = "Segoe UI"

STATUS_LABELS = {"reference": "Reference", "to_read": "To read", "done": "Done"}
LABEL_STATUS = {label: status for status, label in STATUS_LABELS.items()}

FOOTERS = {
    "clipboard": "Click to copy     Star to save     Esc to close",
    "saved": "Click to copy     Arrow to open     Tick when read",
}

# Widths in pixels at 100% Windows scaling. Fonts and widgets are scaled up together,
# so these stay correct at 125% or 150% too.
TEXT_WIDTH_RECENT = 252   # clipboard row: room left after the icon, time, star and x
SAVED_ROW_WIDTH = 404     # a saved row from edge to edge
CHIPS_WIDTH = 414         # the filter chips row
FORM_WIDTH = 406          # inside the form's margins

# Which tab was open last, so the next popup opens on the same one (while the app runs).
LAST_VIEW = "clipboard"


def fit(text, font, max_px):
    """
    Squash text onto one line and cut it with "…" so it fits in max_px pixels.
    Measuring real pixel widths works for any font, unlike counting characters
    ("iiii" is much narrower than "WWWW").
    """
    one_line = " ".join(text[:400].split())
    if font.measure(one_line) <= max_px:
        return one_line
    low, high = 0, len(one_line)
    while low < high:  # binary search for the longest piece that still fits
        mid = (low + high + 1) // 2
        if font.measure(one_line[:mid].rstrip() + "…") <= max_px:
            low = mid
        else:
            high = mid - 1
    return one_line[:low].rstrip() + "…"


def time_ago(seconds):
    if seconds < 60:
        return "now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h"
    return f"{int(seconds // 86400)}d"


def browser_address(text):
    """What to hand the browser: add https:// to links that start with www."""
    text = text.strip()
    return text if "://" in text else "https://" + text


class Tooltip:
    """A small label that appears under a widget after the mouse rests on it for 0.4 s."""

    def __init__(self, widget, text):
        self.widget, self.text = widget, text
        self.tip = None
        self.job = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def _schedule(self, event=None):
        self._cancel()
        self.job = self.widget.after(400, self._show)

    def _cancel(self):
        if self.job:
            try:
                self.widget.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None

    def _show(self):
        self.job = None
        if self.tip or not self.widget.winfo_exists():
            return
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.overrideredirect(True)          # no title bar or border from Windows
        self.tip.attributes("-topmost", True)
        self.tip.configure(bg="#4a4a4a")         # shows as a 1px border around the label
        tk.Label(self.tip, text=self.text, bg="#2f2f2f", fg=TEXT, font=(FONT, 9),
                 padx=8, pady=3, bd=0).pack(padx=1, pady=1)
        self.tip.geometry(f"+{x}+{y}")

    def _hide(self, event=None):
        self._cancel()
        if self.tip:
            try:
                self.tip.destroy()
            except tk.TclError:
                pass
            self.tip = None


class Popup(ctk.CTkToplevel):
    """
    A Toplevel is a window that belongs to a hidden main window (the "root").
    That lets the app keep running after this popup closes, and open a fresh one next time.

    self.view is what's showing: "clipboard", "saved" or "form".
    """

    def __init__(self, master, on_close=None):
        super().__init__(master, fg_color=BG)
        self.on_close = on_close  # app.py passes a function to call when we close
        self._closed = False
        self.conn = db.connect()
        db.cleanup(self.conn)

        self.view = LAST_VIEW
        self.status_filter = "all"   # Saved tab: all / to_read / done / reference
        self.tag_filter = None       # Saved tab: one tag, or None for every tag
        self.shown = []              # rows currently on screen, in order (Enter copies the first)
        self._pending_refresh = None
        self.form = None             # what the Save form is editing (a dict), when it's open
        self.form_frame = None

        self.font = lambda size, bold=False: ctk.CTkFont(family=FONT, size=size, weight="bold" if bold else "normal")
        self.fonts = {
            "text": self.font(14), "name": self.font(14, bold=True), "sub": self.font(12),
            "note": self.font(12), "chip": self.font(12), "pill": self.font(10, bold=True),
            "label": self.font(12, bold=True), "heading": self.font(17, bold=True),
        }

        self.title("Clipboard History")
        self.attributes("-topmost", True)
        if sys.platform == "win32":
            # A "tool window" has only an X button (no minimize/maximize) and no
            # taskbar button, so it behaves like a small panel instead of an app window.
            self.attributes("-toolwindow", True)
        self._place_near_mouse()
        self._dark_title_bar()
        self.after(60, self._dark_title_bar)  # again once Windows has actually drawn it

        # --- Tabs ---
        self.tab_values = ["Clipboard", "Saved"]
        self.tab_bar = ctk.CTkSegmentedButton(
            self, values=self.tab_values, command=self._on_tab, height=34, corner_radius=8,
            font=self.font(13, bold=True), fg_color=FIELD, selected_color="#3d3d3d",
            selected_hover_color="#454545", unselected_color=FIELD, unselected_hover_color="#333333",
            text_color=TEXT)

        # --- Search row (plus the New button on the Saved tab) ---
        self.search_row = ctk.CTkFrame(self, fg_color="transparent")
        self._build_search(self.search_row)
        self.new_button = ctk.CTkButton(
            self.search_row, text="New", image=icon.ctk_icon("plus", TEXT, 13), width=72, height=40,
            fg_color=FIELD, hover_color=ROW_HOVER, border_width=1, border_color=BORDER,
            text_color=TEXT, font=self.font(13), corner_radius=6, command=lambda: self._open_form())

        # --- Filter chips (Saved tab) ---
        self.chips = ctk.CTkFrame(self, fg_color="transparent", height=30)

        # --- Scrollable list ---
        self.list = ctk.CTkScrollableFrame(
            self, fg_color=BG, scrollbar_button_color=BORDER, scrollbar_button_hover_color="#4a4a4a")

        # --- Footer ---
        self.footer_line = ctk.CTkFrame(self, height=1, fg_color=DIVIDER, corner_radius=0)
        self.footer = ctk.CTkLabel(self, text="", text_color=FAINT, font=self.font(12), height=30)

        self.bind("<Escape>", self._on_escape)
        self.bind("<Return>", self._on_return)
        self.bind("<Control-Return>", self._on_ctrl_return)
        self.protocol("WM_DELETE_WINDOW", self.close)  # the window's own X button
        # Close when you click on another app, like Win+V does.
        self.bind("<FocusOut>", lambda e: self.after(150, self._close_if_unfocused))

        self._layout()
        self.refresh()
        # Windows sometimes opens new windows behind others; force focus onto the search box.
        self.after(100, self._grab_focus)

    # =====================================================================
    # Window setup
    # =====================================================================

    def _build_search(self, parent):
        box = ctk.CTkFrame(parent, fg_color=FIELD, border_color=BORDER, border_width=1,
                           corner_radius=6, height=40)
        box.pack(side="left", fill="x", expand=True)
        box.pack_propagate(False)
        self.search_box = box
        # The blue line along the bottom of the search box.
        ctk.CTkFrame(box, height=2, fg_color=ACCENT, corner_radius=0).pack(side="bottom", fill="x", padx=3, pady=(0, 1))
        ctk.CTkLabel(box, text="", image=icon.ctk_icon("search", MUTED, 16), width=20).pack(side="left", padx=(12, 4))
        self.search = ctk.CTkEntry(
            box, placeholder_text="Search", fg_color=FIELD, border_width=0,
            text_color=TEXT, placeholder_text_color=FAINT, font=self.font(14), height=34)
        self.search.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=(1, 0))
        self.search.bind("<KeyRelease>", self._on_type)

    def _dark_title_bar(self):
        """Ask Windows for a dark title bar that matches the window (Windows 10 20H1+ / 11)."""
        if sys.platform != "win32" or self._closed:
            return
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            on = ctypes.c_int(1)
            for attribute in (20, 19):  # "use dark mode": 20 on newer Windows, 19 on older
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(on), ctypes.sizeof(on))
            colour = ctypes.c_int(0x00202020)  # Windows 11 only: exact title bar colour (0x00BBGGRR)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(colour), ctypes.sizeof(colour))
        except Exception:
            pass  # purely cosmetic; never let it stop the popup

    def _place_near_mouse(self):
        x, y = self.winfo_pointerxy()
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, min(x - 20, screen_w - WIDTH - 10))   # keep it fully on screen
        y = max(0, min(y - 20, screen_h - HEIGHT - 60))  # 60px margin for the taskbar
        self.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

    def _layout(self):
        """Show the pieces the current view needs, in order, and hide the rest."""
        for widget in (self.tab_bar, self.search_row, self.chips, self.list, self.footer_line, self.footer):
            widget.pack_forget()
        if self.form_frame is not None:
            self.form_frame.pack_forget()

        if self.view == "form":
            self.form_frame.pack(fill="both", expand=True)
            return

        self.tab_bar.pack(fill="x", padx=12, pady=(12, 0))
        self.search_row.pack(fill="x", padx=12, pady=(10, 6))
        if self.view == "saved":
            self.new_button.pack(side="right", padx=(8, 0), before=self.search_box)
            self.chips.pack(fill="x", padx=12, pady=(0, 4))
            placeholder = "Search titles, notes, tags"
        else:
            self.new_button.pack_forget()
            placeholder = "Search"
        if not self.search.get():
            self.search.configure(placeholder_text=placeholder)
        self.list.pack(fill="both", expand=True, padx=(6, 2))
        self.footer_line.pack(fill="x")
        self.footer.configure(text=FOOTERS[self.view])
        self.footer.pack(fill="x", pady=(2, 4))

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.conn.close()
        self.destroy()
        if self.on_close:
            self.on_close()

    def _focus_elsewhere(self):
        """True when keyboard focus is in a different application."""
        try:
            return self.focus_get() is None
        except (KeyError, tk.TclError):
            return False  # focus is on a widget that was just destroyed: still ours

    def _close_if_unfocused(self, second_look=False):
        # Focus can look "gone" for a moment while a focused box is being replaced,
        # so only close if it still looks gone a little later.
        if self._closed or not self._focus_elsewhere():
            return
        if second_look:
            self.close()
        else:
            self.after(150, lambda: self._close_if_unfocused(second_look=True))

    def _grab_focus(self):
        if self._closed:
            return
        self.lift()
        self.focus_force()
        if self.view != "form":
            self.search.focus_set()

    # =====================================================================
    # Keys and tabs
    # =====================================================================

    def _on_type(self, event):
        if event.keysym in ("Return", "Escape"):
            return
        # Wait until typing pauses for 150ms before redrawing (called "debouncing").
        if self._pending_refresh:
            self.after_cancel(self._pending_refresh)
        self._pending_refresh = self.after(150, self.refresh)

    def _on_escape(self, event=None):
        if self.view == "form":
            self._close_form()
        else:
            self.close()

    def _on_return(self, event=None):
        if self.view == "form":
            # Enter in the title box saves; Enter in the note box is just a new line.
            if self.focus_get() is getattr(self, "f_title", None) or \
                    self.focus_get() is getattr(getattr(self, "f_title", None), "_entry", None):
                self._save_form()
            return
        if self.shown:
            self._copy(self.shown[0]["text"])

    def _on_ctrl_return(self, event=None):
        if self.view == "form":
            self._save_form()
            return "break"

    def _on_tab(self, value):
        global LAST_VIEW
        self.view = "clipboard" if value == self.tab_values[0] else "saved"
        LAST_VIEW = self.view
        self.search.delete(0, "end")
        self._layout()
        self.refresh()
        self.search.focus_set()

    def _update_tab_label(self):
        to_read = sum(1 for r in db.saved(self.conn) if r["status"] == "to_read")
        values = ["Clipboard", f"Saved · {to_read} to read" if to_read else "Saved"]
        if values != self.tab_values:
            self.tab_values = values
            self.tab_bar.configure(values=values)
        self.tab_bar.set(values[0] if self.view == "clipboard" else values[1])

    # =====================================================================
    # Drawing the lists
    # =====================================================================

    def refresh(self):
        if self._closed or self.view == "form":
            return
        self._pending_refresh = None
        for widget in self.list.winfo_children():
            widget.destroy()
        self._update_tab_label()
        query = self.search.get().lower().strip()
        if self.view == "clipboard":
            self._draw_clipboard(query)
        else:
            self._draw_saved(query)
        try:
            self.list._parent_canvas.yview_moveto(0)  # back to the top after redrawing
        except Exception:
            pass

    def _section_header(self, title, count):
        head = ctk.CTkFrame(self.list, fg_color="transparent")
        head.pack(fill="x", padx=8, pady=(6, 4))
        ctk.CTkLabel(head, text=title, text_color=MUTED, font=self.font(11, bold=True), height=16).pack(side="left")
        ctk.CTkLabel(head, text=str(count), text_color="#7d7d7d", font=self.font(11, bold=True),
                     height=16).pack(side="left", padx=(8, 0))

    def _message(self, text):
        ctk.CTkLabel(self.list, text=text, anchor="w", justify="left", text_color=MUTED,
                     font=self.font(13), wraplength=380).pack(fill="x", padx=10, pady=(4, 0))

    def _type_badge(self, parent, text, size=28):
        kind = cliptype.detect(text)
        badge_bg, icon_colour = cliptype.COLORS[kind]
        badge = ctk.CTkLabel(parent, text="", image=icon.ctk_icon(kind, icon_colour, 15 if size >= 28 else 13),
                             width=size, height=size, fg_color=badge_bg, corner_radius=6)
        Tooltip(badge, cliptype.NAMES[kind])
        return badge

    def _icon_button(self, parent, icon_name, tooltip, command, colour=MUTED, size=15):
        button = ctk.CTkButton(parent, text="", image=icon.ctk_icon(icon_name, colour, size), width=28, height=28,
                               fg_color="transparent", hover_color=BORDER, corner_radius=6, command=command)
        Tooltip(button, tooltip)
        return button

    def _text_button(self, parent, symbol, colour, size, command, tooltip=None):
        button = ctk.CTkButton(parent, text=symbol, width=28, height=28, fg_color="transparent",
                               hover_color=BORDER, text_color=colour, font=self.font(size),
                               corner_radius=6, command=command)
        if tooltip:
            Tooltip(button, tooltip)
        return button

    def _make_clickable(self, frame, widgets, text):
        """Clicking anywhere on these widgets copies the text; hovering lightens the row."""
        for widget in widgets:
            widget.bind("<Button-1>", lambda e=None, t=text: self._copy(t), add="+")
            widget.bind("<Enter>", lambda e=None, f=frame: self._hover(f, True), add="+")
            widget.bind("<Leave>", lambda e=None, f=frame: self._hover(f, False), add="+")

    def _hover(self, frame, on):
        try:
            frame.configure(fg_color=ROW_HOVER if on else ROW)
        except tk.TclError:
            pass  # the row was redrawn a moment ago

    # ---------- Clipboard tab ----------

    def _draw_clipboard(self, query):
        rows = [r for r in db.recent(self.conn, limit=500) if query in r["text"].lower()][:MAX_RECENT_SHOWN]
        self.shown = rows
        self._section_header("RECENT · LAST 24 HOURS", len(rows))
        if not rows:
            self._message("No matches." if query else "Nothing copied in the last 24 hours.")
        now = time.time()
        for row in rows:
            self._clipboard_row(row, now)

    def _clipboard_row(self, row, now):
        frame = ctk.CTkFrame(self.list, fg_color=ROW, corner_radius=6, height=44)
        frame.pack(fill="x", padx=4, pady=3)
        frame.pack_propagate(False)  # keep the fixed row height

        badge = self._type_badge(frame, row["text"])
        badge.pack(side="left", padx=(8, 10))

        self._text_button(frame, "✕", MUTED, 12, lambda r=row: self._delete(r["id"])).pack(side="right", padx=(0, 4))
        self._text_button(frame, "☆", "#8a8a8a", 17, lambda r=row: self._open_form(r),
                          tooltip="Save for later").pack(side="right")
        when = ctk.CTkLabel(frame, text=time_ago(now - row["copied_at"]), text_color=MUTED,
                            font=self.font(12), width=30, anchor="e")
        when.pack(side="right", padx=(4, 4))
        label = ctk.CTkLabel(frame, text=fit(row["text"], self.fonts["text"], TEXT_WIDTH_RECENT),
                             text_color=TEXT, font=self.fonts["text"], anchor="w")
        label.pack(side="left", fill="x", expand=True)
        self._make_clickable(frame, [frame, badge, label, when], row["text"])

    # ---------- Saved tab ----------

    def _draw_saved(self, query):
        def matches(row):
            haystack = " ".join(filter(None, (row["text"], row["label"], row["note"], row["tag"])))
            return query in haystack.lower()

        everything = db.saved(self.conn)
        items = [r for r in everything if matches(r)]
        if self.tag_filter:
            items = [r for r in items if r["tag"] == self.tag_filter]
        counts = {status: sum(1 for r in items if r["status"] == status) for status in db.STATUSES}
        self._draw_chips(len(items), counts)
        if self.status_filter != "all":
            items = [r for r in items if r["status"] == self.status_filter]

        shown = items[:MAX_SAVED_SHOWN]
        self.shown = shown
        if not shown:
            if not everything:
                self._message("Nothing saved yet. Click ☆ on anything in the Clipboard tab, or New.")
            elif self.status_filter == "to_read" and not query and not self.tag_filter:
                self._message("Nothing left to read.")
            else:
                self._message("No matches.")
        for row in shown:
            self._saved_row(row)
        if len(items) > len(shown):
            self._message(f"Showing {len(shown)} of {len(items)}. Search to find the rest.")

    def _chip(self, parent, text, selected, command):
        width = self.fonts["chip"].measure(text) + 22
        chip = ctk.CTkButton(
            parent, text=text, width=width, height=26, corner_radius=13, font=self.fonts["chip"],
            fg_color=TEXT if selected else BG, hover_color="#d0d0d0" if selected else ROW_HOVER,
            text_color="#1b1b1b" if selected else SOFT, border_width=0 if selected else 1,
            border_color=BORDER, command=command)
        return chip, width

    def _draw_chips(self, total, counts):
        for widget in self.chips.winfo_children():
            widget.destroy()
        used = 0
        status_chips = [("All", total, "all"), ("To read", counts["to_read"], "to_read"),
                        ("Done", counts["done"], "done")]
        for name, count, status in status_chips:
            chip, width = self._chip(self.chips, f"{name} {count}", self.status_filter == status,
                                     lambda s=status: self._set_status_filter(s))
            chip.pack(side="left", padx=(0, 6))
            used += width + 6

        tags = db.tags(self.conn)
        if self.tag_filter and self.tag_filter not in tags:
            tags.insert(0, self.tag_filter)  # so a filter on a now-empty tag can still be switched off
        if tags:
            ctk.CTkFrame(self.chips, width=1, height=18, fg_color=BORDER).pack(side="left", padx=(0, 6))
            used += 7
        for tag in tags:
            chip, width = self._chip(self.chips, tag, self.tag_filter == tag, lambda t=tag: self._toggle_tag_filter(t))
            if used + width > CHIPS_WIDTH and self.tag_filter != tag:
                chip.destroy()  # no room: search still finds items by tag
                continue
            chip.pack(side="left", padx=(0, 6))
            used += width + 6

    def _set_status_filter(self, status):
        self.status_filter = status
        self.refresh()

    def _toggle_tag_filter(self, tag):
        self.tag_filter = None if self.tag_filter == tag else tag
        self.refresh()

    def _saved_row(self, row):
        text, status, note = row["text"], row["status"], row["note"]
        is_link = cliptype.detect(text) == "link"
        frame = ctk.CTkFrame(self.list, fg_color=ROW, corner_radius=6, height=76 if note else 58)
        frame.pack(fill="x", padx=4, pady=3)
        frame.pack_propagate(False)

        badge = self._type_badge(frame, text)
        badge.pack(side="left", anchor="n", padx=(8, 10), pady=(10, 0))

        # Buttons, packed from the right edge inwards: [open] [tick] [edit]
        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.pack(side="right", anchor="n", padx=(0, 4), pady=(8, 0))
        count = 1
        self._icon_button(buttons, "pencil", "Edit", lambda r=row: self._open_form(r)).pack(side="right")
        if status == "to_read":
            self._icon_button(buttons, "check", "Mark as read", lambda r=row: self._mark_done(r["id"]),
                              size=16).pack(side="right")
            count += 1
        if is_link:
            self._icon_button(buttons, "open", "Open in browser", lambda t=text: self._open_link(t)).pack(side="right")
            count += 1
        room = SAVED_ROW_WIDTH - 52 - 6 - 28 * count

        column = ctk.CTkFrame(frame, fg_color="transparent")
        column.pack(side="left", fill="both", expand=True, pady=(7, 6))

        # Line 1: title, plus a TO READ / DONE pill.
        line1 = ctk.CTkFrame(column, fg_color="transparent", height=21)
        line1.pack(fill="x")
        title = row["label"] or (cliptype.title_from_url(text) if is_link else text)
        pill = {"to_read": ("TO READ", BLUE_BG, BLUE_TEXT), "done": ("DONE", BORDER, MUTED)}.get(status)
        pill_width = self.fonts["pill"].measure(pill[0]) + 20 if pill else 0
        title_label = ctk.CTkLabel(line1, text=fit(title, self.fonts["name"], room - pill_width),
                                   text_color=MUTED if status == "done" else TEXT,
                                   font=self.fonts["name"], anchor="w", height=21)
        title_label.pack(side="left")
        clickable = [frame, badge, column, line1, title_label]
        if pill:
            pill_label = ctk.CTkLabel(line1, text=pill[0], fg_color=pill[1], text_color=pill[2],
                                      font=self.fonts["pill"], corner_radius=4, height=18,
                                      width=pill_width - 8)
            pill_label.pack(side="left", padx=(6, 0))
            clickable.append(pill_label)

        # Line 2: where it points, and its tag.
        if is_link:
            where = cliptype.short_address(text)
        elif row["label"]:
            where = text          # titled text: show the text itself underneath
        else:
            where = ""            # untitled text: the title line already shows it
        tag = row["tag"]
        tag_part = f"  ·  {tag}" if tag else ""
        if where:
            meta = fit(where, self.fonts["sub"], room - self.fonts["sub"].measure(tag_part)) + tag_part
        else:
            meta = tag or ""
        meta_label = ctk.CTkLabel(column, text=meta, text_color=MUTED, font=self.fonts["sub"],
                                  anchor="w", height=17)
        meta_label.pack(fill="x")
        clickable.append(meta_label)

        # Line 3: the note, if there is one.
        if note:
            note_label = ctk.CTkLabel(column, text=fit(f"“{note}”", self.fonts["note"], room),
                                      text_color=SOFT, font=self.fonts["note"], anchor="w", height=17)
            note_label.pack(fill="x")
            clickable.append(note_label)

        self._make_clickable(frame, clickable, text)

    # =====================================================================
    # The Save / Edit / New form
    # =====================================================================

    def _open_form(self, row=None):
        """
        row from the Clipboard tab -> "Save for later" (the copied item becomes a saved item)
        row from the Saved tab     -> "Edit saved item"
        no row                     -> "New saved item" (type a link or text yourself)
        """
        editing = row is not None and row["favourite"] == 1
        new = row is None
        text = row["text"] if row else ""
        is_link = bool(text) and cliptype.detect(text) == "link"

        if editing:
            title = row["label"] or (cliptype.title_from_url(text) if is_link else "")
            status, note, tag = row["status"], row["note"] or "", row["tag"]
        else:
            title = cliptype.title_from_url(text) if is_link else ""
            status = "to_read" if is_link else "reference"
            note, tag = "", None

        self.form = {"item_id": row["id"] if row else None, "editing": editing, "new": new,
                     "text": text, "tag": tag, "auto_title": "" if editing else title,
                     "from": self.view, "delete_armed": False}
        self._build_form(title, status, note,
                         heading="Edit saved item" if editing else "New saved item" if new else "Save for later",
                         title_hint=bool(title) and not editing and is_link)
        self.view = "form"
        self._layout()
        self.after(30, lambda: (self.f_text if new else self.f_title).focus_set())

    def _field_label(self, parent, text, extra=None):
        line = ctk.CTkFrame(parent, fg_color="transparent")
        line.pack(fill="x", pady=(10, 4))
        ctk.CTkLabel(line, text=text, text_color=MUTED, font=self.fonts["label"], height=16).pack(side="left")
        if extra:
            ctk.CTkLabel(line, text=extra, text_color="#7d7d7d", font=self.font(12), height=16).pack(side="left", padx=(6, 0))

    def _build_form(self, title, status, note, heading, title_hint):
        if self.form_frame is not None:
            self.form_frame.destroy()
        self.form_frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        body = ctk.CTkFrame(self.form_frame, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(8, 0))

        # Header: back arrow + heading
        head = ctk.CTkFrame(body, fg_color="transparent")
        head.pack(fill="x")
        self._icon_button(head, "back", "Back", self._close_form, colour=SOFT, size=16).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(head, text=heading, font=self.fonts["heading"], text_color=TEXT).pack(side="left")

        # New item: a box to type or paste the link / text
        self.f_text = None
        if self.form["new"]:
            self._field_label(body, "Link or text")
            self.f_text = ctk.CTkTextbox(body, height=58, fg_color=FIELD, border_width=1, border_color=BORDER,
                                         text_color=TEXT, font=self.font(13), wrap="word", corner_radius=6)
            self.f_text.pack(fill="x")
            self.f_text.bind("<KeyRelease>", lambda e: self._auto_title(), add="+")

        # Title
        self._field_label(body, "Title", None if title_hint else "(optional)")
        self.f_title = ctk.CTkEntry(body, height=36, fg_color=FIELD, border_width=1, border_color=BORDER,
                                    text_color="#ffffff", font=self.fonts["name"], corner_radius=6,
                                    placeholder_text="Give it a name you'll recognise",
                                    placeholder_text_color=FAINT)
        self.f_title.pack(fill="x")
        if title:
            self.f_title.insert(0, title)
        self.f_title_hint = ctk.CTkLabel(body, text="Filled in from the link. Change it if you like." if title_hint else "",
                                         text_color=FAINT, font=self.font(11), anchor="w", height=14)
        if title_hint:
            self.f_title_hint.pack(fill="x", pady=(3, 0))

        # What's being saved (existing items)
        if not self.form["new"]:
            text = self.form["text"]
            where_row = ctk.CTkFrame(body, fg_color=ROW, corner_radius=6, height=38)
            where_row.pack(fill="x", pady=(10, 0))
            where_row.pack_propagate(False)
            self._type_badge(where_row, text, size=24).pack(side="left", padx=(8, 8))
            where = cliptype.short_address(text) if cliptype.detect(text) == "link" else text
            ctk.CTkLabel(where_row, text=fit(where, self.fonts["sub"], FORM_WIDTH - 60), text_color=MUTED,
                         font=self.fonts["sub"], anchor="w").pack(side="left", fill="x", expand=True)

        # Status
        self._field_label(body, "Status")
        self.f_status = ctk.CTkSegmentedButton(
            body, values=list(STATUS_LABELS.values()), height=32, corner_radius=8, font=self.font(13),
            fg_color=FIELD, selected_color=BLUE_BG, selected_hover_color="#26455a",
            unselected_color=FIELD, unselected_hover_color="#333333", text_color=TEXT)
        self.f_status.pack(fill="x")
        self.f_status.set(STATUS_LABELS[status])

        # Tag
        self._field_label(body, "Tag")
        self.f_tags = ctk.CTkFrame(body, fg_color="transparent")
        self.f_tags.pack(fill="x")
        self._draw_form_tags()

        # Note
        self._field_label(body, "Note", "(why are you saving this?)")
        self.f_note = ctk.CTkTextbox(body, fg_color=FIELD, border_width=1, border_color=BORDER, text_color=TEXT,
                                     font=self.font(13), wrap="word", corner_radius=6, height=60)
        self.f_note.pack(fill="both", expand=True)
        if note:
            self.f_note.insert("1.0", note)

        # Footer: [Delete] or hint ......... [Cancel] [Save]
        ctk.CTkFrame(self.form_frame, height=1, fg_color=DIVIDER, corner_radius=0).pack(fill="x", pady=(12, 0))
        foot = ctk.CTkFrame(self.form_frame, fg_color="transparent")
        foot.pack(fill="x", padx=16, pady=(10, 12))
        ctk.CTkButton(foot, text="Save", width=76, height=34, corner_radius=6, fg_color=ACCENT,
                      hover_color="#7fd3ff", text_color="#0b1a24", font=self.font(13, bold=True),
                      command=self._save_form).pack(side="right")
        ctk.CTkButton(foot, text="Cancel", width=76, height=34, corner_radius=6, fg_color=FIELD,
                      hover_color=ROW_HOVER, border_width=1, border_color=BORDER, text_color=TEXT,
                      font=self.font(13), command=self._close_form).pack(side="right", padx=(0, 8))
        if self.form["editing"]:
            self.f_delete = ctk.CTkButton(foot, text="Delete", width=70, height=34, corner_radius=6,
                                          fg_color="transparent", hover_color="#3a2626", text_color=DANGER,
                                          font=self.font(13), command=self._delete_from_form)
            self.f_delete.pack(side="left")
        else:
            ctk.CTkLabel(foot, text="Ctrl+Enter to save", text_color=FAINT, font=self.font(12)).pack(side="left")

    def _draw_form_tags(self):
        """Tag chips that wrap onto new lines, plus "+ New tag"."""
        # If the tag box being replaced has keyboard focus, hand focus to the title first.
        focused = self.focus_get() if not self._focus_elsewhere() else None
        if focused is not None and str(focused).startswith(str(self.f_tags)):
            self.f_title.focus_set()
        for widget in self.f_tags.winfo_children():
            widget.destroy()
        selected = self.form["tag"]
        tags = db.tags(self.conn)[:12]
        if selected and selected not in tags:
            tags.insert(0, selected)  # a tag typed just now, not saved on anything yet

        line, used = None, FORM_WIDTH  # start "full" so the first chip opens a line

        def place(width):
            nonlocal line, used
            if line is None or used + width > FORM_WIDTH:
                line = ctk.CTkFrame(self.f_tags, fg_color="transparent")
                line.pack(fill="x", pady=(0, 6))
                used = 0
            used += width + 6
            return line

        for tag in tags:
            width = self.fonts["chip"].measure(tag) + 26
            chip = ctk.CTkButton(
                place(width), text=tag, width=width, height=28, corner_radius=14, font=self.fonts["chip"],
                fg_color=BLUE_BG if tag == selected else BG, hover_color="#26455a" if tag == selected else ROW_HOVER,
                text_color="#ffffff" if tag == selected else SOFT, border_width=1,
                border_color=ACCENT if tag == selected else BORDER,
                command=lambda t=tag: self._pick_tag(t))
            chip.pack(side="left", padx=(0, 6))

        width = self.fonts["chip"].measure("+ New tag") + 26
        ctk.CTkButton(place(width), text="+ New tag", width=width, height=28, corner_radius=14,
                      font=self.fonts["chip"], fg_color=BG, hover_color=ROW_HOVER, text_color=MUTED,
                      border_width=1, border_color="#4a4a4a", command=self._new_tag_box).pack(side="left")
        self._new_tag_line = line

    def _pick_tag(self, tag):
        self.form["tag"] = None if self.form["tag"] == tag else tag  # click the chosen tag again to clear it
        self._draw_form_tags()

    def _new_tag_box(self):
        """Swap the "+ New tag" chip for a small box to type a tag name into."""
        line = self._new_tag_line
        line.winfo_children()[-1].destroy()
        box = ctk.CTkEntry(line, width=140, height=28, corner_radius=14, fg_color=FIELD, border_width=1,
                           border_color=ACCENT, text_color=TEXT, font=self.fonts["chip"],
                           placeholder_text="Tag name", placeholder_text_color=FAINT)
        box.pack(side="left")
        box.focus_set()
        done = {"value": False}

        def commit(event=None):
            if done["value"]:
                return "break"
            done["value"] = True
            name = " ".join(box.get().split())[:30]
            if name:
                self.form["tag"] = name
            self.after(1, self._draw_form_tags)
            return "break"

        def cancel(event=None):
            done["value"] = True
            self.after(1, self._draw_form_tags)
            return "break"

        box.bind("<Return>", commit)
        box.bind("<Escape>", cancel)
        box.bind("<FocusOut>", commit)

    def _auto_title(self):
        """New item: suggest a title from the link as it's typed, unless you've written your own."""
        text = self.f_text.get("1.0", "end").strip()
        suggestion = cliptype.title_from_url(text) if text else ""
        if self.f_title.get() == self.form["auto_title"]:
            self.f_title.delete(0, "end")
            if suggestion:
                self.f_title.insert(0, suggestion)
            self.form["auto_title"] = suggestion
            if suggestion and cliptype.detect(text) == "link" and self.f_status.get() == "Reference":
                self.f_status.set("To read")

    def _save_form(self):
        form = self.form
        if form is None:
            return
        text = form["text"] if not form["new"] else self.f_text.get("1.0", "end").strip()
        if not text or len(text) > db.MAX_LENGTH:
            self.f_text.configure(border_color=DANGER)  # nothing to save: point at the empty box
            self.f_text.focus_set()
            return
        db.save_item(
            self.conn, text,
            title=self.f_title.get(),
            note=self.f_note.get("1.0", "end").strip(),
            tag=form["tag"],
            status=LABEL_STATUS[self.f_status.get()],
            item_id=None if form["new"] else form["item_id"],
        )
        self.status_filter = "all"
        self._close_form(to="saved")

    def _delete_from_form(self):
        """Delete needs two clicks, so a slip can't lose a saved note."""
        if not self.form["delete_armed"]:
            self.form["delete_armed"] = True
            self.f_delete.configure(text="Click again to delete", width=150, fg_color="#3a2626")

            def disarm(form=self.form):
                if self.form is form and not self._closed:
                    form["delete_armed"] = False
                    self.f_delete.configure(text="Delete", width=70, fg_color="transparent")
            self.after(3000, disarm)
            return
        db.delete(self.conn, self.form["item_id"])
        self._close_form(to="saved")

    def _close_form(self, to=None):
        global LAST_VIEW
        if self.form is None:
            return
        self.view = to or self.form["from"]
        LAST_VIEW = self.view
        self.form = None
        frame, self.form_frame = self.form_frame, None
        self._layout()
        self.search.focus_set()  # move focus out BEFORE the form (which has it) disappears
        self.update_idletasks()
        if frame is not None:
            frame.destroy()
        self.refresh()

    # =====================================================================
    # Actions
    # =====================================================================

    def _copy(self, text):
        pyperclip.copy(text)
        db.save(self.conn, text)  # bump it to the top of the clipboard history
        self.close()              # close; now press Ctrl+V wherever you want

    def _open_link(self, text):
        webbrowser.open(browser_address(text))
        # The browser comes to the front, so the popup closes itself, like clicking away.

    def _mark_done(self, item_id):
        db.set_status(self.conn, item_id, "done")
        self.refresh()

    def _delete(self, item_id):
        db.delete(self.conn, item_id)
        self.refresh()


if __name__ == "__main__":
    # Standalone test: an invisible root window, plus the popup. Closing the popup ends the program.
    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.withdraw()
    Popup(root, on_close=root.destroy)
    root.mainloop()
