"""First-page text and EXIF facts, using outside tools only when present."""

import html
import json
import re
import tempfile
import zipfile
from datetime import date
from pathlib import Path

from . import tools
from .naming import MEDIA_EXTS, make_date

LIMIT = 4000
PLAIN_EXTS = {".txt", ".md", ".csv", ".tsv", ".eml", ".html", ".htm", ".json", ".rtf",
              ".tex", ".bib", ".ris", ".vcf", ".xml", ".log", ".ics", ".org", ".yaml", ".yml"}
ZIP_PARTS = {
    ".docx": ["word/document.xml"],
    ".pptx": ["ppt/slides/slide1.xml"],
    ".odt": ["content.xml"],
    ".odp": ["content.xml"],
}


def strip_xml(text):
    text = re.sub(r"<(?:w:p|a:p|text:p)[ >/]", "\n<", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", html.unescape(text)).strip()


def pdf_text(path):
    if not tools.which("pdftotext"):
        return ""
    out = tools.run(["pdftotext", "-l", "1", "-q", str(path), "-"], timeout=30) or ""
    if out.strip() or not tools.which("ocrmypdf"):
        return out
    # A scan with no text layer: OCR page one into a sidecar, never touching the file.
    with tempfile.TemporaryDirectory() as tmp:
        side = Path(tmp) / "page1.txt"
        tools.run(["ocrmypdf", "-q", "--pages", "1", "--sidecar", str(side),
                   str(path), str(Path(tmp) / "out.pdf")], timeout=180)
        return side.read_text(errors="replace") if side.is_file() else ""


def first_text(path, limit=LIMIT):
    """Text from the start of a file, or "" when it cannot be read cheaply."""
    path = Path(path)
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            return pdf_text(path)[:limit]
        if ext in PLAIN_EXTS:
            with open(path, encoding="utf-8", errors="replace") as f:
                return f.read(limit)
        if ext in ZIP_PARTS:
            with zipfile.ZipFile(path) as z:
                for part in ZIP_PARTS[ext]:
                    if part in z.namelist():
                        return strip_xml(z.read(part).decode("utf-8", "replace"))[:limit]
    except (OSError, zipfile.BadZipFile, ValueError):
        return ""
    return ""


def exif(path):
    """(date or None, has camera data) from exiftool, for photos and videos."""
    path = Path(path)
    if path.suffix.lower() not in MEDIA_EXTS or not tools.which("exiftool"):
        return None, False
    out = tools.run(["exiftool", "-j", "-DateTimeOriginal", "-CreateDate",
                     "-MediaCreateDate", "-Make", "-Model", str(path)], timeout=30)
    try:
        info = json.loads(out)[0] if out else {}
    except (ValueError, IndexError):
        info = {}
    found = None
    for key in ("DateTimeOriginal", "CreateDate", "MediaCreateDate"):
        m = re.match(r"(\d{4}):(\d{2}):(\d{2})", str(info.get(key, "")))
        if m:
            found = make_date(*m.groups())
            if found and found.year > 1970:
                break
            found = None
    camera = bool(str(info.get("Make", "")).strip() or str(info.get("Model", "")).strip())
    return found, camera


def mtime_date(mtime):
    return date.fromtimestamp(mtime)
