# Notion

Every page gets a **Room**: Do, Keep, Know, Let Go, or Inbox when nothing decides it. Notion sets it for you with a formula, so new pages file themselves. You only correct.

## Setup

1. Add a Select property named `Room override` with four options: Do, Keep, Know, Let Go. Leave it empty on almost every page.
2. Add a Formula property named `Room`. Adapt the type names to your own database:

```
ifs(
  !empty(prop("Room override")), format(prop("Room override")),
  prop("Archived"), "Let Go",
  includes(["Tasks", "Project Brief", "Project Board"], format(prop("Type"))), "Do",
  or(!empty(prop("Course")), !empty(prop("Subject"))), "Know",
  or(format(prop("Status")) == "in-progress", format(prop("Status")) == "planned"), "Do",
  includes(["Personal Reference", "Journal", "Writing Source"], format(prop("Type"))), "Keep",
  or(format(prop("Status")) == "inbox", format(prop("Type")) == "Capture"), "Inbox",
  "Know"
)
```

3. Add five views, each filtered on `Room`: `0 Inbox`, `> Do` (oldest first), `< Keep`, `= Know` (grouped by course), `x Let Go`.

## The order of the rules

The first rule that matches wins.

1. Your correction (`Room override`) always wins.
2. Archived pages are Let Go.
3. Task lists and project pages are Do.
4. Anything tied to a class or subject is Know, even while you are still writing it.
5. Pages marked in progress or planned are Do.
6. Personal records and your own writing are Keep.
7. Unsorted captures stay in the Inbox.
8. Everything else is Know.

A page moves between rooms as its claim changes: an assignment is Do until it is submitted, then you set `Room override` to Keep.
