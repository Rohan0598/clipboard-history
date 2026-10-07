"""
Stage 10: every icon the app uses, drawn in code (no image files, looks the same on
every Windows version).

  make_tray_image()     the tray / .exe icon
  type_image(kind)      link / email / code / number / text badges in the popup
  ctk_icon(name, ...)   small interface icons: search, pencil, open, check, back, plus

Icons are drawn big on a 24x24 grid scaled up 8x, then shrunk, which smooths the edges.
"""

from PIL import Image, ImageDraw

S = 8            # drawing scale: 1 grid unit = 8 pixels
BIG = 24 * S     # 192 px drawing canvas
OUT = 48         # size of the finished image (customtkinter shrinks it further on screen)


def make_tray_image(paused=False):
    """Draw a small clipboard icon in code, so we don't need an image file. Grey = paused."""
    board, clip = ((140, 140, 140), (100, 100, 100)) if paused else ((58, 123, 213), (40, 90, 160))
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((10, 8, 54, 60), radius=8, fill=board)
    d.rounded_rectangle((22, 3, 42, 15), radius=4, fill=clip)
    for y in (26, 36, 46):
        d.rounded_rectangle((18, y, 46, y + 4), radius=2, fill="white")   # text lines
    return img


# ---------- helpers ----------

def _p(*points):
    """Grid coordinates -> pixel coordinates."""
    return [(x * S, y * S) for x, y in points]


def _box(x0, y0, x1, y1):
    return (x0 * S, y0 * S, x1 * S, y1 * S)


def _line(d, points, color, width=2.2):
    w = round(width * S)
    d.line(_p(*points), fill=color, width=w, joint="curve")
    r = w / 2  # round the two ends
    for x, y in (points[0], points[-1]):
        d.ellipse((x * S - r, y * S - r, x * S + r, y * S + r), fill=color)


def _finish(img):
    return img.resize((OUT, OUT), Image.LANCZOS)


# ---------- the five type icons ----------

def _draw_link(color):
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = round(2.2 * S)
    # Two overlapping rounded "chain links", drawn level, then the whole thing is turned 45 degrees.
    d.rounded_rectangle(_box(2.5, 8.5, 14.5, 15.5), radius=3.5 * S, outline=color, width=w)
    d.rounded_rectangle(_box(9.5, 8.5, 21.5, 15.5), radius=3.5 * S, outline=color, width=w)
    return img.rotate(45, resample=Image.BICUBIC)


def _draw_email(color):
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(_box(3.5, 5.5, 20.5, 18.5), radius=2 * S, outline=color, width=round(2.2 * S))
    _line(d, [(4.5, 7.5), (12, 13), (19.5, 7.5)], color)
    return img


def _draw_code(color):
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    left = [(8.5, 4), (6.8, 4.5), (6, 6.5), (6, 9.5), (5.3, 11.3), (4, 12),
            (5.3, 12.7), (6, 14.5), (6, 17.5), (6.8, 19.5), (8.5, 20)]
    _line(d, left, color)
    _line(d, [(24 - x, y) for x, y in left], color)   # mirror image = the closing brace
    return img


def _draw_number(color):
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _line(d, [(5, 9.5), (19, 9.5)], color)
    _line(d, [(5, 14.5), (19, 14.5)], color)
    _line(d, [(10, 4.5), (8.5, 19.5)], color)
    _line(d, [(15.5, 4.5), (14, 19.5)], color)
    return img


def _draw_text(color):
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.pieslice(_box(5, 4.5, 21, 13), start=90, end=270, fill=color)   # the filled bowl of the ¶
    _line(d, [(13, 4.5), (13, 19.5)], color)
    _line(d, [(17, 4.5), (17, 19.5)], color)
    _line(d, [(12, 4.5), (19, 4.5)], color)
    return img


# ---------- interface icons ----------

def _draw_search(color):
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse(_box(4.5, 4.5, 17.5, 17.5), outline=color, width=round(2 * S))
    _line(d, [(16, 16), (20.5, 20.5)], color, width=2)
    return img


def _draw_pencil(color):
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _line(d, [(4, 20), (4, 16), (15, 5), (19, 9), (8, 20), (4, 20)], color, width=2)
    _line(d, [(13, 7), (17, 11)], color, width=2)
    return img


def _draw_open(color):
    """Open in browser: an arrow leaving a box."""
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _line(d, [(14, 4), (20, 4), (20, 10)], color, width=2)
    _line(d, [(20, 4), (11, 13)], color, width=2)
    _line(d, [(18, 14), (18, 19.5), (4.5, 19.5), (4.5, 6), (10, 6)], color, width=2)
    return img


def _draw_check(color):
    """Mark as read: a tick in a circle."""
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse(_box(3.5, 3.5, 20.5, 20.5), outline=color, width=round(2 * S))
    _line(d, [(8.3, 12.2), (10.9, 14.7), (15.8, 9.6)], color, width=2.1)
    return img


def _draw_back(color):
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _line(d, [(15, 5), (8, 12), (15, 19)], color, width=2.3)
    return img


def _draw_plus(color):
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _line(d, [(12, 5), (12, 19)], color, width=2.4)
    _line(d, [(5, 12), (19, 12)], color, width=2.4)
    return img


_DRAW = {"link": _draw_link, "email": _draw_email, "code": _draw_code,
         "number": _draw_number, "text": _draw_text,
         "search": _draw_search, "pencil": _draw_pencil, "open": _draw_open,
         "check": _draw_check, "back": _draw_back, "plus": _draw_plus}


def pil_icon(name, color):
    """The icon as a plain Pillow image (used for testing and previews)."""
    return _finish(_DRAW[name](color))


# customtkinter images are cached: building them once is much faster than on every redraw.
_cache = {}


def ctk_icon(name, color, size):
    import customtkinter as ctk  # imported here so build.py can use this file without it
    key = (name, color, size)
    if key not in _cache:
        img = pil_icon(name, color)
        _cache[key] = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    return _cache[key]
