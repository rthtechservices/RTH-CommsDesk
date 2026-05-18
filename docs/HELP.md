# RTH CommsDesk Help

This file is the user-facing help guide. Keep it simple, practical, and current as features are added.

## What RTH CommsDesk does today

RTH CommsDesk helps review communication messages by showing likely important items in an Attention Queue.

Current MVP features:

- Sync recent Gmail inbox messages in read-only mode.
- Backfill older Gmail inbox pages in read-only mode.
- Sync Outlook mailbox messages through the Microsoft connector adapter.
- Sync Teams chat messages through the Microsoft connector adapter.
- Ingest notification summaries from SMS/WhatsApp/Messenger-style webhook payloads with confidence metadata.
- Keep Gmail sync metadata locally so repeat syncs are incremental.
- Skip duplicate Gmail messages and duplicate attention items on repeat sync.
- Show the latest sync/backfill counts: fetched, inserted, duplicates skipped, threads updated, and backlog cursor status.
- Show current provider/storage status on the dashboard: AI analysis provider, live/mock mode, calendar provider, execution provider, and Gmail full-body sync state.
- Store message metadata and snippets by default.
- Fetch and store full Gmail conversation content manually from a message detail page.
- Show a chronological Gmail conversation timeline on message detail pages.
- Preserve sender, recipients, CC, dates, subject, and message order when full thread context is available.
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
- Run Sent-mail learning to infer VIP candidates, salutation preference, and tone guidance.
- Review/approve/reject/edit inferred VIP and voice guidance from the Voice Calibration page.
- Review local draft suggestions from the Drafts page.
- Analyze a stored Gmail conversation with the mock AI provider by default or an OpenAI-compatible/Azure OpenAI provider when explicitly configured.
- Store and view local conversation summaries.
- Store and view proposed action review packages with a recommendation, explanation, confidence score, optional draft response, and local review status.
- Validate structured AI output before storing it and fall back to the mock provider if live AI fails or returns invalid output.
- Generate local calendar availability recommendations for scheduling requests and due-date reminders.
- Locally approve, reject, edit, or snooze a review package without changing Gmail or any calendar.
- Filter the attention queue by active/unreviewed, needs reply, important, noise, reviewed, date range, sender/contact, and source.
- Use Bulk Triage mode for queue pagination beyond the top dashboard slice.
- Generate and review local automation candidates for mark_noise, unsubscribe_review, archive_candidate, and delete_candidate.
- Apply bulk actions and undo recent bulk actions where practical.
- Prepare, approve, and confirm outbound execution records for draft creation, reply send, calendar creation, and label/archive actions.
- View execution audit trails with payload/result history.
- Enforce web/API authentication when enabled for non-local deployment.
- Provide admin retention controls to clear cached bodies/excerpts and purge aged audit rows.

## What it does not do today

RTH CommsDesk does not currently:

- Execute any outbound action without explicit approve + confirm steps.
- Perform live Microsoft Graph mailbox/chat sync without connector service configuration and permissions.
- Run non-mock production outbound provider calls by default in local development.
- Auto-approve or auto-confirm execution actions.
- Use paid or cloud AI credentials as a requirement for local draft generation.
- Use live AI by default. Live AI is opt-in through environment variables and uses mock fallback.
- Store full email bodies by default.

## Dashboard sections

### Attention Queue

The Attention Queue lists messages that the app thinks may need attention. Higher scores should appear closer to the top.

Reviewed and noise/dismissed items are excluded from the default active queue so the list can move forward as items are processed. Use the queue filters to view reviewed or noise items again.

### VIP Contacts

VIP Contacts are senders the user has marked as important. Future messages from VIP senders should rank higher.

### Contacts

The Contacts page is linked from the dashboard header. Use it to edit contact profiles, aliases, relationship type, importance tier, preferred channel, notes, and normal/VIP/noise status.

### Drafts

The Drafts page lists local draft suggestions. Drafts are stored only in the local CommsDesk database and are not sent or created in Gmail.

### Voice Calibration

The Voice Calibration page lets you refresh Sent-mail learning inferences and review:

- inferred VIP candidates
- inferred salutation style
- inferred preferred name
- inferred tone notes
- excerpted evidence used for inference

Guidance only affects draft tone after you approve it.

### Bulk Triage

The Bulk Triage page lets you process large backlogs with:

- queue controls for unreviewed, needs reply, important, proposed actions, noise candidates, unsubscribe candidates, and reviewed
- pagination beyond the first dashboard slice
- bulk status and relationship actions
- local automation candidate review with reason and confidence
- undo for recent bulk actions where practical

### Executions

The Executions page tracks outbound action records. Each record requires:

1. prepare (from a draft or review package)
2. approve
3. final confirm
4. execute

Execution records include payload preview, provider result, status history, and audit events.

### Review Packages

The Review Packages page lists local AI analysis recommendations. Each package shows:

- communication summary
- recommended action
- explanation
- confidence score
- draft response when a reply or clarification is recommended
- local status: pending, approved, rejected, edited, or snoozed

Review packages are local only. Approving a package does not send email, create a Gmail draft, archive, delete, unsubscribe, label a message, or create a calendar event.

When a scheduling request or due date is detected, review package detail pages can also show:

- proposed calendar action kind
- availability/conflict reasoning
- proposed meeting/reminder timing
- suggested alternate windows when conflicts exist

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

### Backfill older

Fetches the next older Gmail inbox page using Gmail's backlog cursor. Use this when the dashboard keeps showing the same recent messages and you want the local queue to move farther back through the mailbox.

Each click/run fetches one Gmail results page. The maximum page size is controlled by `GMAIL_READ_MAX_RESULTS` and defaults to 100. If Gmail returns a `nextPageToken`, CommsDesk stores it and the next Backfill older run continues from that token. Backfill is read-only. It stores local message records and sync diagnostics only.

### Provider and storage status

The dashboard shows the current local runtime mode:

- AI analysis provider: usually `mock` unless live AI is explicitly configured.
- AI mode/detail: shows whether the app is using the default mock path or a configured live provider with mock fallback.
- Calendar provider: usually `mock` unless a read provider is configured.
- Execution provider: `mock` in local development; execution still requires prepare, approve, and final confirm.
- Gmail full-body sync: `Off` means sync stores metadata/snippets by default and full conversation content is fetched manually from message detail pages.

### Sync Outlook

Runs Outlook ingestion through the Microsoft connector adapter. Records are normalized into the same local thread/message model used by Gmail and appear with source `outlook`.

### Sync Teams

Runs Teams message ingestion through the Microsoft connector adapter. Messages are normalized into local threads with source `teams` and channel metadata so queue filtering and review remain consistent.

### Notification webhook ingest

`POST /api/notifications/webhook` accepts notification summaries (SMS/WhatsApp/Messenger style). These entries are stored as lower-confidence summaries, deduplicated by notification id/source id, and clearly marked with source confidence.

### Sign in and API auth

When app authentication is enabled, web routes require login (`/login`) and API routes require either `X-API-Key` or `Authorization: Bearer <token>`. Notification webhook ingestion remains protected by webhook secret when configured.

### View

Opens the message detail page.

### Fetch full conversation

On a Gmail message detail page, fetches all available messages in that Gmail thread and stores normalized body text locally. Plain text MIME parts are preferred. HTML-only messages are converted to plain text before storage/display.

The conversation timeline then shows the selected message in chronological thread context. This is intended to make cases clear where one person changed plans and another person only acknowledged the update.

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

If a conversation has a review package, draft generation uses the stored conversation summary, proposed action type, full locally stored thread context, contact relationship, importance score, and summarized correction history. If the review package says no response is needed, no draft is created automatically.

If approved voice guidance exists, draft generation also applies inferred salutation style/preferred name and tone notes (for example, to avoid full-name formal greetings in friend threads or to keep client replies concise and professional).

When live AI is configured, draft prompts include the full local conversation timeline, selected message, sender/recipient roles, contact relationship, approved voice guidance, recent corrections, and the proposed action context. Draft output is expected as structured JSON and is sanitized before local storage. If live AI fails or returns invalid output, CommsDesk stores a mock fallback draft and shows the fallback provider name on the draft review page.

### Analyze conversation

On a message detail page, Analyze conversation creates or updates a local review package for that source message and thread.

The mock analysis provider remains the default.

For OpenAI-compatible Chat Completions, set `AI_PROVIDER=openai`, `OPENAI_API_KEY`, `AI_MODEL`, and optionally `AI_BASE_URL`.

For Azure OpenAI / Azure AI Foundry deployments, set `AI_PROVIDER=azure_openai`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, and `AZURE_OPENAI_API_VERSION`. `AZURE_OPENAI_ENDPOINT` should be the resource endpoint such as `https://example.cognitiveservices.azure.com`, not an Azure `/openai/responses?...` URL. Azure mode builds `/openai/deployments/<deployment>/chat/completions?api-version=<version>` automatically.

Use `GET /api/ai/status` to see whether CommsDesk is using `mock`, `openai`, or `azure_openai`. Use `POST /api/ai/test` to run a tiny JSON-only provider check. The test result shows provider, model/deployment, endpoint host, success/failure, HTTP status code, and sanitized error category such as `auth_error`, `not_found`, `bad_request`, `timeout`, `invalid_json`, or `provider_error`. It does not return API keys.

The analysis prompt includes the full local conversation timeline, selected message, sender/recipient roles, contact relationship, approved voice guidance, recent user corrections, and the known proposed action types. Live output must be structured JSON with summary, action type, explanation, confidence, optional draft body, detected due date, proposed lead time, and caveats. Invalid live output falls back to the mock provider.

The analysis provider can recommend:

- no response needed
- reply
- schedule meeting
- ask clarifying question
- mark noise
- unsubscribe review
- create calendar reminder
- follow up later
- archive candidate
- delete candidate
- review needed

Calendar reminders, archive/delete candidates, unsubscribe review, and other actions remain local recommendations only.

### Review package status

Open a review package to approve, reject, edit, or snooze it locally. The status is for local tracking and does not execute anything outside CommsDesk.

### Review drafts

Open the Drafts page from the dashboard header or open a generated draft directly after creating it. The review page shows the source message, selected voice profile, local status, and suggested reply text.

### Voice calibration refresh

Open Voice Calibration from the dashboard header and click **Refresh inferences from Sent Mail**. Then approve/reject/edit inferred VIP and tone guidance so only approved guidance affects draft generation.

### Bulk candidate refresh

Open Bulk Triage and click **Refresh automation candidates** to regenerate local noise/unsubscribe/archive/delete recommendations from stored message patterns and backlog-age signals.

### Prepare execution from draft

From Draft Review, click **Prepare external Gmail draft execution**. Then open the execution record, approve it, and confirm execution from the final confirmation screen.

### Prepare execution from review package

From Review Package detail, click **Prepare execution from this review package**. The execution payload is generated from the package action type and any calendar proposal data.

### Reset contact normal

Removes VIP or noise status from a contact and recalculates existing messages from that sender.

### Edit contact

Opens the contact profile. Saving relationship, importance, alias, VIP/noise, channel, or notes changes recalculates local attention scores for existing messages that match the contact primary email or aliases.

### Admin retention controls

Open `/admin` to run retention cleanup and clear selected local cached content. These controls only affect local storage and do not modify external Gmail/Microsoft accounts.

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
