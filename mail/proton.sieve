# The Baney Extended System: Proton Mail filter.
# Install: Proton Mail, Settings, Filters, Add Sieve filter, paste this, Save.
# First create four labels named Do, Keep, Know and Let Go.
# What stays in the inbox: mail from people, and mail that asks something of you.
# Nothing is deleted. The first rule that matches wins.
# Replace the example senders (your-school.edu, newsletter-you-chose.com) first.
# Keep your filled-in copy in mail/private/, which git ignores.

require ["fileinto", "imap4flags"];

# 1. Do: bills due, deadlines, school, leaked-secret alerts. Stays in the inbox.
if anyof (
  header :contains "subject" ["action required", "payment request", "payment due",
    "past due", "amount due", "balance due", "due date", "deadline", "expires in",
    "required", "please respond", "RSVP"],
  address :domain :is "from" ["instructure.com", "blackboard.com", "your-school.edu"],
  allof (address :domain :is "from" "gitguardian.com", header :contains "subject" "detected")
) {
  fileinto "Do";
  stop;
}

# Codes, verification mail and replies in a conversation always stay in the inbox.
if anyof (
  header :contains "subject" ["code", "verify", "verification"],
  header :matches "subject" ["Re:*", "RE:*", "Fwd:*", "FW:*"]
) {
  stop;
}

# 2. Keep: receipts, orders, statements, tax forms.
if header :contains "subject" ["receipt", "invoice", "statement", "order confirmed",
    "your order", "order has been", "payment confirmation",
    "payment received", "trade confirmation", "1099", "W-2", "tax form", "paystub",
    "pay stub"] {
  fileinto "Keep";
  fileinto "archive";
  stop;
}

# 3. Know: newsletters chosen on purpose.
if address :domain :is "from" ["substack.com", "newsletter-you-chose.com"] {
  fileinto "Know";
  fileinto "archive";
  stop;
}

# 4. Let Go: bulk mail, sign-in notices and robot notifications.
if anyof (
  exists "List-Unsubscribe",
  header :contains "subject" ["new sign-in", "new device", "passkey",
    "trusted device", "breach detected", "added a card"],
  address :is "from" ["notifications@github.com", "calendar-notification@google.com"]
) {
  fileinto "Let Go";
  fileinto "archive";
  stop;
}
