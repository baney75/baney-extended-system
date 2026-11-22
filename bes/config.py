"""Config at ~/.config/bes/config.toml, or the file named by BES_CONFIG.

    roots = ["~/BES"]
    drops = [{path = "~/Downloads", root = "~/BES"}]
    ai_command = ""

A missing file means: only sort the roots given on the command line.
"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Drop:
    path: Path
    root: Path


@dataclass
class Config:
    roots: list = field(default_factory=list)
    drops: list = field(default_factory=list)
    ai_command: str = ""
    path: Path | None = None


def config_path():
    env = os.environ.get("BES_CONFIG")
    if env:
        return Path(env).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or "~/.config"
    return Path(base).expanduser() / "bes" / "config.toml"


def expand(p):
    return Path(os.path.expandvars(str(p))).expanduser().resolve()


def load(path=None):
    path = Path(path) if path else config_path()
    if not path.is_file():
        return Config(path=path)
    with open(path, "rb") as f:
        data = tomllib.load(f)
    roots = [expand(r) for r in data.get("roots", [])]
    drops = []
    for d in data.get("drops", []):
        if isinstance(d, dict) and d.get("path") and d.get("root"):
            drops.append(Drop(expand(d["path"]), expand(d["root"])))
    ai = str(data.get("ai_command", "") or "").strip()
    return Config(roots=roots, drops=drops, ai_command=ai, path=path)
