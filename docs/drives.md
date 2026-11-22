# Drives and clouds

Every drive you own gets the same five folders at its top:

```
0 Inbox/   1 Do/   2 Keep/   3 Know/   4 Let Go/   BES.md
```

## A local drive or NAS

```
bes init /path/to/drive
bes sort /path/to/drive --dry-run   # shows what would move
bes sort /path/to/drive             # moves it, journaled
bes undo /path/to/drive --last 20   # if anything looks wrong
```

Add the drive to the config so the timer sorts it every 15 minutes (`bes autostart` installs the timer). Libraries of movies or music can sit beside the rooms untouched.

## Google Drive, OneDrive, Proton Drive

Use the desktop sync client for each, then treat the synced folder like a local drive: `bes init` it and add it to the config. The sorting happens on your computer and syncs up.

Without a sync client, create the five folders in the web app by hand, and drop new files into `0 Inbox` to be sorted the next time a synced machine runs.

## Phones

Set the camera roll backup and the scanner app to save into `0 Inbox` on a synced drive. Photos go to `2 Keep/<year>/` on their own.
