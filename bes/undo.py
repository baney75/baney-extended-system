"""`bes undo`: reverse journaled moves, newest first, and journal the undo."""

from pathlib import Path

from . import journal
from .journal import parse_time


def pending_moves(root):
    entries = journal.read(root)
    undone = {e.get("undoes") for e in entries if e.get("op") == "undo"}
    return [e for e in entries if e.get("op") == "move" and e.get("id") not in undone]


def select(moves, last=None, since=None):
    """By count, by time, or (with neither) the most recent sort run."""
    if since is not None:
        return [m for m in moves if parse_time(m["ts"]) >= since]
    if last is not None:
        return moves[-last:] if last > 0 else []
    if not moves:
        return []
    batch = moves[-1].get("batch")
    return [m for m in moves if m.get("batch") == batch]


def undo(root, last=None, since=None, warn=print):
    """Returns a list of (from, to) pairs that were restored."""
    root = Path(root)
    restored = []
    for m in reversed(select(pending_moves(root), last, since)):
        current = journal.resolve(root, m["to"])
        original = journal.resolve(root, m["from"])
        if not current.exists() and not current.is_symlink():
            warn(f"cannot undo {m['to']}: it is no longer there")
            continue
        target = journal.unique_path(original, src=current)
        try:
            journal.move(current, target)
        except OSError as e:
            warn(f"cannot undo {m['to']}: {e}")
            continue
        journal.append(root, {
            "id": journal.new_id(),
            "ts": journal.now_iso(),
            "op": "undo",
            "undoes": m["id"],
            "from": journal.rel(root, current),
            "to": journal.rel(root, target),
        })
        for d in reversed(m.get("made_dirs", [])):
            try:
                journal.resolve(root, d).rmdir()  # only if the sort made it and it is empty
            except OSError:
                pass
        restored.append((current, target))
    return restored
