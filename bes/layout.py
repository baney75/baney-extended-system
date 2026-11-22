"""The rooms on disk, `bes init`, and the BES.md description."""

import re
from datetime import datetime
from pathlib import Path

INBOX = "0 Inbox"
DO = "1 Do"
KEEP = "2 Keep"
KNOW = "3 Know"
LETGO = "4 Let Go"
ROOMS = [INBOX, DO, KEEP, KNOW, LETGO]
RECORDS = KEEP + "/Records"
CITATIONS = KNOW + "/Citations"
ROOM_NAMES = {INBOX: "Inbox", DO: "Do", KEEP: "Keep", KNOW: "Know", LETGO: "Let Go"}

COUNTS_START = "<!-- bes:counts:start -->"
COUNTS_END = "<!-- bes:counts:end -->"

BES_MD = """\
# Baney Extended System

This folder is sorted by the Baney Extended System (BES).

Everything you keep is asking you to do something, keep it, know it, or let it
go. The `bes` command sorts it for you and you only correct it.

## The four rooms

| Folder | Room | What goes here | Mark |
| --- | --- | --- | --- |
| `0 Inbox/` | Inbox | Only what the machine could not decide. | (none) |
| `1 Do/` | Do | Anything that asks something of you: a reply, a bill, a form, an assignment, a project you are making. | `>` |
| `2 Keep/` | Keep | Your story and your records: photos, letters, voicemails, texts, journals, receipts, IDs, finished work. | `<` |
| `3 Know/` | Know | The world's knowledge you gathered: books, papers, class material, articles, videos, citations. | `=` |
| `4 Let Go/` | Let Go | Everything else. Held for a season, emptied only when you say. | `x` |

Rooms are verbs, not subjects. A chemistry handout is in Know, and the lab
report you owe is in Do. When the report is graded it moves to Keep.

## Inside the rooms

At most one more level:

- `1 Do/`: loose items, plus one folder per work you are making (`1 Do/Six Actual/`).
- `2 Keep/`: `Records/` (identity, money, health, home, school, legal) and one folder per year (`2 Keep/2026/`).
- `3 Know/`: one folder per subject you name, plus `Citations/`.
- `4 Let Go/`: flat.

## Names

    YYYY-MM-DD Title (Person, Person).ext

The date is when the thing entered your life: the event, the scan, the
message, or the due date for something in Do. People go in parentheses when
they matter. A name collision gets ` (2)` appended, never an overwrite.

## Machine files

- `.bes/index.jsonl`: one JSON object per item (path, room, date, title,
  people, ext, bytes, mtime). It is derived; rebuild it with `bes index`.
- `.bes/journal.jsonl`: every move `bes` made, so `bes undo` can reverse it.

## For AI agents

- Folders and names are the source of truth. The index is only a cache.
- Never delete. Move unwanted items to `4 Let Go/`. Only a person empties it,
  with `bes letgo --empty`.
- To file something, move it into a room and name it by the rule above.
- Read `.bes/index.jsonl` for a fast list of everything here.

{counts_start}
{counts}
{counts_end}
"""


def is_root(path):
    return (Path(path) / ".bes").is_dir()


def room_of(rel):
    """Room name for a path relative to the root, or None."""
    first = Path(rel).parts[0] if Path(rel).parts else ""
    return ROOM_NAMES.get(first)


def counts_block(counts):
    if not counts:
        return "Run `bes index` to count the items in each room."
    when = datetime.now().astimezone().isoformat(timespec="seconds")
    lines = ["## Items per room", "", "| Room | Items |", "| --- | --- |"]
    for room in ROOMS:
        lines.append(f"| {ROOM_NAMES[room]} | {counts.get(ROOM_NAMES[room], 0)} |")
    lines += ["", f"Counted {when} by `bes index`."]
    return "\n".join(lines)


def write_bes_md(root, counts=None):
    """Write BES.md. Only the counts block changes between runs."""
    path = Path(root) / "BES.md"
    block = counts_block(counts)
    if path.is_file() and counts is not None:
        text = path.read_text(encoding="utf-8")
        pattern = re.compile(re.escape(COUNTS_START) + ".*?" + re.escape(COUNTS_END), re.S)
        if pattern.search(text):
            new = pattern.sub(lambda _: f"{COUNTS_START}\n{block}\n{COUNTS_END}", text)
            path.write_text(new, encoding="utf-8")
            return path
    path.write_text(
        BES_MD.format(counts_start=COUNTS_START, counts=block, counts_end=COUNTS_END),
        encoding="utf-8",
    )
    return path


def init_root(root):
    root = Path(root).expanduser().resolve()
    made = []
    for rel in ROOMS + [RECORDS, CITATIONS, ".bes"]:
        d = root / rel
        if not d.is_dir():
            d.mkdir(parents=True, exist_ok=True)
            made.append(rel)
    if not (root / "BES.md").is_file():
        write_bes_md(root)
        made.append("BES.md")
    return root, made
