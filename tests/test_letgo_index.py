import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

from bes import index, journal, letgo
from tests.helpers import NOON, TreeTest

REPO = Path(__file__).resolve().parent.parent


class LetGoTest(TreeTest):
    def setUp(self):
        super().setUp()
        self.held_dir = self.root / "4 Let Go"
        self.old = self.put("2026-01-01 setup.exe", folder=self.held_dir, days_old=120)
        self.young = self.put("2026-11-01 old.tmp", folder=self.held_dir, days_old=5)
        (self.held_dir / "Old folder").mkdir()
        self.put("inner.txt", folder=self.held_dir / "Old folder", days_old=200)
        stamp = time.time() - 200 * 86400
        os.utime(self.held_dir / "Old folder", (stamp, stamp))

    def names(self, items):
        return [h.path.name for h in items]

    def test_lists_only_old_items(self):
        self.assertEqual(self.names(letgo.held(self.root, 90)), ["2026-01-01 setup.exe", "Old folder"])
        self.assertEqual(len(letgo.held(self.root, 0)), 3)

    def test_journal_arrival_time_wins_over_mtime(self):
        journal.append(self.root, {"id": "x", "ts": journal.now_iso(), "op": "move",
                                   "from": "0 Inbox/setup.exe", "to": "4 Let Go/2026-01-01 setup.exe"})
        self.assertEqual(self.names(letgo.held(self.root, 90)), ["Old folder"])

    def test_empty_needs_exact_yes(self):
        items = letgo.held(self.root, 90)
        for answer in ("", "y", "YES", "no", "yes please"):
            n = letgo.empty(self.root, items, ask=lambda _: answer, say=lambda _: None)
            self.assertEqual(n, 0, answer)
            self.assertTrue(self.old.exists())

    def test_empty_on_end_of_input_deletes_nothing(self):
        def eof(_):
            raise EOFError
        self.assertEqual(letgo.empty(self.root, letgo.held(self.root, 90), ask=eof, say=lambda _: None), 0)
        self.assertTrue(self.old.exists())

    def test_empty_with_yes_deletes_listed_items_only(self):
        said = []
        n = letgo.empty(self.root, letgo.held(self.root, 90), ask=lambda _: "yes\n", say=said.append)
        self.assertEqual(n, 2)
        self.assertEqual(sorted(p.name for p in self.held_dir.iterdir()), ["2026-11-01 old.tmp"])
        self.assertTrue(any("2026-01-01 setup.exe" in line for line in said))  # listed before asking
        deletes = [e for e in journal.read(self.root) if e["op"] == "delete"]
        self.assertEqual(sorted(e["path"] for e in deletes),
                         ["4 Let Go/2026-01-01 setup.exe", "4 Let Go/Old folder"])

    def test_cli_without_yes_deletes_nothing(self):
        env = dict(os.environ, PYTHONPATH=str(REPO))
        for stdin in ("", "y\n", "no\n"):
            done = subprocess.run([sys.executable, "-m", "bes", "letgo", str(self.root), "--empty"],
                                  input=stdin, capture_output=True, text=True, env=env, cwd=REPO)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("Nothing deleted.", done.stdout)
            self.assertTrue(self.old.exists())

    def test_cli_list_never_deletes(self):
        env = dict(os.environ, PYTHONPATH=str(REPO))
        done = subprocess.run([sys.executable, "-m", "bes", "letgo", str(self.root), "--older-than", "0"],
                              input="yes\n", capture_output=True, text=True, env=env, cwd=REPO)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(list(self.held_dir.iterdir())), 3)


class IndexTest(TreeTest):
    def test_index_fields_and_counts(self):
        self.put("2026-11-21 Scan 1650.pdf", content="12345", when=NOON)
        self.put("2026-11-22 Voicemail (Mom) (2).m4a", folder=self.root / "2 Keep" / "2026", when=NOON)
        self.put("2026-12-01 Pay Verizon.pdf", folder=self.root / "1 Do", when=NOON)
        self.put("notes.txt", folder=self.root / "3 Know" / "Chemistry", when=NOON)
        self.put(".hidden", folder=self.root / "3 Know")
        items, counts = index.build(self.root)
        lines = (self.root / ".bes" / "index.jsonl").read_text().splitlines()
        rows = {r["path"]: r for r in map(json.loads, lines)}
        self.assertEqual(len(rows), 4)
        scan = rows["0 Inbox/2026-11-21 Scan 1650.pdf"]
        self.assertEqual(set(scan), {"path", "room", "date", "title", "people", "ext", "bytes", "mtime"})
        self.assertEqual((scan["room"], scan["date"], scan["title"], scan["people"], scan["ext"], scan["bytes"]),
                         ("Inbox", "2026-11-21", "Scan 1650", [], ".pdf", 5))
        vm = rows["2 Keep/2026/2026-11-22 Voicemail (Mom) (2).m4a"]
        self.assertEqual((vm["room"], vm["title"], vm["people"]), ("Keep", "Voicemail", ["Mom"]))
        self.assertEqual(rows["3 Know/Chemistry/notes.txt"]["date"], None)
        self.assertEqual(counts, {"Inbox": 1, "Do": 1, "Keep": 1, "Know": 1})
        md = (self.root / "BES.md").read_text()
        self.assertIn("| Keep | 1 |", md)
        self.assertIn("| Let Go | 0 |", md)
        self.assertIn("## The four rooms", md)

    def test_reindex_replaces_counts_only(self):
        index.build(self.root)
        md = self.root / "BES.md"
        md.write_text(md.read_text().replace("# Baney Extended System", "# Baney Extended System\n\nMy note."))
        self.put("x.txt", folder=self.root / "1 Do")
        index.build(self.root)
        text = md.read_text()
        self.assertIn("My note.", text)
        self.assertIn("| Do | 1 |", text)
        self.assertEqual(text.count("<!-- bes:counts:start -->"), 1)


if __name__ == "__main__":
    unittest.main()
