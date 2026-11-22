"""`bes autostart`: run `bes sort` every 15 minutes.

Linux gets a systemd user service and timer; macOS gets a launchd agent.
The same templates live in contrib/ for people who install by hand.
"""

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

LABEL = "org.baney.bes.sort"

SERVICE = """\
[Unit]
Description=Baney Extended System: sort Inboxes and drop folders

[Service]
Type=oneshot
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin
{env}ExecStart={command} sort
"""

TIMER = """\
[Unit]
Description=Run bes sort every 15 minutes

[Timer]
OnCalendar=*:0/15
Persistent=true

[Install]
WantedBy=timers.target
"""

PLIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
{arguments}
  </array>
  <key>StartInterval</key>
  <integer>900</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
{env}  </dict>
  <key>StandardOutPath</key>
  <string>{log}</string>
  <key>StandardErrorPath</key>
  <string>{log}</string>
</dict>
</plist>
"""


def xml_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def bes_command():
    """The argv that runs bes: the installed script, else this Python with -m bes."""
    found = shutil.which("bes")
    return [found] if found else [sys.executable, "-m", "bes"]


def systemd_quote(arg):
    return f'"{arg}"' if any(c in arg for c in ' "\\') else arg


def render_service(command, config=None):
    env = f"Environment=BES_CONFIG={systemd_quote(str(config))}\n" if config else ""
    return SERVICE.format(env=env, command=" ".join(systemd_quote(a) for a in command))


def render_plist(command, log, config=None):
    args = "\n".join(f"    <string>{xml_escape(a)}</string>" for a in command + ["sort"])
    env = ""
    if config:
        env = f"    <key>BES_CONFIG</key>\n    <string>{xml_escape(str(config))}</string>\n"
    return PLIST.format(label=LABEL, arguments=args, env=env, log=xml_escape(str(log)))


def unit_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "systemd" / "user"


def plist_path():
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def run(args, say):
    say("$ " + shlex.join(args))
    try:
        subprocess.run(args, check=False)
    except OSError as e:
        say(f"could not run {args[0]}: {e}")


def install(platform=None, enable=True, say=print):
    platform = platform or sys.platform
    command = bes_command()
    config = os.environ.get("BES_CONFIG")
    if platform.startswith("linux"):
        folder = unit_dir()
        folder.mkdir(parents=True, exist_ok=True)
        files = {folder / "bes-sort.service": render_service(command, config),
                 folder / "bes-sort.timer": TIMER}
        for path, text in files.items():
            path.write_text(text, encoding="utf-8")
            say(f"wrote {path}")
        if enable:
            run(["systemctl", "--user", "daemon-reload"], say)
            run(["systemctl", "--user", "enable", "--now", "bes-sort.timer"], say)
        else:
            say("To turn it on: systemctl --user daemon-reload && "
                "systemctl --user enable --now bes-sort.timer")
        return list(files)
    if platform == "darwin":
        path = plist_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        log = Path.home() / "Library" / "Logs" / "bes.log"
        path.write_text(render_plist(command, log, config), encoding="utf-8")
        say(f"wrote {path}")
        if enable:
            run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)], say)
        else:
            say(f"To turn it on: launchctl bootstrap gui/$(id -u) {shlex.quote(str(path))}")
        return [path]
    raise SystemExit(f"bes autostart supports Linux and macOS, not {platform}")


def remove(platform=None, enable=True, say=print):
    platform = platform or sys.platform
    if platform.startswith("linux"):
        if enable:
            run(["systemctl", "--user", "disable", "--now", "bes-sort.timer"], say)
        paths = [unit_dir() / "bes-sort.timer", unit_dir() / "bes-sort.service"]
    elif platform == "darwin":
        if enable and plist_path().exists():
            run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist_path())], say)
        paths = [plist_path()]
    else:
        raise SystemExit(f"bes autostart supports Linux and macOS, not {platform}")
    removed = []
    for p in paths:
        if p.exists():
            p.unlink()
            say(f"removed {p}")
            removed.append(p)
    return removed
