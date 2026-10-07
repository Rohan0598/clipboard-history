"""
Stage 9: Work out what kind of thing was copied, so the popup can show an icon.

detect(text) returns one of: "link", "email", "number", "code", "text".
The checks run in that order and the first match wins.
"""

import re

LINK = re.compile(r"^(https?://|www\.)\S+$", re.IGNORECASE)
EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")
# Digits plus the separators people use in prices, phone numbers and dates. Must contain a digit.
NUMBER = re.compile(r"^[+\-]?[\d\s,.\-/()]*\d[\d\s,.\-/()]*$")
CODE = re.compile(
    r"[{};]|=>|->|==|!=|</?\w+[^>]*>"                                # symbols and HTML tags
    r"|^\s*(def|class)\s+\w+.*:\s*$"                                 # Python: def foo(): / class Foo:
    r"|^\s*(import\s+[\w.]+\s*$|from\s+[\w.]+\s+import\s)"           # Python imports
    r"|\b(const|let|var)\s+\w+\s*="                                  # JavaScript variables
    r"|\bfunction\s*\w*\s*\("                                        # JavaScript functions
    r"|^\s*(python3?|pip3?|git|npm|npx|node|cd|ls|dir|docker|curl|cls)\b"  # commands at the start
    r"|^\s*(select\s+(\*|[\w.]+(\s*,\s*[\w.]+)*)\s+from|insert\s+into|update\s+\w+\s+set|delete\s+from|create\s+(table|index|database))\b",  # SQL
    re.IGNORECASE | re.MULTILINE,
)

NAMES = {"link": "Link", "email": "Email", "number": "Number", "code": "Code", "text": "Text"}

# (badge background, icon colour) for the dark theme
COLORS = {
    "link":   ("#1f3848", "#6cc8ff"),
    "email":  ("#382e4a", "#c9a7ff"),
    "code":   ("#43342a", "#ffb86b"),
    "number": ("#1f3d37", "#6fdcc3"),
    "text":   ("#323232", "#c4c4c4"),
}


def detect(text):
    t = text.strip()
    if LINK.match(t):
        return "link"
    if EMAIL.match(t):
        return "email"
    if NUMBER.match(t):
        return "number"
    if CODE.search(t):
        return "code"
    return "text"


# ---------- Stage 10: titles and short addresses for saved links ----------

from urllib.parse import urlparse

# Words that should keep their capitals when a title is made from a link.
_KEEP_CASE = {
    "ai": "AI", "ml": "ML", "llm": "LLM", "llms": "LLMs", "chatgpt": "ChatGPT", "openai": "OpenAI",
    "ui": "UI", "ux": "UX", "api": "API", "apis": "APIs", "pm": "PM", "pms": "PMs", "prd": "PRD",
    "seo": "SEO", "saas": "SaaS", "b2b": "B2B", "b2c": "B2C", "okr": "OKR", "okrs": "OKRs",
    "kpi": "KPI", "kpis": "KPIs", "sql": "SQL", "css": "CSS", "html": "HTML", "ios": "iOS",
    "github": "GitHub", "youtube": "YouTube", "linkedin": "LinkedIn", "javascript": "JavaScript",
    "python": "Python", "figma": "Figma", "google": "Google",
}


def _parse(url):
    return urlparse(url.strip() if "://" in url else "https://" + url.strip())


def short_address(url):
    """theproductspace.in/blogs/... without https://, www. or a trailing slash."""
    p = _parse(url)
    host = p.netloc.lower().removeprefix("www.")
    return (host + p.path).rstrip("/")


def title_from_url(url):
    """
    Turn a link into a readable title, without going online:
      .../45-chatgpt-prompts-for-product-managers  ->  "45 ChatGPT prompts for product managers"
    Short or ID-like endings (a profile name, ?id=123) fall back to the site name.
    """
    if detect(url) != "link":
        return ""
    p = _parse(url)
    host = p.netloc.lower().removeprefix("www.")
    parts = [part for part in p.path.split("/") if part]
    slug = re.sub(r"\.(html?|php|aspx?)$", "", parts[-1], flags=re.IGNORECASE) if parts else ""
    words = [w for w in re.split(r"[-_+]+|%20", slug) if w]
    # Blogs like Medium end the address in a random ID ("...-teams-3f9a8c2b1d7e"): drop it.
    if words and re.fullmatch(r"[0-9a-f]{8,}", words[-1].lower()) and re.search(r"\d", words[-1]):
        words = words[:-1]
    letters = [w for w in words if re.search(r"[a-zA-Z]", w)]
    if len(words) < 3 or len(letters) < 2 or any(len(w) > 25 for w in words):
        return host
    words = [_KEEP_CASE.get(w.lower(), w.lower()) for w in words]
    title = " ".join(words)
    return title[0].upper() + title[1:]
