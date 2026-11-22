"""The optional AI step for Inbox leftovers (config key ai_command, off by default).

The command gets the file name, a blank line, and the first 2,000
characters of text on stdin. Its answer must be exactly one room name:
Do, Keep, Know or Let Go. Anything else leaves the item where it is.
"""

import shlex

from . import tools

ANSWERS = {"do": "Do", "keep": "Keep", "know": "Know", "let go": "Let Go"}
TEXT_LIMIT = 2000


def ask(command, name, text, timeout=120):
    if not command:
        return None
    try:
        args = shlex.split(command)
    except ValueError:
        return None
    prompt = f"{name}\n\n{text[:TEXT_LIMIT]}"
    out = tools.run(args, input_text=prompt, timeout=timeout)
    if out is None:
        return None
    answer = " ".join(out.split()).rstrip(".").lower()
    return ANSWERS.get(answer)
