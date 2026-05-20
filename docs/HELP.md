# RTH CommsDesk Help

This file is the user-facing help guide. Keep it simple, practical, and current as features are added.

## UI / Design

RTH CommsDesk uses a dark "mission control / operations console" design aligned with the RTH/TaskDesk color palette. All pages share a single stylesheet (`app/web/ui.css`) and a common Jinja2 base template (`base.html`) which provides:

- Sticky dark topbar with brand name and navigation links.
- Connected pill-segment **workflow rail** showing stages: Sync → Triage → Analyze → Review → Prepare → Execute → Audit. Past stages show a subtle green tint (`.done`); the current stage glows amber (`.active`). Amber = work is here now, not success.
- **Next Best Action strip** at the top of the dashboard: a single sentence and button indicating the highest-priority next operator step. Color-coded: red = blocker, amber = pending review, green = queue clear.
- Status dots with green/amber/red glow for provider states.
- Dark panel cards, badges, and button variants.
- Responsive layout at 1280px (`.wrap`) and 1720px (`.wide-wrap`).

### Color palette and semantic tokens

The RTH palette is defined in `ui.css`:
- `--blue`, `--sky`, `--cyan`, `--teal`, `--green`, `--amber`, `--orange`, `--red`, `--pink`, `--purple`, `--indigo`
- Semantic tokens: `--ok` (green), `--warn` (amber), `--bad` (red), `--info` (cyan), `--ai` (purple), `--calendar` (teal)

### Attention queue visual hierarchy

- **Score tiers**: `score-urgent` (red, ≥80), `score-high` (amber, ≥55), `score-medium` (cyan, ≥30), `score-low` (muted, <30).
- **Row accent bars**: `attention-row.urgent` (red left border), `.high` (amber), `.medium` (cyan).
- **Source badges**: `badge.src-gmail` (cyan), `badge.src-outlook` (blue), `badge.src-notification` (purple).
- **Action badges**: `badge.act-reply` (amber), `badge.act-schedule` (teal), `badge.act-review` (purple), `badge.act-noise` (indigo).
- **Row action hierarchy**: Open = `.button.primary` (blue), Important = `.button.amber` (amber), Reviewed = `.button.outline` (muted).

### Command Center pending counts

- Non-zero pending counts (review packages, ready executions) display in amber → action needed.
- Zero counts display in green → nothing pending.


## What RTH CommsDesk does today

RTH CommsDesk helps review communication messages by showing likely important items in an Attention Queue.

Current MVP features:

- Sync recent Gmail inbox messages in read-only mode.
- Backfill older Gmail inbox pages in read-only mode.
- Sync Outlook mailbox messages through the Microsoft connector adapter.
- Keep Teams as a disabled future connector seam; it is not exposed as an operator sync action.
- Ingest notification summaries from SMS/WhatsApp/Messenger-style webhook payloads with confidence metadata.
- Keep Gmail sync metadata locally so repeat syncs are incremental.
- Skip duplicate Gmail messages and duplicate attention items on repeat sync.
- Show the latest sync/backfill counts: fetched, inserted, duplicates skipped, threads updated, and backlog cursor status.
- Show compact dashboard status cards for provider readiness, operational smoke state, command-center queues, source counts, and next recommended operator actions.
- Open the Provider Status page to see live, mock, disabled, missing configuration, dry-run, failed, and not-implemented states for each provider/action, plus copy/paste configuration guidance.
- Open the Operational Smoke page to see Gmail read config, Outlook Graph status, Outlook sync readiness, Azure/OpenAI readiness, execution mode, dry-run state, write flags, source counts, blockers, safe `.env` snippets, and persisted sanitized smoke history.
- Open the Assistant Profile page to inspect approved voice memory, preferred sign-off, pending learned traits, disabled/rejected guidance, relationship overrides, and local draft-preview output.
- Store message metadata and snippets by default.
- Test delegated Microsoft Graph configuration with sanitized `POST /api/graph/test` output.
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
- Run Sent-mail learning to infer VIP candidates, salutation preference, tone guidance, and recurring operator sign-off patterns.
- Review/approve/reject/edit inferred VIP and voice guidance from the Voice Calibration page.
- Approve, reject, edit, disable, or reset learned voice guidance from the Assistant Profile page.
- Generate a local-only draft preview that shows how approved voice memory affects draft wording without creating a Gmail draft, execution record, send, or calendar item.
- Review local draft suggestions from the Drafts page.
- Analyze a stored Gmail conversation with the mock AI provider by default or an OpenAI-compatible/Azure OpenAI provider when explicitly configured.
- Store and view local conversation summaries.
- Store and view proposed action review packages with a recommendation, plain-language evidence, confidence score, optional draft response, correction controls, and local review status.
- Validate structured AI output before storing it and fall back to the mock provider if live AI fails or returns invalid output.
- Generate local calendar availability recommendations for scheduling requests and due-date reminders, without creating past candidates or inventing timed meetings from date-only requests.
- Locally approve, reject, edit, or snooze a review package without changing Gmail or any calendar.
- Filter the attention queue by active/unreviewed, needs reply, important, noise, reviewed, date range, sender/contact, and source: all, Gmail, Outlook, or notification-derived.
- Use Bulk Triage mode for queue pagination beyond the top dashboard slice.
- Generate and review local automation candidates for mark_noise, unsubscribe_review, archive_candidate, and delete_candidate.
- Apply bulk actions and undo recent bulk actions where practical.
- Prepare, approve, and confirm outbound execution records for draft creation, reply send, calendar creation, and label/archive actions.
- Run guarded external execution providers in dry-run mode when explicitly configured; dry-run records do not modify external systems.
- Enable Phase 19 operational test mode for allowlisted Gmail draft/send and Google Calendar test execution while keeping non-test recipients blocked.
- View execution audit trails with payload/result history.
- Enforce web/API authentication when enabled for non-local deployment.
- Provide admin retention controls to clear cached bodies/excerpts and purge aged audit rows.
- Create local backups from `/admin` or `.\scripts\backup-commsdesk.ps1` while excluding `.env`, OAuth token files, and client secrets.

## What it does not do today

RTH CommsDesk does not currently:

- Execute any outbound action without explicit approve + confirm steps.
- Perform live Microsoft Graph mailbox/chat sync without connector service configuration, delegated authorization, and permissions.
- Send Outlook mail, write Outlook calendar events, or sync Teams through live Graph.
- Expose Teams as a daily operator sync action.
- Run non-mock production outbound provider calls by default in local development.
- Perform live external writes unless `EXECUTION_PROVIDER=external`, the specific feature flag is enabled, execution is approved/confirmed, and dry-run has been deliberately disabled.
- Streamline Gmail test execution unless `OPERATIONAL_TEST_MODE=true` and `EXECUTION_TEST_EMAIL_ALLOWLIST` contains the target test recipient.
- Fully live-wire Microsoft Graph Teams or Outlook Calendar without tenant-specific permissions and setup.
- Auto-approve or auto-confirm execution actions.
- Use paid or cloud AI credentials as a requirement for local draft generation.
- Use live AI by default. Live AI is opt-in through environment variables and uses mock fallback.
- Store full email bodies by default.

## Dashboard sections

### Attention Queue

The Attention Queue lists messages that the app thinks may need attention. Higher scores should appear closer to the top. Dashboard rows are compact and show score, source, sender/contact, subject, recommended action, status/date, and the primary review actions.

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

Guidance only affects draft tone after you approve it. Recurring approved sign-off guidance, such as a repeated closing found in sent mail, can be applied to drafts globally unless contact-specific guidance overrides it.

### Assistant Profile

The Assistant Profile page is linked from the main navigation and dashboard. Use it to inspect what the assistant currently knows about the operator's writing style.

It shows:

- preferred sign-off, status, evidence count, and whether drafts will currently use it
- approved global voice traits
- pending learned traits
- rejected and disabled guidance
- avoided phrases and tone/brevity guidance inferred from approved guidance
- relationship-specific overrides
- safe evidence excerpts where stored
- last sent-learning refresh date when available

Guidance actions:

- Approve: marks a pending trait active so draft generation can use it.
- Reject: keeps the trait out of draft generation.
- Edit: changes salutation style, preferred name, or tone notes without changing external systems.
- Disable: leaves an approved trait recorded but inactive.
- Reset default: clears the trait fields and returns it to pending/inactive.

The local draft preview on this page is for inspection only. It renders a sample reply using approved voice memory in memory. It does not create a local draft row, Gmail draft, send, calendar item, execution record, audit row, or external provider request.

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
- date-only meeting interpretations as all-day tentative candidates with a clarifying reply, not invented timed events

Review package detail also shows the evidence behind the recommendation, what would happen if prepared for execution, current correction state, and compact controls to teach the assistant:

- correct action type
- this does or does not need reply
- better summary
- better draft instruction
- correct calendar interpretation
- mark as noise or not noise

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

The dashboard shows the current local runtime mode and links to `/providers` for the full provider matrix. Status lights use:

- Green: operational.
- Amber: warning, manual step, mock, or dry-run.
- Red: broken or blocking.
- Grey: disabled or not implemented.

- AI analysis provider: usually `mock` unless live AI is explicitly configured.
- AI mode/detail: shows whether the app is using the default mock path or a configured live provider with mock fallback.
- Calendar provider: usually `mock` unless a read provider is configured.
- Execution provider: `mock` in local development; execution still requires prepare, approve, and final confirm.
- Gmail full-body sync: `Off` means sync stores metadata/snippets by default and full conversation content is fetched manually from message detail pages.

The Provider Status page distinguishes:

- Live: configured and enabled.
- Mock: deterministic/local fallback.
- Disabled: intentionally off by feature flag.
- Missing configuration: enabled or live-capable but required setup is absent.
- Dry-run: action will record an execution result without writing externally.
- Failed: provider check or runtime execution failed.
- Not implemented: intentionally unavailable until a future phase.

Provider status also classifies each provider/action as live-ready, mock-only, adapter-shape-only, partially wired, or not implemented. It provides configuration snippets and says when a restart is recommended, but it does not edit `.env`.

### Command center dashboard

The dashboard is organized around the daily workflow:

- Workflow breadcrumb: Sync → Triage → Analyze → Review → Prepare → Execute → Audit.
- Consolidated status cards: what is working, what is blocked, what is in dry-run/manual mode, and what to do next.
- Needs My Attention: current filtered attention queue in compact rows.
- Proposed Actions: recent review packages.
- Ready For Approval: execution records waiting for approve or confirm.
- Calendar Candidates: meeting/reminder recommendations.
- Noise And Unsubscribe Candidates: local automation candidates.
- Backlog Progress: reviewed count and pending work indicators.
- Provider Status Warnings: missing config or dry-run states that affect workflow trust.
- Operational Smoke: Gmail, Outlook, AI, execution, dry-run, and write-flag readiness.
- Source Counts: all, Gmail, Outlook, and notification-derived counts with unreviewed attention totals.
- Process next links: open the next attention item, next pending review package, or next execution approval/confirmation.

### Message Detail

Message Detail is for inspecting one conversation and taking local review actions. The conversation timeline and stored bodies wrap and scroll inside the main content column so long messages do not overlap the action sidebar.

Actions are grouped into:

- Message actions.
- Conversation/AI actions.
- Contact actions.
- Draft/execution actions.

Contact controls are context-aware: VIP contacts do not show "Mark Contact VIP", noise contacts do not show "Mark Sender as Noise", and reset appears only for VIP/noise contacts.

### Operational Smoke

Open `/operational-smoke` to answer whether the local workflow is ready to use.

It shows:

- Gmail read configuration and latest sync status.
- Outlook delegated Microsoft Graph authorization and Outlook sync status.
- Azure/OpenAI analysis status with a test action.
- Execution provider mode and dry-run state.
- Phase 19 operational test mode and test recipient allowlist status.
- Whether Gmail draft, Gmail send, and Google Calendar test execution are currently possible.
- Whether Gmail cleanup execution is currently possible, dry-run, mock-only, or blocked.
- Gmail write flags and Google Calendar write flag.
- Mailbox cleanup sender-rollup summary counts and blocked/protected totals.
- Source counts for all, Gmail, Outlook, and notification-derived messages.
- Pending review package and execution queues.
- Operator smoke checklist for route smoke, Azure/OpenAI test, Microsoft Graph delegated test, Outlook sync readiness, Gmail draft dry-run/live readiness, Google Calendar readiness, and execution audit checks.
- Run Smoke Now button that persists a sanitized local smoke run and per-check result history.
- Recent smoke history and smoke detail pages with pass/warning/fail/skipped status and next actions.
- Direct route smoke links, including `/assistant-profile`.
- Plain-language token/config blockers.
- Disabled Microsoft write boundaries: Outlook send, Outlook Calendar, and Teams.
- Copy/paste configuration snippets for safe local defaults, delegated Outlook read, and optional live AI setup. The page does not edit `.env`; restart the app after changing environment variables.

For controlled test execution, configure `.env` manually:

```env
OPERATIONAL_TEST_MODE=true
EXECUTION_TEST_EMAIL_ALLOWLIST=test-recipient@example.com
EXECUTION_PROVIDER=external
EXTERNAL_WRITE_DRY_RUN=true
```

Use exact test email addresses whenever possible. Explicit domain entries such as `@example.com` are supported, but non-allowlisted recipients remain blocked. Gmail send requires `EXTERNAL_WRITE_DRY_RUN=false` and still requires explicit approval plus final confirmation.

Smoke persistence stores only sanitized operational metadata, status counts, configuration booleans, route names, provider states, and next actions. It does not store OAuth tokens, private keys, message bodies, email body content, full external payloads, or private message text.

### Daily Gmail cleanup runbook

Use this runbook when you want to process mailbox cleanup candidates with controlled Gmail label and archive actions.

Prerequisites:
- App is running (`.\scripts\start-commsdesk.ps1`).
- Gmail is synced and has recent messages.
- Cleanup candidates have been refreshed.

**Step 1: Check environment posture**

Run the operator script before doing anything:

```powershell
.\scripts\test-gmail-cleanup-execution.ps1
```

This shows current flag values and the effective posture (mock, dry-run, live, or blocked). It does not modify anything.

**Step 2: Verify required flags**

For dry-run validation:

```env
EXECUTION_PROVIDER=external
GMAIL_WRITE_ENABLED=true
GMAIL_LABEL_ARCHIVE_ENABLED=true
OPERATIONAL_TEST_MODE=true
EXTERNAL_WRITE_DRY_RUN=true   # keep true until dry-run is confirmed safe
```

For live Gmail cleanup (only after successful dry-run):

```env
EXTERNAL_WRITE_DRY_RUN=false
```

**Step 3: Refresh cleanup candidates**

Open `/bulk-triage/mailbox-cleanup` or run:

```powershell
.\scripts\smoke-mailbox-cleanup.ps1
```

**Step 4: Review high-confidence senders**

Open `/bulk-triage/mailbox-cleanup`. Review the sender list. Check:
- Confidence score and recommended action
- Protected status (never cleanup a protected sender)
- Evidence summary and sample subjects

**Step 5: Mark sender noise if not already done**

Use the "Mark Sender as Noise" button on the cleanup detail page if needed. This updates the local contact and adjusts the rollup.

**Step 6: Prepare a cleanup execution**

On the cleanup candidate detail page, click one of:
- **Prepare label** — adds RTH-Cleanup label to all messages from this sender. Messages stay in inbox.
- **Prepare archive** — removes INBOX label. Messages move to archive.
- **Prepare label + archive** — both. Label makes recovery easier.

This creates an execution record. No Gmail write occurs yet. You are redirected to `/executions`.

**Step 7: Review the execution detail page**

Open the execution record in `/executions`. Read the **Gmail Cleanup Confirmation** section carefully:
- Sender email and domain
- Number of messages affected
- Cleanup mode (label / archive / both)
- Whether the action will actually write to Gmail (posture)
- Recovery guidance

If the message count is >50, an extra warning is shown. Double-check the sender is correct.

**Step 8: Approve**

Click **Approve** in the execution controls. Status changes to `approved`.

**Step 9: Confirm and execute**

Click **Confirm and execute**. If dry-run mode is on, the result will show `status: dry_run` and Gmail is not modified. If live mode is on, Gmail is modified.

**Step 10: Verify the audit trail**

Scroll to the audit trail section on the execution detail page. Confirm the result matches expectations. For dry-run: verify `status: dry_run`. For live: verify `status: applied` with `succeeded_count` matching `attempted_count`.

**Recovery**

If a cleanup action modified Gmail unintentionally:
- For **cleanup_label**: search Gmail for `label:<label_name>` to find all affected messages. Select all and remove the label.
- For **cleanup_archive**: search Gmail for `from:<sender_email> in:archive`. Select all and move to inbox.
- For **cleanup_label_and_archive**: search Gmail for `label:<label_name> from:<sender_email>`. Select all, move to inbox, remove label.

No messages are permanently deleted by any cleanup action. Cleanup is always reversible.

**Rollback to safe mode**

```env
EXECUTION_PROVIDER=mock
EXTERNAL_WRITE_DRY_RUN=true
GMAIL_WRITE_ENABLED=false
GMAIL_LABEL_ARCHIVE_ENABLED=false
```

Restart the app after changing `.env`.

### Daily operator runbook

From the repo root:

```powershell
.\scripts\start-commsdesk.ps1
```

Open these in order:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/operational-smoke
http://127.0.0.1:8000/providers
http://127.0.0.1:8000/assistant-profile
```

Daily workflow:

1. Start the app with `.\scripts\start-commsdesk.ps1`; it activates `.venv`, runs migrations, optionally backs up local SQLite, and starts Uvicorn.
2. Run smoke from `/operational-smoke` or `.\scripts\smoke-commsdesk.ps1`.
3. Use the dashboard Start Here Today lane to check last smoke, last Gmail sync, last Outlook sync, pending review packages, ready executions, pending voice guidance, and provider blockers.
4. Sync Gmail from the dashboard.
5. Run `POST /api/graph/test` before Outlook sync, then sync Outlook only after Graph is healthy.
6. Run `./scripts/smoke-mailbox-cleanup.ps1` to refresh sender rollups, print cleanup summary counts, and verify cleanup dry-run/live posture.
7. Review `/bulk-triage/mailbox-cleanup` and inspect high-confidence senders, protected senders, and blocked candidates.
8. Prepare cleanup executions only when evidence and posture are clear. No Gmail mutation occurs until approve + final confirm.
9. Review packages and local drafts.
10. Prepare draft/execution records locally.
11. Dry-run first. For Gmail draft or Calendar testing, use `OPERATIONAL_TEST_MODE=true`, `EXECUTION_PROVIDER=external`, `EXTERNAL_WRITE_DRY_RUN=true`, and an explicit `EXECUTION_TEST_EMAIL_ALLOWLIST`.
12. Live Gmail draft creation requires operational test mode, allowlist, feature flags, approval, final confirmation, and `EXTERNAL_WRITE_DRY_RUN=false`.
13. Verify `/executions` audit after any dry-run or live execution.
14. Run `./scripts/backup-commsdesk.ps1` before risky config changes.

OAuth reauthorization:

- Gmail read/write: run `.\scripts\reauth-commsdesk.ps1 -Gmail`. Required scopes are `https://www.googleapis.com/auth/gmail.readonly`, `https://www.googleapis.com/auth/gmail.compose`, `https://www.googleapis.com/auth/gmail.send`, and `https://www.googleapis.com/auth/gmail.modify`.
- Google Calendar: run `.\scripts\reauth-commsdesk.ps1 -GoogleCalendar`. Required scopes are `https://www.googleapis.com/auth/calendar.freebusy` and `https://www.googleapis.com/auth/calendar.events`.
- Microsoft Graph delegated auth: run `.\scripts\reauth-commsdesk.ps1 -MicrosoftGraph`. Required scopes are `User.Read Mail.Read offline_access`. The Entra app must allow public client flows for local delegated auth.
- The reauth script deletes only the selected token file. It does not delete `.env`, client secrets, or client configuration.

Common blockers:

- AI test fails: check `AI_PROVIDER`, provider endpoint shape, deployment/model, and API key outside the UI.
- Graph test asks for authorization: complete device-code login, then retry `POST /api/graph/test`.
- Graph delegated auth fails with a client-secret assertion error: enable public client/native client flows in Entra, delete `microsoft_graph_token.json`, and retry.
- Gmail draft live execution fails for scopes: enable write flags, delete `gmail_token.json`, and reauthorize.
- Test execution blocked: confirm operational test mode, external provider mode, allowlist, action flags, dry-run posture, approval, and final confirmation.

Rollback to safe mode:

```env
EXECUTION_PROVIDER=mock
EXTERNAL_WRITE_DRY_RUN=true
OPERATIONAL_TEST_MODE=false
EXECUTION_TEST_EMAIL_ALLOWLIST=
GMAIL_WRITE_ENABLED=false
GMAIL_DRAFT_CREATE_ENABLED=false
GMAIL_SEND_ENABLED=false
GMAIL_LABEL_ARCHIVE_ENABLED=false
GOOGLE_CALENDAR_WRITE_ENABLED=false
```

Restart Uvicorn after changing `.env`.

### Sync Outlook

Runs Outlook ingestion through the Microsoft connector adapter. With delegated Microsoft Graph configured, Outlook mail read uses `GET /me/messages` for `MICROSOFT_ACCOUNT=me` or `/users/{MICROSOFT_ACCOUNT}/messages` for a configured mailbox. Records are normalized into the same local thread/message model used by Gmail and appear with source `outlook`.

Delegated local setup uses:

- `MICROSOFT_GRAPH_ENABLED=true`
- `MICROSOFT_GRAPH_OUTLOOK_MAIL_ENABLED=true`
- `MICROSOFT_GRAPH_AUTH_MODE=delegated`
- `MICROSOFT_GRAPH_SCOPES=User.Read Mail.Read offline_access`
- `MICROSOFT_GRAPH_TOKEN_FILE=./microsoft_graph_token.json`
- `MICROSOFT_TENANT_ID`
- `MICROSOFT_CLIENT_ID`

Use `POST /api/graph/test` before syncing Outlook. The test returns only sanitized status: auth mode, account, configured booleans, success/failure, HTTP status if available, and sanitized error category/message. It never returns access tokens, refresh tokens, or client secrets. If delegated authorization is required, complete the Microsoft device login and retry the test.

Outlook sync is read-only. It uses Graph `$select` to request only the fields needed for local triage and follows pages safely up to the requested limit.

Future Outlook write planning only:

- Outlook send would require future delegated Graph write scopes such as `Mail.Send` and possibly `Mail.ReadWrite`.
- Outlook calendar write would require future delegated calendar scopes such as `Calendars.ReadWrite`.
- Any future Outlook write path must mirror Gmail execution gating: prepare, approve, confirm, audit, provider status, feature flags, operational test mode, allowlist where recipient-specific, and dry-run before live writes.
- Current CommsDesk code makes no Outlook send or Outlook calendar write calls and shows these providers as disabled/not implemented.

### Sync Teams

Teams remains disabled/not implemented for live Graph and is not part of the operational dashboard workflow. The adapter shape is preserved for future work, but Outlook mail read is the only Microsoft Graph sync path currently intended for local smoke testing.

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

If approved voice guidance exists, draft generation also applies inferred salutation style/preferred name, tone notes, and recurring sign-off guidance (for example, to avoid full-name formal greetings in friend threads, keep client replies concise, or use an approved operator closing). Send-ready drafts strip generic placeholders such as `[Your Name]`, `[Your signature]`, `[your name]`, and `[signature]`.

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

### Mailbox cleanup workflow

Open `/bulk-triage/mailbox-cleanup` to work at sender/domain level instead of one message at a time.

What to review first:

- High-confidence cleanup senders.
- Protected senders (intentionally blocked).
- Evidence summary, confidence, and affected message counts.
- Cleanup posture: blocked, mock-only, dry-run, or live-capable.

Safety boundaries:

- The cleanup pages do not mutate Gmail directly.
- Gmail cleanup can only be prepared from mailbox cleanup, then executed from `/executions` after explicit approve + confirm.
- Protected senders remain blocked unless manually reset.
- Delete remains conservative and non-permanent in this workflow.

Real-inbox smoke helper:

- Run `./scripts/smoke-mailbox-cleanup.ps1`.
- Optional switches: `-RunMigrations`, `-RunSyncIfNeeded`, `-RunBackfillPage`, `-Open`.
- The script refreshes cleanup candidates and prints sender-rollup counts plus execution posture.

### Prepare execution from draft

From Draft Review, click **Prepare external Gmail draft execution**. Then open the execution record, approve it, and confirm execution from the final confirmation screen.

Review notes stay in CommsDesk; external Gmail drafts must be send-ready. The Draft Review page can show review-only notes, caveats, and explanation text, but the Gmail execution payload uses only the clean subject and user-facing email body. CommsDesk strips review-only labels, caveats, internal reasoning, and duplicated `Subject:` lines before preparing a Gmail draft payload.

When `EXECUTION_PROVIDER=mock`, confirmation records a mock result. When `EXECUTION_PROVIDER=external` and dry-run is on, confirmation records a dry-run result with `external_write_performed=false`. Phase 19 external Gmail draft execution additionally requires `OPERATIONAL_TEST_MODE=true`, `EXECUTION_TEST_EMAIL_ALLOWLIST`, `GMAIL_WRITE_ENABLED=true`, and `GMAIL_DRAFT_CREATE_ENABLED=true`.

If a live Gmail execution says the token has insufficient authentication scopes, delete `gmail_token.json` and re-authorize after enabling the required Gmail write flag. Read-only sync tokens do not automatically gain compose, send, or modify scopes.

When any Gmail write flag is enabled, CommsDesk asks Google for the combined Gmail scope set: `https://www.googleapis.com/auth/gmail.readonly`, `https://www.googleapis.com/auth/gmail.compose`, `https://www.googleapis.com/auth/gmail.send`, and `https://www.googleapis.com/auth/gmail.modify`. CommsDesk checks the stored token scopes before reuse. If `gmail_token.json` is missing one of those scopes, it forces reauthorization or reports the exact missing scopes.

### Prepare execution from review package

From Review Package detail, click **Prepare execution from this review package**. The execution payload is generated from the package action type and any calendar proposal data.

Review package detail shows the item position, conversation timeline, recommendation, explanation, confidence, contact context, matched voice guidance, and local status controls before execution is prepared.

Execution records are immutable attempts. A draft or review package can have multiple attempts, and each attempt keeps its own payload, status, provider result/error, timestamps, and audit trail. From an execution detail page, use **Prepare New Execution** to regenerate from the current source artifact, **Re-run Execution** to create a new attempt with the same payload, or **Clone as New Execution** to copy the payload into a fresh pending-review attempt. Every new attempt still requires approval and final confirmation.

Calendar execution uses `GOOGLE_CALENDAR_TIME_ZONE`, defaulting to `America/Vancouver`, and includes that time zone on both the start and end payload values.

Phase 19 Google Calendar test execution requires `OPERATIONAL_TEST_MODE=true`, `EXECUTION_PROVIDER=external`, and `GOOGLE_CALENDAR_WRITE_ENABLED=true`. Dry-run is allowed and clearly records that no external write occurred. Live calendar creation requires final confirmation after reviewing the target calendar and event payload.

### Reset contact normal

Removes VIP or noise status from a contact and recalculates existing messages from that sender.

### Edit contact

Opens the contact profile. Saving relationship, importance, alias, VIP/noise, channel, or notes changes recalculates local attention scores for existing messages that match the contact primary email or aliases.

### Admin retention controls

Open `/admin` to run retention cleanup and clear selected local cached content. These controls only affect local storage and do not modify external Gmail/Microsoft accounts.

Use **Create Local Backup** before risky configuration changes. The backup ZIP includes local SQLite, `.env.example`, and key docs. It excludes `.env`, `gmail_token.json`, `google_calendar_token.json`, `microsoft_graph_token.json`, and `client_secret.json` by default.

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
