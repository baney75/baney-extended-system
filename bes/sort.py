"""`bes sort`: sort each root's Inbox and its drop folders.

Every item is planned first (so --dry-run shows exactly what a real run
would do), then moved, and every move is written to the journal.
Nothing is ever deleted.
"""

import hashlib
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import ai, journal, naming, rules, textread
from .layout import DO, INBOX, KEEP, KNOW, LETGO, ROOM_NAMES

IGNORED = {"desktop.ini", "thumbs.db", "icon\r"}


@dataclass
class Move:
    src: Path
    dest: Path
    room: str
    rule: str
    error: str = ""


class Duplicates:
    """SHA-256 lookups against files already kept in Do, Keep and Know.

    Only files whose size matches are ever hashed, so a big tree stays cheap.
    """

    def __init__(self, root):
        self.root = Path(root)
        self.by_size = None
        self.hashes = {}

    def load(self):
        self.by_size = {}
        for room in (DO, KEEP, KNOW):
            for top, dirs, files in os.walk(self.root / room):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for name in files:
                    p = Path(top) / name
                    if name.startswith(".") or p.is_symlink():
                        continue
                    try:
                        self.by_size.setdefault(p.stat().st_size, []).append(p)
                    except OSError:
                        continue

    def digest(self, path):
        if path not in self.hashes:
            h = hashlib.sha256()
            try:
                with open(path, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
                self.hashes[path] = h.hexdigest()
            except OSError:
                self.hashes[path] = None
        return self.hashes[path]

    def has(self, path, size):
        if self.by_size is None:
            self.load()
        others = [o for o in self.by_size.get(size, []) if o != path]
        if not others:
            return False
        mine = self.digest(path)
        return mine is not None and any(self.digest(o) == mine for o in others)

    def add(self, path, size):
        if self.by_size is None:
            self.load()
        self.by_size.setdefault(size, []).append(path)


def sources(root, cfg):
    """(folder, is_inbox) pairs for one root: its Inbox, then its drop folders."""
    out = [(root / INBOX, True)]
    for drop in cfg.drops if cfg else []:
        if drop.root == root and drop.path != root / INBOX:
            out.append((drop.path, False))
    return out


def gather(entry, now, dups):
    st = entry.stat()
    is_dir = entry.is_dir()
    ext = "" if is_dir else entry.suffix
    parsed = naming.parse_stem(entry.name if is_dir else entry.stem, ext)
    shot_day, camera = (None, False) if is_dir else textread.exif(entry)
    day = parsed.date or shot_day or textread.mtime_date(st.st_mtime)
    if parsed.date:
        since = datetime.combine(parsed.date, datetime.min.time()).timestamp()
    else:
        since = st.st_mtime
    cache = {}

    def text():
        if "text" not in cache:
            cache["text"] = textread.first_text(entry)
        return cache["text"]

    empty_dir = is_dir and not any(not n.startswith(".") for n in os.listdir(entry))
    facts = rules.Facts(
        path=entry,
        is_dir=is_dir,
        size=0 if is_dir else st.st_size,
        age_days=(now - since) / 86400,
        day=day,
        camera=camera,
        empty_dir=empty_dir,
        text=text,
        is_duplicate=lambda: dups.has(entry, st.st_size),
    )
    return facts, parsed


def ai_folder(answer, day):
    return {"Do": DO, "Keep": f"{KEEP}/{day.year}", "Know": KNOW, "Let Go": LETGO}[answer]


def plan(root, cfg=None, now=None, warn=print):
    """Decide every move for one root without touching anything."""
    root = Path(root)
    now = time.time() if now is None else now
    dups = Duplicates(root)
    reserved = set()
    moves = []
    for folder, is_inbox in sources(root, cfg):
        if not folder.is_dir():
            warn(f"skipping {folder}: not a folder")
            continue
        for entry in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
            if entry.name.startswith(".") or entry.name.lower() in IGNORED or entry.is_symlink():
                continue
            try:
                facts, parsed = gather(entry, now, dups)
                dest_dir, rule = rules.classify(facts)
            except OSError as e:
                warn(f"skipping {entry}: {e}")
                continue
            if dest_dir == rules.SKIP:
                continue
            if dest_dir is None and cfg is not None and cfg.ai_command:
                text = "" if facts.is_dir else facts.text()
                answer = ai.ask(cfg.ai_command, entry.name, text)
                if answer:
                    dest_dir, rule = ai_folder(answer, facts.day), f"ai:{answer}"
            if dest_dir is None:
                if not is_inbox:
                    continue  # drop-folder leftovers stay where they are, untouched
                target_dir, room = folder, ROOM_NAMES[INBOX]
            else:
                target_dir = root / dest_dir
                room = ROOM_NAMES[dest_dir.split("/")[0]]
            if facts.is_dir:
                new_name = entry.name  # folders move whole and keep their names
            else:
                new_name = naming.build_name(facts.day, parsed.title, parsed.people, entry.suffix)
            dest = target_dir / new_name
            if dest == entry:
                continue
            dest = journal.unique_path(dest, reserved, src=entry)
            if dest == entry:
                continue
            reserved.add(dest)
            if dest_dir and dest_dir != LETGO and not facts.is_dir:
                dups.add(entry, facts.size)
            moves.append(Move(entry, dest, room, rule))
    return moves


def apply(root, moves):
    """Carry out planned moves and journal each one. Returns the batch id."""
    root = Path(root)
    batch = journal.new_id()
    for m in moves:
        try:
            if journal.taken(m.dest) and not journal.same_file(m.src, m.dest):
                m.dest = journal.unique_path(m.dest)
            made = journal.move(m.src, m.dest)
        except OSError as e:
            m.error = str(e)
            continue
        journal.append(root, {
            "id": journal.new_id(),
            "batch": batch,
            "ts": journal.now_iso(),
            "op": "move",
            "from": journal.rel(root, m.src),
            "to": journal.rel(root, m.dest),
            "rule": m.rule,
            "made_dirs": [journal.rel(root, d) for d in made],
        })
    return batch
