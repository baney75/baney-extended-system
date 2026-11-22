"""Safe moves and the move journal at ROOT/.bes/journal.jsonl.

Paths inside the root are stored relative to it, so a drive keeps a
working journal when it mounts somewhere else. Paths outside the root
(drop folders like ~/Downloads) are stored absolute.
"""

import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_time(text):
    """An ISO 8601 time; a bare time means local time."""
    when = datetime.fromisoformat(text.strip())
    if when.tzinfo is None:
        when = when.astimezone()
    return when


def new_id():
    return uuid.uuid4().hex[:12]


def journal_path(root):
    return Path(root) / ".bes" / "journal.jsonl"


def rel(root, path):
    try:
        return Path(path).relative_to(root).as_posix()
    except ValueError:
        return str(path)


def resolve(root, stored):
    p = Path(stored)
    return p if p.is_absolute() else Path(root) / p


def append(root, entry):
    path = journal_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read(root):
    path = journal_path(root)
    if not path.is_file():
        return []
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue
    return entries


def taken(path, reserved=()):
    return path in reserved or path.exists() or path.is_symlink()


def unique_path(dest, reserved=(), src=None):
    """dest, or dest with " (2)", " (3)" ... so nothing is overwritten.

    A name that src already holds counts as free, so sorting twice never
    renames an item that is already in its place.
    """
    dest = Path(dest)

    def free(p):
        if p in reserved:
            return False
        return not taken(p) or (src is not None and same_file(src, p))

    if free(dest):
        return dest
    stem, suffix = (dest.name, "") if dest.is_dir() and not dest.suffix else (dest.stem, dest.suffix)
    n = 2
    while True:
        candidate = dest.with_name(f"{stem} ({n}){suffix}")
        if free(candidate):
            return candidate
        n += 1


def same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def move(src, dest):
    """Move src to dest without overwriting. Returns the folders it created."""
    src, dest = Path(src), Path(dest)
    made = []
    parent = dest.parent
    missing = []
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for d in reversed(missing):
        d.mkdir()
        made.append(d)
    if taken(dest) and not same_file(src, dest):
        raise FileExistsError(dest)
    try:
        os.rename(src, dest)
    except OSError:
        shutil.move(str(src), str(dest))  # across drives: copy, then remove the source
    return made
