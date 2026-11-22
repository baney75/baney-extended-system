import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

from bes import layout


class TreeTest(unittest.TestCase):
    """Builds a fresh BES root in a temp folder, with outside tools hidden."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bes-test-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.env = {k: os.environ.get(k) for k in ("BES_NO_TOOLS", "BES_CONFIG", "XDG_CONFIG_HOME", "HOME")}
        os.environ["BES_NO_TOOLS"] = "1"
        os.environ["BES_CONFIG"] = str(self.tmp / "no-config.toml")
        self.addCleanup(self.restore_env)
        self.root, _ = layout.init_root(self.tmp / "root")
        self.inbox = self.root / layout.INBOX

    def restore_env(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def put(self, name, content=None, days_old=None, when=None, folder=None):
        """Make a file in the Inbox (or folder) with a chosen modification time."""
        path = (folder or self.inbox) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if content is None:
            content = "contents of " + name  # unique, so fixtures are never duplicates
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content)
        if when is not None:
            stamp = when.timestamp()
            os.utime(path, (stamp, stamp))
        elif days_old is not None:
            stamp = time.time() - days_old * 86400
            os.utime(path, (stamp, stamp))
        return path

    def snapshot(self, base=None):
        base = base or self.root
        out = {}
        for p in sorted(base.rglob("*")):
            st = p.lstat()
            data = p.read_bytes() if p.is_file() else None
            out[p.relative_to(base).as_posix()] = (p.is_dir(), st.st_size, st.st_mtime_ns, data)
        return out


NOON = datetime(2026, 3, 4, 12, 0, 0)
