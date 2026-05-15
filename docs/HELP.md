# RTH CommsDesk Help

This file is the user-facing help guide. Keep it simple, practical, and current as features are added.

## What RTH CommsDesk does today

RTH CommsDesk helps review Gmail messages by showing likely important items in an Attention Queue.

Current MVP features:

- Sync recent Gmail inbox messages in read-only mode.
- Keep Gmail sync metadata locally so repeat syncs are incremental.
- Skip duplicate Gmail messages and duplicate attention items on repeat sync.
- Show the latest sync counts: fetched, inserted, duplicates skipped, and threads updated.
- Store message metadata and snippets by default.
- Classify messages using local deterministic rules.
- Assign an attention score.
- Show a readable dashboard with attention items, scores, labels, reasons, VIP contacts, unread human-like messages, and suspected noise.
- Mark attention items as reviewed.
- Mark a sender as noise.
- Mark a contact as VIP.
- Reset a contact back to normal.
- Manage contact profiles from the Contacts page.
- Add contact aliases so multiple sender addresses can map to one person or organization.
- Set relationship type, importance tier, preferred channel, notes, and VIP/noise/normal status.
- See contact relationship and importance context on message detail pages.
- Mark a message as important.
- Mark a message as requiring a reply.
- Correct a message with structured labels such as important, needs reply, client work, job alert, newsletter, receipt, system notice, marketing, noise, or ignore.
- Generate a local review-only draft suggestion from a message detail page.
- Choose a voice profile for draft suggestions: client, friend, partner, vendor, or short acknowledgement.
- Review local draft suggestions from the Drafts page.

## What it does not do today

RTH CommsDesk does not currently:

- Send emails.
- Reply to emails.
- Archive emails.
- Delete emails.
- Read Outlook, Teams, SMS, or other message channels.
- Create external Gmail drafts.
- Use paid or cloud AI credentials as a requirement for local draft generation.
- Store full email bodies by default.

## Dashboard sections

### Attention Queue

The Attention Queue lists messages that the app thinks may need attention. Higher scores should appear closer to the top.

### VIP Contacts

VIP Contacts are senders the user has marked as important. Future messages from VIP senders should rank higher.

### Contacts

The Contacts page is linked from the dashboard header. Use it to edit contact profiles, aliases, relationship type, importance tier, preferred channel, notes, and normal/VIP/noise status.

### Drafts

The Drafts page lists local draft suggestions. Drafts are stored only in the local CommsDesk database and are not sent or created in Gmail.

### Recent Unread Human Messages

This section shows unread messages that look more like personal or human communication than automated notices.

### Suspected Noise

This section shows messages likely to be newsletters, job alerts, marketing, system notices, or other low-priority items.

## Common actions

### Sync Gmail

Pulls recent Gmail inbox messages. The app requires a local Google OAuth client secrets file before the first sync.

The dashboard shows what happened during the latest sync:

- Fetched: messages returned by Gmail.
- Inserted: new local messages created.
- Duplicates skipped: Gmail messages already stored locally.
- Threads updated: local thread metadata recalculated after the sync.

Normal sync uses the last successful Gmail high-water mark. This keeps future syncs incremental while still overlapping slightly to avoid missing same-time messages.

### Resync recent

Runs a safe manual resync of the recent Gmail window without using the high-water mark. Existing messages are updated and counted as duplicates rather than inserted again.

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

### Generate local draft

Creates a local draft suggestion from the message detail page. Choose a voice profile before generating:

- Client: direct, competent, and clear about next steps.
- Friend: warmer and more casual.
- Partner: warm, direct, and less corporate.
- Vendor: brief and transactional.
- Short acknowledgement: very brief confirmation of receipt.

Generated drafts are suggestions only. The app does not send the draft, reply to Gmail, create a Gmail draft, archive, or delete anything.

### Review drafts

Open the Drafts page from the dashboard header or open a generated draft directly after creating it. The review page shows the source message, selected voice profile, local status, and suggested reply text.

### Reset contact normal

Removes VIP or noise status from a contact and recalculates existing messages from that sender.

### Edit contact

Opens the contact profile. Saving relationship, importance, alias, VIP/noise, channel, or notes changes recalculates local attention scores for existing messages that match the contact primary email or aliases.

Supported relationship types:

- partner
- close_friend
- friend
- family
- client
- prospect
- vendor
- newsletter
- system
- unknown

Aliases should be entered as one email address per line. Full message bodies are not needed for alias matching.

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

## Local database reset

The local SQLite database is `commsdesk.db` by default. It can contain private message metadata, snippets, classifications, and feedback.

To reset disposable local data:

```powershell
# Stop the local uvicorn server first.
Remove-Item .\commsdesk.db -ErrorAction SilentlyContinue
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Startup also runs Alembic migrations, but `python -m alembic upgrade head` is the explicit setup/reset command. Do not delete or share OAuth files unless you intentionally want to re-authorize Gmail.
