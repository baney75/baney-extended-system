"""`bes letgo`: list what has sat in Let Go, and empty it only on a typed yes.

This is the only code in bes that deletes anything.
"""

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from . import journal
from .layout import LETGO


@dataclass
class Held:
    path: Path
    days: float
    bytes: int


def entered(root):
    """When each Let Go item arrived, from the journal."""
    times = {}
    for e in journal.read(root):
        if e.get("op") in ("move", "undo") and str(e.get("to", "")).startswith(LETGO + "/"):
            try:
                times[str(journal.resolve(root, e["to"]))] = journal.parse_time(e["ts"]).timestamp()
            except (KeyError, ValueError):
                continue
    return times


def size_of(path):
    if path.is_file():
        return path.stat().st_size
    total = 0
    for p in path.rglob("*"):
        if p.is_file() and not p.is_symlink():
            total += p.stat().st_size
    return total


def held(root, older_than=90, now=None):
    root = Path(root)
    now = time.time() if now is None else now
    arrived = entered(root)
    items = []
    folder = root / LETGO
    if not folder.is_dir():
        return items
    for p in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if p.name.startswith("."):
            continue
        since = arrived.get(str(p), p.lstat().st_mtime)
        days = (now - since) / 86400
        if days >= older_than:
            items.append(Held(p, days, size_of(p)))
    return items


def describe(root, items):
    lines = []
    for h in items:
        lines.append(f"{h.days:6.0f} days  {h.bytes:>12,} bytes  {journal.rel(root, h.path)}")
    return lines


def empty(root, items, ask=input, say=print):
    """Delete the listed items after the person types yes. Returns the count deleted."""
    root = Path(root)
    if not items:
        say("Nothing in Let Go is old enough to remove.")
        return 0
    say(f"These {len(items)} items will be deleted for good:")
    for line in describe(root, items):
        say("  " + line)
    try:
        answer = ask("Type yes to delete them: ")
    except EOFError:
        answer = ""
    if answer.strip() != "yes":
        say("Nothing deleted.")
        return 0
    count = 0
    for h in items:
        try:
            if h.path.is_dir() and not h.path.is_symlink():
                shutil.rmtree(h.path)
            else:
                h.path.unlink()
        except OSError as e:
            say(f"could not delete {h.path}: {e}")
            continue
        journal.append(root, {
            "id": journal.new_id(),
            "ts": journal.now_iso(),
            "op": "delete",
            "path": journal.rel(root, h.path),
            "bytes": h.bytes,
        })
        count += 1
    say(f"Deleted {count} items.")
    return count
