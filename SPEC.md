# The Baney Extended System: Specification

Version 1.0, 2026-11-22.

## The idea in one line

Everything you keep is asking you to do something, keep it, know it, or let it go. The system sorts it for you and you only correct it.

## The four rooms

| # | Room | What goes here | Mark |
| --- | --- | --- | --- |
| 0 | Inbox | Only what the machine could not decide. | (none) |
| 1 | Do | Anything that asks something of you: a reply, a bill, a form, an assignment, a project you are making. | `>` |
| 2 | Keep | Your story and your records: photos, letters, voicemails, texts, journals, receipts, IDs, finished work. | `<` |
| 3 | Know | The world's knowledge you gathered: books, papers, class material, articles, videos, citations. | `=` |
| 4 | Let Go | Everything else. Held for a season, emptied only when you say. | `x` |

The marks are for paper: write one in the top corner of a page. An unmarked page is undecided.

Rooms are verbs, not subjects. A chemistry handout is in Know, and the lab report you owe is in Do. When the report is graded it moves to Keep.

## Layout on any drive

```
0 Inbox/
1 Do/
2 Keep/
3 Know/
4 Let Go/
BES.md        a plain description of this layout, for people and AI agents
.bes/         machine files: index.jsonl, journal.jsonl
```

Inside the rooms, at most one more level:

- `1 Do/`: loose items, plus one folder per work you are making (`1 Do/Six Actual/`).
- `2 Keep/`: `Records/` (identity, money, health, home, school, legal) and one folder per year (`2 Keep/2026/`).
- `3 Know/`: one folder per subject you name, plus `Citations/`.
- `4 Let Go/`: flat.

## Names

```
YYYY-MM-DD Title (Person, Person).ext
```

The date is when the thing entered your life: the event, the scan, the message, or the due date for something in Do. People go in parentheses when they matter. Examples:

- `2026-11-21 Scan 1650.pdf`
- `2026-11-22 Voicemail (Mom).m4a`
- `2026-12-01 Pay Verizon.pdf`

## Automatic sorting

The `bes` command sorts every Inbox and every configured drop folder (Downloads, a scanner folder) on a timer. Rules run in this order and the first match wins:

1. **Let Go:** partial or temporary downloads (`.crdownload`, `.part`, `.tmp`), empty files, exact duplicates of a file already kept (same SHA-256), installers (`.dmg`, `.exe`, `.msi`, `.pkg`, `.deb`, `.AppImage`) older than 7 days, screenshots older than 30 days.
2. **Keep/Records:** names or text containing receipt, invoice, statement, tax, W-2, 1099, 1098, lease, deed, title, insurance, policy, passport, license, birth certificate, social security, medical, prescription, diploma, transcript, warranty, contract.
3. **Keep/<year>:** camera photos and videos (`IMG_`, `PXL_`, `DSC`, `.heic`, EXIF camera data), voicemails and recordings, journals, letters, exported texts and call logs.
4. **Know:** books (`.epub`, `.mobi`, `.azw3`), papers (a DOI or arXiv id in the name or first page), slides and lecture notes, syllabi, citation cards.
5. **Do:** names or text containing form, application, assignment, homework, due, deadline, draft, todo, sign, RSVP.
6. Otherwise it stays in the Inbox.

Every sort also renames the item to the naming rule, taking the date from the file name (`SCN_20261121_1650`, `IMG_20261121_...`, `Screenshot 2026-11-21`), then EXIF, then modification time.

An optional AI step can decide Inbox leftovers. It is off by default. When on, `bes` runs a configured command with the file name and the first 2,000 characters of text, and accepts only a one-word answer naming a room.

## Safety

- `bes` never deletes. It moves, and it writes every move to `.bes/journal.jsonl`.
- `bes undo` reverses moves by count or by time.
- Let Go is emptied only by `bes letgo --empty`, which lists what it will remove and asks first.
- A name collision gets ` (2)` appended, never an overwrite.

## Mail

The same four rooms are labels. Server-side filters do the sorting, so nothing has to run on your computer.

- **Gmail:** import `mail/gmail-filters.xml` once (Settings, Filters, Import filters) and tick "apply to existing conversations." This both cleans the existing inbox and sorts all future mail.
- **Proton Mail:** paste `mail/proton.sieve` into Settings, Filters, Add Sieve filter.

What stays in the inbox is mail from people and mail that asks something of you. Everything the crowd sends (marketing, notifications, newsletters, sign-in notices) is labeled and archived. Nothing is deleted.

## Notes

In Notion, every page gets a `Room` property with the same four values. Views show one room each. Class notes default to Know.

## Paper

1. One tray. Everything paper lands there.
2. Mark the corner of anything you keep: `>` Do, `<` Keep, `=` Know, `x` Let Go.
3. Scan the tray when it fills. Scans land in the Inbox and sort themselves by date and words.
4. File the paper in a four-folder box with the same names, or recycle it once scanned.

## Media and citations

`bes cite <url>` writes a citation card to `3 Know/Citations/` for a YouTube video or web page: title, channel or author, date published, date accessed, URL, length, and ready-made APA 7, MLA 9 and Chicago citations, plus a place for timestamped quotes.

## For AI agents

Each root has `BES.md` (the layout in plain words) and `.bes/index.jsonl` (one JSON object per item: path, room, date, title, people, extension, bytes). The index is derived and rebuilt by `bes index`. Folders and names are the source of truth.

## The theory behind it

See `THEORY.md` and `docs/research.html`.
