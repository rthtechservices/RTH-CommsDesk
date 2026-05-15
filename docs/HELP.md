# RTH CommsDesk Help

This file is the user-facing help guide. Keep it simple, practical, and current as features are added.

## What RTH CommsDesk does today

RTH CommsDesk helps review Gmail messages by showing likely important items in an Attention Queue.

Current MVP features:

- Sync recent Gmail inbox messages in read-only mode.
- Store message metadata and snippets by default.
- Classify messages using local deterministic rules.
- Assign an attention score.
- Show a readable dashboard with attention items, scores, labels, reasons, VIP contacts, unread human-like messages, and suspected noise.
- Mark attention items as reviewed.
- Mark a sender as noise.
- Mark a contact as VIP.
- Reset a contact back to normal.
- Mark a message as important.
- Mark a message as requiring a reply.
- Correct a message with structured labels such as important, needs reply, client work, job alert, newsletter, receipt, system notice, marketing, noise, or ignore.
- Generate a draft reply placeholder.

## What it does not do today

RTH CommsDesk does not currently:

- Send emails.
- Reply to emails.
- Archive emails.
- Delete emails.
- Read Outlook, Teams, SMS, or other message channels.
- Generate polished AI replies.
- Store full email bodies by default.

## Dashboard sections

### Attention Queue

The Attention Queue lists messages that the app thinks may need attention. Higher scores should appear closer to the top.

### VIP Contacts

VIP Contacts are senders the user has marked as important. Future messages from VIP senders should rank higher.

### Recent Unread Human Messages

This section shows unread messages that look more like personal or human communication than automated notices.

### Suspected Noise

This section shows messages likely to be newsletters, job alerts, marketing, system notices, or other low-priority items.

## Common actions

### Sync Gmail

Pulls recent Gmail inbox messages. The app requires a local Google OAuth client secrets file before the first sync.

### View

Opens the message detail page.

### Mark as reviewed

Removes the item from the default Attention Queue.

### Mark sender as noise

Marks the sender as low priority. Existing and future messages from that sender should be reduced or dismissed.

### Mark contact VIP

Marks the sender/contact as important. Existing and future messages from that sender should score higher.

### Mark requires reply

Marks the message as needing a reply.

### Correct classification

Records that the app classified a message incorrectly. Choose a structured label and optional importance level. The app updates the current message classification and attention score immediately.

### Mark important

Boosts the current message so it stays visible in the Attention Queue.

### Reset contact normal

Removes VIP or noise status from a contact and recalculates existing messages from that sender.

## Local setup summary

From the repo root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/
```

## Local Gmail OAuth files

Expected local-only files:

- `client_secret.json`
- `gmail_token.json`
- `.env`
- local SQLite database file

Do not commit these files.
