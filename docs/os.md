# Operating systems, in theory

This page is a thought experiment. Nothing here changes your computer.

Every operating system ships a home folder organized by file type: Documents, Pictures, Music, Videos, Downloads. That is the library model, and it answers the wrong question. A photo of a receipt and a photo of your family are both Pictures. One is a record; the other is your story.

## A home folder built on the four rooms

```
~/
  0 Inbox/     replaces Downloads, Desktop and the scanner folder
  1 Do/        everything that asks something of you, one folder per work
  2 Keep/      Records/ and one folder per year
  3 Know/      one folder per subject, plus Citations/
  4 Let Go/    the trash, held for a season and emptied on request
  Library/     apps, music and movie libraries, config: not records
```

## What the system would do

- **Save dialogs** default to `0 Inbox`, and the OS sorts on save.
- **The file browser** shows four rooms, not a tree. Search answers by room: "what do I owe this week" reads `1 Do` by date.
- **Trash** becomes Let Go: recoverable for a season, emptied only when you confirm.
- **Notifications** follow the mail rule: people and asks reach you; the crowd is batched and archived.
- **Every file** carries its date and people in its name, so it survives copying to any other system.

The `bes` command is a working piece of this on today's systems: one timer, plain folders, no new file system required.
