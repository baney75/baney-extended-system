# Mail

The four rooms become four labels: **Do**, **Keep**, **Know** and **Let Go**. The mail service sorts on its own servers, so nothing has to run on your computer.

**The rule:** the inbox holds mail from people and mail that asks something of you. Everything else is labeled and archived. Nothing is deleted.

| Label | What gets it | Leaves the inbox? |
| --- | --- | --- |
| Do | Bills due, deadlines, "action required", school portals, leaked-secret alerts | No |
| Keep | Receipts, order and payment confirmations, statements, tax forms | Yes |
| Know | Newsletters you chose to read | Yes |
| Let Go | Bulk mail with an unsubscribe link, sign-in and device notices, robot notifications | Yes |

Verification codes and replies in a conversation always stay in the inbox.

## Gmail

1. Settings, See all settings, Filters and Blocked Addresses, Import filters.
2. Choose `mail/gmail-filters.xml`, then Open file.
3. Tick **Apply new filters to existing email**, then Create filters.

This cleans the existing inbox and sorts new mail from then on. To undo, open the Let Go label, select all, and Move to Inbox.

Before importing, edit the sender lists in the file: the Know senders (newsletters you want) and the protected senders (family, schools) that must never be archived.

## Proton Mail

1. Create four labels: Do, Keep, Know, Let Go.
2. Settings, Filters, Add Sieve filter. Paste `mail/proton.sieve`. Save.

If your account already has filters that clear the inbox, keep them and make this one label-only: delete every `fileinto "archive";` line and change each `stop;` to `return;`, so your other filters still run. Add it last.

Proton applies Sieve filters to new mail. To sort existing mail, search for it and apply the label by hand once.

## Why

Most of an inbox is what Kierkegaard called the crowd: messages sent to everyone and addressed to no one. The inbox should hold only what is addressed to you. See `THEORY.md`, section 6.
