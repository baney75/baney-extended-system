import json
import sys
import unittest
from datetime import datetime, timedelta

from bes import config, journal, sort, undo
from tests.helpers import NOON, TreeTest


def run_sort(root, cfg=None):
    moves = sort.plan(root, cfg, warn=lambda _: None)
    sort.apply(root, moves)
    return moves


class CollisionTest(TreeTest):
    def test_existing_file_gets_suffix_never_overwritten(self):
        self.put("2026-03-04 homework.txt", content="old", folder=self.root / "1 Do")
        self.put("homework.txt", content="new", when=NOON)
        run_sort(self.root)
        do = self.root / "1 Do"
        self.assertEqual((do / "2026-03-04 homework.txt").read_text(), "old")
        self.assertEqual((do / "2026-03-04 homework (2).txt").read_text(), "new")

    def test_two_items_same_target_in_one_run(self):
        self.put("homework 1.txt", content="one", when=NOON)
        self.put("homework_1.txt", content="two", when=NOON)
        self.put("homework__1.txt", content="three", when=NOON)
        run_sort(self.root)
        got = {p.name: p.read_text() for p in (self.root / "1 Do").iterdir()}
        self.assertEqual(got, {"2026-03-04 homework 1.txt": "one",
                               "2026-03-04 homework 1 (2).txt": "two",
                               "2026-03-04 homework 1 (3).txt": "three"})

    def test_sorting_twice_changes_nothing(self):
        self.put("2026-03-04 random.bin", content="first", when=NOON)
        self.put("random.bin", content="second", when=NOON)
        first = run_sort(self.root)
        self.assertEqual([m.dest.name for m in first], ["2026-03-04 random (2).bin"])
        self.assertEqual(run_sort(self.root), [])
        self.assertEqual(run_sort(self.root), [])
        self.assertEqual(sorted(p.name for p in self.inbox.iterdir()),
                         ["2026-03-04 random (2).bin", "2026-03-04 random.bin"])

    def test_suffix_goes_after_people(self):
        self.put("2026-03-04 Voicemail (Mom).m4a", content="a", folder=self.root / "2 Keep" / "2026")
        self.put("Voicemail (Mom).m4a", content="b", when=NOON)
        run_sort(self.root)
        self.assertTrue((self.root / "2 Keep" / "2026" / "2026-03-04 Voicemail (Mom) (2).m4a").is_file())


class DryRunTest(TreeTest):
    def test_dry_run_touches_nothing(self):
        for name in ("SCN_20261121_1650.pdf", "IMG_20250704_120000.jpg", "Chem syllabus.pdf",
                     "W-2 2025.pdf", "homework 3 due.docx", "random.bin"):
            self.put(name, when=NOON)
        self.put("setup.exe", days_old=10)
        (self.inbox / "Essay draft").mkdir()
        self.put("outline.txt", folder=self.inbox / "Essay draft")
        before = self.snapshot()
        moves = sort.plan(self.root, None, warn=lambda _: None)
        self.assertEqual(len(moves), 8)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(journal.journal_path(self.root).exists())

    def test_cli_dry_run_json(self):
        from bes import cli
        self.put("homework 3 due.docx", when=NOON)
        before = self.snapshot()
        out = self.capture(lambda: cli.main(["sort", str(self.root), "--dry-run", "--json"]))
        data = json.loads(out)
        self.assertEqual(data[0]["dry_run"], True)
        self.assertEqual(data[0]["items"], [{
            "from": "0 Inbox/homework 3 due.docx",
            "to": "1 Do/2026-03-04 homework 3 due.docx",
            "room": "Do",
            "name": "2026-03-04 homework 3 due.docx",
            "rule": "do",
        }])
        self.assertEqual(self.snapshot(), before)

    def capture(self, fn):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(fn(), 0)
        return buf.getvalue()


class JournalUndoTest(TreeTest):
    def fill(self):
        self.put("IMG_20250704_120000.jpg")
        self.put("W-2 2025.pdf", when=NOON)
        self.put("homework 3 due.docx", when=NOON)
        self.put("random.bin", when=NOON)
        self.put("setup.exe", days_old=10)

    def test_every_move_is_journaled(self):
        self.fill()
        moves = run_sort(self.root)
        entries = journal.read(self.root)
        self.assertEqual(len(entries), len(moves))
        for e in entries:
            self.assertEqual(e["op"], "move")
            for key in ("id", "batch", "ts", "from", "to", "rule"):
                self.assertIn(key, e)
            self.assertTrue(e["from"].startswith("0 Inbox/"))
            self.assertTrue((self.root / e["to"]).exists())
        self.assertEqual(len({e["batch"] for e in entries}), 1)

    def test_round_trip_restores_tree(self):
        self.fill()
        before = self.snapshot(self.inbox)
        dirs_before = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_dir())
        run_sort(self.root)
        self.assertEqual([p.name for p in self.inbox.iterdir()], ["2026-03-04 random.bin"])
        restored = undo.undo(self.root, last=5, warn=lambda _: None)
        self.assertEqual(len(restored), 5)
        after = self.snapshot(self.inbox)
        self.assertEqual(before, after)  # same names, bytes and modification times
        dirs_after = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_dir())
        self.assertEqual(dirs_before, dirs_after)  # "2 Keep/2025" made by the sort is gone
        ops = [e["op"] for e in journal.read(self.root)]
        self.assertEqual(ops, ["move"] * 5 + ["undo"] * 5)

    def test_undo_twice_does_not_repeat(self):
        self.fill()
        run_sort(self.root)
        self.assertEqual(len(undo.undo(self.root, last=2, warn=lambda _: None)), 2)
        self.assertEqual(len(undo.undo(self.root, last=2, warn=lambda _: None)), 2)
        self.assertEqual(len(undo.undo(self.root, last=10, warn=lambda _: None)), 1)
        self.assertEqual(len(undo.undo(self.root, last=10, warn=lambda _: None)), 0)

    def test_default_undo_is_last_sort_run(self):
        self.put("homework.txt", when=NOON)
        run_sort(self.root)
        self.put("todo list.txt", when=NOON)
        self.put("rsvp.txt", when=NOON)
        run_sort(self.root)
        restored = undo.undo(self.root, warn=lambda _: None)
        self.assertEqual(sorted(t.name for _, t in restored), ["rsvp.txt", "todo list.txt"])
        self.assertTrue((self.root / "1 Do" / "2026-03-04 homework.txt").exists())

    def test_undo_since(self):
        self.put("homework.txt", when=NOON)
        run_sort(self.root)
        lines = journal.journal_path(self.root).read_text().splitlines()
        old = json.loads(lines[0])
        old["ts"] = "2020-01-01T00:00:00+00:00"
        journal.journal_path(self.root).write_text(json.dumps(old) + "\n")
        self.put("todo.txt", when=NOON)
        run_sort(self.root)
        since = datetime.now().astimezone() - timedelta(hours=1)
        restored = undo.undo(self.root, since=since, warn=lambda _: None)
        self.assertEqual([t.name for _, t in restored], ["todo.txt"])

    def test_undo_follows_a_chain_of_moves(self):
        self.put("random.bin", when=NOON)
        run_sort(self.root)  # renamed in place in the Inbox
        script = self.tmp / "ai.py"
        script.write_text("print('Know')\n")
        cfg = config.Config(ai_command=f'"{sys.executable}" "{script}"')
        run_sort(self.root, cfg)  # now moved to Know
        self.assertTrue((self.root / "3 Know" / "2026-03-04 random.bin").exists())
        undo.undo(self.root, last=2, warn=lambda _: None)
        self.assertEqual([p.name for p in self.inbox.iterdir()], ["random.bin"])

    def test_undo_does_not_overwrite(self):
        self.put("homework.txt", content="first", when=NOON)
        run_sort(self.root)
        self.put("homework.txt", content="newcomer", when=NOON, folder=self.inbox)
        undo.undo(self.root, warn=lambda _: None)
        self.assertEqual((self.inbox / "homework.txt").read_text(), "newcomer")
        self.assertEqual((self.inbox / "homework (2).txt").read_text(), "first")


class NeverDeleteTest(TreeTest):
    def test_sort_keeps_every_byte(self):
        names = ["a.crdownload", "empty.txt", "setup.exe", "receipt.pdf", "IMG_1234.jpg",
                 "book.epub", "homework.txt", "random.bin"]
        for n in names:
            self.put(n, content="" if n == "empty.txt" else None, days_old=40)
        self.put("dup.txt", content="kept", folder=self.root / "3 Know")
        self.put("dup copy.txt", content="kept")
        before = sorted(p.read_bytes() for p in self.root.rglob("*") if p.is_file() and ".bes" not in p.parts)
        run_sort(self.root)
        after = sorted(p.read_bytes() for p in self.root.rglob("*")
                       if p.is_file() and ".bes" not in p.parts and p.name != "BES.md")
        before = [b for b in before if not b.startswith(b"# Baney")]
        self.assertEqual(before, after)


class FolderTest(TreeTest):
    def test_folder_moves_whole_and_keeps_name(self):
        proj = self.inbox / "Lab report draft"
        proj.mkdir()
        self.put("notes.txt", folder=proj)
        self.put("data.csv", folder=proj / "raw")
        run_sort(self.root)
        moved = self.root / "1 Do" / "Lab report draft"
        self.assertTrue((moved / "notes.txt").is_file())
        self.assertTrue((moved / "raw" / "data.csv").is_file())

    def test_undecided_folder_stays(self):
        (self.inbox / "Stuff").mkdir()
        self.put("a.bin", folder=self.inbox / "Stuff")
        self.assertEqual(sort.plan(self.root, None, warn=lambda _: None), [])


class DropTest(TreeTest):
    def test_drop_folder_sorts_into_root_and_leaves_leftovers(self):
        downloads = self.tmp / "Downloads"
        self.put("Moby Dick.epub", folder=downloads, when=NOON)
        self.put("unknown.bin", folder=downloads, when=NOON)
        cfg_file = self.tmp / "config.toml"
        cfg_file.write_text(f'roots = ["{self.root}"]\n'
                            f'drops = [{{path = "{downloads}", root = "{self.root}"}}]\n')
        cfg = config.load(cfg_file)
        self.assertEqual(cfg.roots, [self.root])
        moves = run_sort(self.root, cfg)
        self.assertEqual([m.rule for m in moves], ["know:book"])
        self.assertTrue((self.root / "3 Know" / "2026-03-04 Moby Dick.epub").is_file())
        self.assertTrue((downloads / "unknown.bin").is_file())
        entry = journal.read(self.root)[0]
        self.assertEqual(entry["from"], str(downloads / "Moby Dick.epub"))  # absolute outside the root
        self.assertEqual(entry["to"], "3 Know/2026-03-04 Moby Dick.epub")
        undo.undo(self.root, warn=lambda _: None)
        self.assertTrue((downloads / "Moby Dick.epub").is_file())

    def test_missing_config_means_no_drops(self):
        cfg = config.load(self.tmp / "nope.toml")
        self.assertEqual((cfg.roots, cfg.drops, cfg.ai_command), ([], [], ""))


class AiTest(TreeTest):
    def script(self, body):
        path = self.tmp / "ai.py"
        path.write_text(body)
        return config.Config(ai_command=f'"{sys.executable}" "{path}"')

    def test_ai_is_off_by_default(self):
        self.put("random.bin", when=NOON)
        m = sort.plan(self.root, config.Config(), warn=lambda _: None)[0]
        self.assertEqual(m.rule, "stay")

    def test_ai_gets_name_and_text_and_answer_is_used(self):
        self.put("mystery.txt", content="z" * 5000, when=NOON)
        seen = self.tmp / "seen.txt"
        cfg = self.script(f"import sys\nopen({str(seen)!r}, 'w').write(sys.stdin.read())\nprint('  know\\n')\n")
        m = sort.plan(self.root, cfg, warn=lambda _: None)[0]
        self.assertEqual((m.rule, m.dest.parent), ("ai:Know", self.root / "3 Know"))
        sent = seen.read_text()
        self.assertTrue(sent.startswith("mystery.txt\n\n"))
        self.assertEqual(len(sent), len("mystery.txt\n\n") + 2000)

    def test_ai_keep_goes_to_year_and_let_go_works(self):
        self.put("random.bin", when=NOON)
        m = sort.plan(self.root, self.script("print('Keep')"), warn=lambda _: None)[0]
        self.assertEqual(m.dest.parent, self.root / "2 Keep" / "2026")
        m = sort.plan(self.root, self.script("print('Let Go')"), warn=lambda _: None)[0]
        self.assertEqual(m.dest.parent, self.root / "4 Let Go")

    def test_ai_other_answers_leave_item_in_inbox(self):
        self.put("random.bin", when=NOON)
        for body in ("print('I think Know')", "print('Trash')", "print('')",
                     "import sys; sys.exit(3)", "print('Do Keep')"):
            m = sort.plan(self.root, self.script(body), warn=lambda _: None)[0]
            self.assertEqual((m.rule, m.dest.parent), ("stay", self.inbox), body)

    def test_ai_only_sees_leftovers(self):
        self.put("homework.txt", when=NOON)
        m = sort.plan(self.root, self.script("print('Let Go')"), warn=lambda _: None)[0]
        self.assertEqual(m.rule, "do")


if __name__ == "__main__":
    unittest.main()
