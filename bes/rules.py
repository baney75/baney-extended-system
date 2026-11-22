"""The sorting rules from SPEC.md, in order. The first match wins.

1. Let Go: partial downloads, empty files, duplicates, old installers, old screenshots.
2. Keep/Records: record words in the name or first-page text.
3. Keep/<year>: camera media, voicemails, recordings, journals, letters, texts.
4. Know: books, papers, slides, lecture notes, syllabi, citation cards.
5. Do: words that ask something of you.
6. Otherwise the item stays where it is.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

from .layout import CITATIONS, DO, KEEP, KNOW, LETGO, RECORDS
from .naming import MEDIA_EXTS

SKIP = "skip"  # leave the item alone entirely this run

PARTIAL_EXTS = {".crdownload", ".part", ".partial", ".download", ".tmp", ".temp"}
INSTALLER_EXTS = {".dmg", ".exe", ".msi", ".pkg", ".deb", ".appimage"}
BOOK_EXTS = {".epub", ".mobi", ".azw", ".azw3"}
SLIDE_EXTS = {".ppt", ".pptx", ".key", ".odp"}
CITATION_EXTS = {".bib", ".ris"}
RECORDING_EXTS = {".amr", ".3ga"}
HEIC_EXTS = {".heic", ".heif"}

PARTIAL_GRACE_DAYS = 1  # a younger partial download may still be downloading
INSTALLER_DAYS = 7
SCREENSHOT_DAYS = 30


def words(*alternatives):
    """Match whole words; underscores, dashes and dots count as separators."""
    body = "|".join(a.replace(" ", r"[\s_.-]+") for a in alternatives)
    return re.compile(r"(?<![a-z0-9])(?:" + body + r")(?![a-z0-9])", re.I)


RECORDS_WORDS = words(
    "receipts?", "invoices?", "statements?", "tax", "taxes", "w-?2s?", "1099s?", "1098s?",
    "leases?", "deeds?", "titles?", "insurance", "polic(?:y|ies)", "passports?",
    "licen[cs]es?", "birth certificates?", "social security", "medical", "prescriptions?",
    "diplomas?", "transcripts?", "warrant(?:y|ies)", "contracts?",
)
PERSONAL_WORDS = words(
    "voicemails?", "voice memos?", "voice notes?", "recordings?", "journals?", "diary",
    "diaries", "letters?", "messages", "texts", "sms", "imessages?", "call logs?",
    "call history", "chat export",
)
CAMERA_NAME = re.compile(r"^(?:IMG|PXL|DSC|MVIMG|VID)", re.I)
CLASS_WORDS = words("lectures?", "slides?", "syllabus", "syllabi", "class notes",
                    "course notes")
DOI = re.compile(r"(?<![0-9])10\.\d{4,9}[/_][^\s]+")
ARXIV = re.compile(r"(?i)arxiv[:\s_-]*\d{4}\.\d{4,5}|^\d{4}\.\d{4,5}(?:v\d+)?$")
DO_WORDS = words(
    "forms?", "applications?", "assignments?", "homework", "due", "deadlines?", "drafts?",
    "todo", "to-?do", "sign", "rsvp",
)


@dataclass
class Facts:
    """What the rules need to know about one Inbox or drop-folder item."""

    path: Path
    is_dir: bool
    size: int
    age_days: float  # since the name date if any, else since the last change
    day: date  # the item's date: name, then EXIF, then modification time
    camera: bool = False  # EXIF names a camera make or model
    empty_dir: bool = False
    text: Callable[[], str] = field(default=lambda: "")
    is_duplicate: Callable[[], bool] = field(default=lambda: False)

    @property
    def name(self):
        return self.path.name

    @property
    def ext(self):
        return "" if self.is_dir else self.path.suffix.lower()

    @property
    def stem(self):
        return self.path.name if self.is_dir else self.path.stem


def classify(f):
    """Return (destination folder relative to the root, rule), or (None, "stay")."""
    name, ext = f.name, f.ext

    # 1. Let Go
    if ext in PARTIAL_EXTS:
        if f.age_days < PARTIAL_GRACE_DAYS:
            return SKIP, "partial-in-progress"
        return LETGO, "letgo:partial"
    if f.empty_dir or (not f.is_dir and f.size == 0):
        return LETGO, "letgo:empty"
    if not f.is_dir and f.is_duplicate():
        return LETGO, "letgo:duplicate"
    if ext in INSTALLER_EXTS and f.age_days > INSTALLER_DAYS:
        return LETGO, "letgo:installer"
    if re.match(r"(?i)screen ?shot", name) and f.age_days > SCREENSHOT_DAYS:
        return LETGO, "letgo:screenshot"

    text = "" if f.is_dir else f.text()

    # 2. Keep/Records
    if RECORDS_WORDS.search(f.stem) or RECORDS_WORDS.search(text):
        return RECORDS, "keep:records"

    # 3. Keep/<year>
    year = f"{KEEP}/{f.day.year}"
    if not f.is_dir and (CAMERA_NAME.match(name) or ext in HEIC_EXTS
                         or (f.camera and ext in MEDIA_EXTS)):
        return year, "keep:media"
    if ext in RECORDING_EXTS or PERSONAL_WORDS.search(f.stem):
        return year, "keep:personal"

    # 4. Know
    if ext in BOOK_EXTS:
        return KNOW, "know:book"
    if ext in CITATION_EXTS or (ext == ".md" and "## Citations" in text and "url:" in text):
        return CITATIONS, "know:citation"
    if DOI.search(name) or ARXIV.search(f.stem) or DOI.search(text) or ARXIV.search(text):
        return KNOW, "know:paper"
    if ext in SLIDE_EXTS or CLASS_WORDS.search(f.stem) or re.search(r"(?i)\bsyllabus\b", text):
        return KNOW, "know:class"

    # 5. Do
    if DO_WORDS.search(f.stem) or DO_WORDS.search(text):
        return DO, "do"

    # 6. Stay
    return None, "stay"
