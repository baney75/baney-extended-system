"""`bes index`: write .bes/index.jsonl and refresh the counts in BES.md."""

import json
import os
from datetime import datetime
from pathlib import Path

from . import layout, naming


def entries(root):
    root = Path(root)
    for room in layout.ROOMS:
        for top, dirs, files in os.walk(root / room):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for name in sorted(files):
                p = Path(top) / name
                if name.startswith(".") or p.is_symlink():
                    continue
                st = p.stat()
                parsed = naming.parse_stem(p.stem, p.suffix)
                yield {
                    "path": p.relative_to(root).as_posix(),
                    "room": layout.ROOM_NAMES[room],
                    "date": parsed.date.isoformat() if parsed.date else None,
                    "title": parsed.title,
                    "people": parsed.people,
                    "ext": p.suffix.lower(),
                    "bytes": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds"),
                }


def build(root):
    root = Path(root)
    items = list(entries(root))
    path = root / ".bes" / "index.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    counts = {}
    for item in items:
        counts[item["room"]] = counts.get(item["room"], 0) + 1
    layout.write_bes_md(root, counts)
    return items, counts
