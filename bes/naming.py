"""Read dates, titles and people out of file names, and build BES names.

    YYYY-MM-DD Title (Person, Person).ext
"""

import re
from dataclasses import dataclass, field
from datetime import date

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".3gp", ".avi", ".mkv", ".webm", ".mts"}
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".dng",
              ".cr2", ".cr3", ".nef", ".arw", ".raf", ".orf", ".rw2", ".gif", ".webp"}
MEDIA_EXTS = VIDEO_EXTS | PHOTO_EXTS

YMD = r"((?:19|20)\d\d)(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])"
HM = r"(?:[_-]?(\d{2})(\d{2})\d*)?"

# Camera and scanner names that carry a date: (pattern, kind or None).
DATED = [
    (re.compile(r"^SCN[_-]?" + YMD + HM, re.I), "Scan"),
    (re.compile(r"^(?:IMG|PXL|MVIMG|VID)[_-]" + YMD + HM, re.I), None),
    (re.compile(
        r"^Screen ?shot[ _-]*(?:from[ _-]*)?((?:19|20)\d\d)-?(0[1-9]|1[0-2])-?(0[1-9]|[12]\d|3[01])"
        r"(?:\D{1,4}(\d{2})\D?(\d{2})(?:\D?\d{2})?)?", re.I), "Screenshot"),
]
# Camera names with only a counter: IMG_1234, DSC_0042, DSCN0042.
UNDATED = re.compile(r"^(IMG|PXL|DSC[NF_]?|MVIMG|VID|MOV|SCN)[_-]?(\d{3,})", re.I)
ISO = re.compile(
    r"(?<!\d)((?:19|20)\d\d)[-_.](0[1-9]|1[0-2])[-_.](0[1-9]|[12]\d|3[01])(?!\d)")
LEADING_COMPACT = re.compile(r"^" + YMD + r"(?!\d)")
COUNTER = re.compile(r"\s*\((\d+)\)$")
PEOPLE = re.compile(r"\s*\(([^()]*)\)$")
UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
MAX_TITLE = 120


@dataclass
class Parsed:
    date: date | None
    title: str
    people: list = field(default_factory=list)
    kind: str = ""


def make_date(y, m, d):
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def clean_title(text):
    text = UNSAFE.sub(" ", text.replace("_", " "))
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -_.,;")


def kind_for(prefix, ext):
    if ext.lower() in VIDEO_EXTS or prefix.upper() in ("VID", "MOV"):
        return "Video"
    if prefix.upper() == "SCN":
        return "Scan"
    return "Photo"


def parse_stem(stem, ext=""):
    """Split a file name (without extension) into date, title and people."""
    s = stem.strip()
    while COUNTER.search(s):
        s = COUNTER.sub("", s, count=1)
    people = []
    m = PEOPLE.search(s)
    if m and m.group(1).strip():
        people = [p.strip() for p in m.group(1).split(",") if p.strip()]
        s = s[: m.start()]

    for pattern, kind in DATED:
        m = pattern.match(s)
        if not m:
            continue
        found = make_date(m.group(1), m.group(2), m.group(3))
        if found is None:
            continue
        kind = kind or kind_for(s[:3], ext)
        tail = s[m.end():]
        if kind == "Screenshot":
            tail = re.sub(r"(?i)\b[ap]\.?m\.?\b", "", tail)
        words = [kind]
        if m.group(4):
            words.append(m.group(4) + m.group(5))
        title = clean_title(" ".join(words) + " " + clean_title(tail))
        return Parsed(found, title, people, kind)

    m = UNDATED.match(s)
    if m:
        kind = kind_for(m.group(1)[:3], ext)
        title = clean_title(f"{kind} {m.group(2)} {s[m.end():]}")
        return Parsed(None, title, people, kind)

    found = None
    m = ISO.search(s) or LEADING_COMPACT.match(s)
    if m:
        found = make_date(m.group(1), m.group(2), m.group(3))
        if found:
            s = s[: m.start()] + " " + s[m.end():]
    kind = "Screenshot" if re.match(r"(?i)screen ?shot", s) else ""
    return Parsed(found, clean_title(s), people, kind)


def build_name(day, title, people=(), ext=""):
    title = clean_title(title)[:MAX_TITLE].strip() or "Untitled"
    name = f"{day.isoformat()} {title}"
    if people:
        name += " (" + ", ".join(people) + ")"
    return name + ext.lower()
