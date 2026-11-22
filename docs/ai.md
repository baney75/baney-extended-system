# For AI agents

The Baney Extended System is human first. Folders and file names are the source of truth, and an agent reads them like a person would.

Each BES root has:

- `BES.md`: the layout in plain words. Read it first.
- `.bes/index.jsonl`: one JSON object per item (`path`, `room`, `date`, `title`, `people`, `ext`, `bytes`). Rebuild it with `bes index ROOT`. It is derived; never edit it by hand.
- `.bes/journal.jsonl`: every move `bes` has made, which `bes undo` reverses.

## Rules for an agent

1. Answer "what do I owe?" from `1 Do`, "what happened?" from `2 Keep`, and "what do I know about X?" from `3 Know`.
2. Put new files in `0 Inbox` and let `bes sort` place them, or name them `YYYY-MM-DD Title (People).ext` and place them yourself.
3. Never delete. Moving to `4 Let Go` is the strongest action an agent should take.
4. Mail uses the same four labels. A thread labeled Do is something the owner has to act on.

## The optional AI step

`bes sort` can ask a model about items it could not place. It is off by default. Set `ai_command` in the config to a command that reads the file name and the first 2,000 characters of text on standard input and prints one word: Do, Keep, Know or Let Go. Any other answer leaves the item in the Inbox.
