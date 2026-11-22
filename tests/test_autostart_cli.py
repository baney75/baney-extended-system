import json
import os
import plistlib
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from bes import autostart, layout
from tests.helpers import NOON, TreeTest

REPO = Path(__file__).resolve().parent.parent


class AutostartTest(TreeTest):
    def test_linux_writes_service_and_timer(self):
        os.environ["XDG_CONFIG_HOME"] = str(self.tmp / "xdg")
        with mock.patch("bes.autostart.subprocess.run") as run:
            paths = autostart.install(platform="linux", enable=False, say=lambda _: None)
        run.assert_not_called()
        folder = self.tmp / "xdg" / "systemd" / "user"
        self.assertEqual(sorted(p.name for p in paths), ["bes-sort.service", "bes-sort.timer"])
        service = (folder / "bes-sort.service").read_text()
        self.assertIn(" sort\n", service.split("ExecStart=")[1])
        self.assertIn("BES_CONFIG=", service)
        timer = (folder / "bes-sort.timer").read_text()
        self.assertIn("OnCalendar=*:0/15", timer)
        self.assertIn("WantedBy=timers.target", timer)
        removed = autostart.remove(platform="linux", enable=False, say=lambda _: None)
        self.assertEqual(len(removed), 2)
        self.assertEqual(list(folder.iterdir()), [])

    def test_macos_writes_valid_plist(self):
        os.environ["HOME"] = str(self.tmp / "home")
        with mock.patch("bes.autostart.subprocess.run") as run:
            (path,) = autostart.install(platform="darwin", enable=False, say=lambda _: None)
        run.assert_not_called()
        self.assertEqual(path, self.tmp / "home" / "Library" / "LaunchAgents" / "org.baney.bes.sort.plist")
        data = plistlib.loads(path.read_bytes())
        self.assertEqual(data["Label"], "org.baney.bes.sort")
        self.assertEqual(data["ProgramArguments"][-1], "sort")
        self.assertEqual(data["StartInterval"], 900)
        autostart.remove(platform="darwin", enable=False, say=lambda _: None)
        self.assertFalse(path.exists())

    def test_contrib_templates_match_code(self):
        contrib = REPO / "contrib"
        self.assertEqual((contrib / "bes-sort.service").read_text(),
                         autostart.render_service(["%h/.local/bin/bes"]))
        self.assertEqual((contrib / "bes-sort.timer").read_text(), autostart.TIMER)
        plist = autostart.render_plist(["/Users/YOU/.local/bin/bes"], "/Users/YOU/Library/Logs/bes.log")
        self.assertEqual((contrib / "org.baney.bes.sort.plist").read_text(), plist)
        plistlib.loads(plist.encode())


class CommandLineTest(TreeTest):
    def bes(self, *args, stdin=""):
        env = dict(os.environ, PYTHONPATH=str(REPO))
        return subprocess.run([sys.executable, "-m", "bes", *args], input=stdin,
                              capture_output=True, text=True, env=env, cwd=REPO)

    def test_init_makes_layout(self):
        target = self.tmp / "fresh"
        done = self.bes("init", str(target))
        self.assertEqual(done.returncode, 0, done.stderr)
        for rel in layout.ROOMS + ["2 Keep/Records", "3 Know/Citations", ".bes"]:
            self.assertTrue((target / rel).is_dir(), rel)
        md = (target / "BES.md").read_text()
        self.assertIn("Only what the machine could not decide.", md)
        self.assertIn("YYYY-MM-DD Title (Person, Person).ext", md)

    def test_sort_refuses_non_root(self):
        done = self.bes("sort", str(self.tmp))
        self.assertEqual(done.returncode, 1)
        self.assertIn("bes init", done.stderr)

    def test_sort_without_roots_or_config(self):
        done = self.bes("sort")
        self.assertEqual(done.returncode, 2)

    def test_sort_and_undo_round_trip(self):
        self.put("homework.txt", when=NOON)
        self.assertEqual(self.bes("sort", str(self.root)).returncode, 0)
        self.assertTrue((self.root / "1 Do" / "2026-03-04 homework.txt").exists())
        done = self.bes("undo", str(self.root), "--last", "1")
        self.assertIn("Undid 1 moves.", done.stdout)
        self.assertTrue((self.inbox / "homework.txt").exists())

    def test_config_roots_used_when_none_given(self):
        cfg = self.tmp / "config.toml"
        cfg.write_text(f'roots = ["{self.root}"]\n')
        os.environ["BES_CONFIG"] = str(cfg)
        self.put("homework.txt", when=NOON)
        done = self.bes("sort", "--dry-run", "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)[0]["items"][0]["room"], "Do")

    def test_ascii_dashes_only_in_repo_text(self):
        bad = []
        for p in list(REPO.glob("bes/*.py")) + list(REPO.glob("tests/*.py")) + list(REPO.glob("contrib/*")) \
                + [REPO / "pyproject.toml", REPO / ".github" / "workflows" / "ci.yml"]:
            text = p.read_text(encoding="utf-8")
            if chr(0x2014) in text or chr(0x2013) in text:
                bad.append(p.name)
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
