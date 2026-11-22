"""Optional outside programs (pdftotext, exiftool, yt-dlp, ocrmypdf).

Each one is used only when found on PATH. Setting BES_NO_TOOLS=1 hides
them all, which keeps tests the same on every machine.
"""

import os
import shutil
import subprocess


def which(name):
    if os.environ.get("BES_NO_TOOLS"):
        return None
    return shutil.which(name)


def run(args, input_text=None, timeout=60):
    """Run a program and return its stdout, or None if it failed."""
    try:
        done = subprocess.run(
            args,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return done.stdout
