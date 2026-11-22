"""The `bes` command."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import __version__, autostart, cite, config, index, journal, layout, letgo, sort, undo


def warn(message):
    print(f"bes: {message}", file=sys.stderr)


def pick_root(arg, cfg):
    """The ROOT argument, else the current folder if it is a root, else the first configured root."""
    if arg:
        root = config.expand(arg)
    elif layout.is_root(Path.cwd()):
        root = Path.cwd().resolve()
    elif cfg.roots:
        root = cfg.roots[0]
    else:
        raise SystemExit("bes: no ROOT given and no roots in the config")
    if not layout.is_root(root):
        raise SystemExit(f"bes: {root} is not a BES root. Run: bes init {root}")
    return root


def cmd_init(args, cfg):
    root, made = layout.init_root(args.root)
    print(f"BES root ready at {root}")
    for rel in made:
        print(f"  made {rel}")
    if root not in cfg.roots:
        print(f"To sort it on a timer, add it to {cfg.path}:  roots = [\"{root}\"]")
    return 0


def cmd_sort(args, cfg):
    roots = [config.expand(r) for r in args.roots] or list(cfg.roots)
    if not roots:
        warn("no roots: pass a ROOT or set roots in " + str(cfg.path))
        return 2
    report, status = [], 0
    for root in dict.fromkeys(roots):
        if not layout.is_root(root):
            warn(f"{root} is not a BES root. Run: bes init {root}")
            status = 1
            continue
        moves = sort.plan(root, cfg, warn=warn)
        if not args.dry_run:
            sort.apply(root, moves)
        items = [{
            "from": journal.rel(root, m.src),
            "to": journal.rel(root, m.dest),
            "room": m.room,
            "name": m.dest.name,
            "rule": m.rule,
            **({"error": m.error} if m.error else {}),
        } for m in moves]
        if any(m.error for m in moves):
            status = 1
        report.append({"root": str(root), "dry_run": args.dry_run, "items": items})
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return status
    for r in report:
        verb = "would move" if args.dry_run else "moved"
        print(f"{r['root']}: {verb} {len(r['items'])} items")
        for it in r["items"]:
            line = f"  {it['room']:<7} {it['from']}  ->  {it['to']}  [{it['rule']}]"
            print(line + (f"  ERROR {it['error']}" if "error" in it else ""))
    return status


def cmd_undo(args, cfg):
    root = pick_root(args.root, cfg)
    since = journal.parse_time(args.since) if args.since else None
    restored = undo.undo(root, last=args.last, since=since, warn=warn)
    for current, target in restored:
        print(f"  {journal.rel(root, current)}  ->  {journal.rel(root, target)}")
    print(f"Undid {len(restored)} moves.")
    return 0


def cmd_letgo(args, cfg):
    root = pick_root(args.root, cfg)
    items = letgo.held(root, args.older_than)
    if args.empty:
        letgo.empty(root, items)
        return 0
    if not items:
        print(f"Nothing in Let Go is older than {args.older_than} days.")
        return 0
    print(f"In Let Go for {args.older_than} days or more:")
    for line in letgo.describe(root, items):
        print("  " + line)
    print("Run with --empty to delete them (you will be asked first).")
    return 0


def cmd_index(args, cfg):
    root = pick_root(args.root, cfg)
    items, counts = index.build(root)
    print(f"Indexed {len(items)} items in {root / '.bes' / 'index.jsonl'}")
    for room in layout.ROOMS:
        name = layout.ROOM_NAMES[room]
        print(f"  {name:<7} {counts.get(name, 0)}")
    return 0


def cmd_cite(args, cfg):
    try:
        meta = cite.lookup(args.url)
    except OSError as e:
        warn(f"could not read {args.url}: {e}")
        return 1
    today = date.today()
    if args.root:
        root = config.expand(args.root)
        if not layout.is_root(root):
            raise SystemExit(f"bes: {root} is not a BES root. Run: bes init {root}")
        path = cite.write(root, meta, today, args.subject or "")
        print(f"wrote {path}")
    else:
        sys.stdout.write(cite.card(meta, today, args.subject or ""))
    return 0


def cmd_autostart(args, cfg):
    if args.remove:
        autostart.remove(enable=not args.no_enable)
    else:
        if not cfg.roots:
            warn(f"no roots in {cfg.path}; the timer will have nothing to sort until you add some")
        autostart.install(enable=not args.no_enable)
    return 0


def parser():
    p = argparse.ArgumentParser(prog="bes", description="The Baney Extended System: Do, Keep, Know, Let Go.")
    p.add_argument("--version", action="version", version=f"bes {__version__}")
    sub = p.add_subparsers(dest="command", metavar="COMMAND")

    s = sub.add_parser("init", help="make the four rooms and BES.md in ROOT")
    s.add_argument("root")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("sort", help="sort each Inbox and drop folder")
    s.add_argument("roots", nargs="*", metavar="ROOT")
    s.add_argument("--dry-run", action="store_true", help="show the plan, move nothing")
    s.add_argument("--json", action="store_true", help="print the plan as JSON")
    s.set_defaults(func=cmd_sort)

    s = sub.add_parser("undo", help="reverse moves from the journal (default: the last sort)")
    s.add_argument("root", nargs="?")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--last", type=int, metavar="N", help="undo the last N moves")
    g.add_argument("--since", metavar="ISO", help="undo every move at or after this time")
    s.set_defaults(func=cmd_undo)

    s = sub.add_parser("letgo", help="list Let Go items, or empty them with --empty")
    s.add_argument("root", nargs="?")
    s.add_argument("--older-than", type=float, default=90, metavar="DAYS")
    s.add_argument("--empty", action="store_true", help="delete them after you type yes")
    s.set_defaults(func=cmd_letgo)

    s = sub.add_parser("index", help="write .bes/index.jsonl and refresh BES.md")
    s.add_argument("root", nargs="?")
    s.set_defaults(func=cmd_index)

    s = sub.add_parser("cite", help="write a citation card for a URL")
    s.add_argument("url")
    s.add_argument("--root", help="write the card to ROOT/3 Know/Citations (else print it)")
    s.add_argument("--subject", help="subject name, saved in the card's front matter")
    s.set_defaults(func=cmd_cite)

    s = sub.add_parser("autostart", help="run bes sort every 15 minutes (systemd or launchd)")
    s.add_argument("--remove", action="store_true", help="turn it off and remove the files")
    s.add_argument("--no-enable", action="store_true", help="write or remove files only")
    s.set_defaults(func=cmd_autostart)
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 0
    try:
        cfg = config.load()
    except (OSError, ValueError) as e:
        warn(f"cannot read config: {e}")
        return 2
    return args.func(args, cfg)
