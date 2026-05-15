# RTH CommsDesk Phase Plan

This plan breaks the build into bounded phases suitable for separate LLM sessions. Each session should complete one phase, update documentation, and stop.

## Product target

RTH CommsDesk is an assistant-grade communications operations console. It should not be limited to a feed of snippets and manual VIP/noise buttons.

The intended end-state is:

```text
High-volume communication ingestion
→ full thread/conversation context
→ AI-assisted summaries and recommendations
→ historical learning from sent mail and user corrections
→ bulk triage and noise automation
→ calendar-aware scheduling recommendations
→ user-approved outbound execution
```

Every phase should move toward useful automation and insight while keeping actions explainable, auditable, and under explicit user control when external systems are modified.

## Completed phases

## Phase 01 — Usability and structured feedback loop

Primary outcome: make the current Gmail MVP usable and teachable.

Scope:

- Improve dashboard layout and message detail layout.
- Replace raw free-text-only corrections with structured feedback labels.
- Make corrections update classification and attention score immediately.
- Improve rules for job alerts, newsletters, renewal reminders, insurance, invoices, taxes, bills, due dates, expiry dates, and payment deadlines.
- Add clearer actions: Important, Needs Reply, Noise, Reviewed, Details, VIP.
- Add tests for correction behavior and key examples.

Status: completed.

## Phase 02 — Durable Gmail sync and local data reliability

Primary outcome: make Gmail ingestion repeatable, safe, and predictable.

Scope:

- Add persistent sync metadata/high-water mark.
- Add safe resync behavior.
- Improve duplicate handling and thread metadata updates.
- Clarify local SQLite reset and migration behavior.
- Resolve `init_db()` versus Alembic lifecycle conflict.
- Add operational diagnostics for sync results.
- Add tests for incremental sync and duplicate protection.

Status: completed.

## Phase 03 — Contact intelligence and relationship-aware triage

Primary outcome: make the app understand who matters.

Scope:

- Add stronger contact profile fields and aliases.
- Add relationship types such as partner, close friend, client, prospect, vendor, newsletter, system.
- Add contact-level notes and default channel.
- Add contact importance rules and contact-level score adjustments.
- Add a contact management screen.
- Add contact correction history.
- Add tests for relationship-aware scoring.

Status: completed.

## Phase 04 — Safe draft reply generation and voice profiles

Primary outcome: generate local review-only draft suggestions.

Scope:

- Implement provider-neutral AI draft service.
- Keep drafts local and unsent.
- Add voice profiles for client, friend, partner, vendor, and short acknowledgement.
- Add approved-example storage if available.
- Add prompt templates that include classification, contact relationship, and user voice guidance.
- Add tests using a mock AI provider.

Status: completed.

Known limitation: Phase 04 drafts are not yet sufficiently context-aware because the app does not yet fetch and summarize full Gmail conversation content or learn voice from sent mail.

## Next phases

## Phase 05 — Gmail conversation context and full-content ingestion

Primary outcome: stop treating isolated snippets as enough context.

Scope:

- Fetch Gmail thread/conversation metadata and messages, not just isolated inbox items.
- Store conversation/thread membership clearly.
- Retrieve message bodies using a configurable body-storage policy.
- Prefer normalized plain-text bodies with HTML stripped/sanitized.
- Preserve enough quoted/reply structure to understand who said what.
- Show conversation timeline on message detail pages.
- Distinguish sender, recipients, CC, dates, and message order.
- Add a larger historical backfill path so the queue can progress beyond the same 100 items.
- Add reviewed/noise/important filters that allow the user to keep moving through thousands of messages.
- Add tests for thread grouping, body extraction, and historical pagination.

Out of scope:

- AI response quality tuning beyond providing richer context.
- External send/archive/delete/unsubscribe behavior.
- Calendar execution.

Status: completed.

## Phase 06 — AI summarization and proposed action intelligence

Primary outcome: start producing useful intelligence, not generic replies.

Scope:

- Add provider-neutral AI analysis service with mock provider for tests.
- Generate conversation summaries from full thread context.
- Determine whether a response is needed.
- Recommend action types such as no_response_needed, reply, schedule_meeting, ask_clarifying_question, mark_noise, unsubscribe_review, create_calendar_reminder, follow_up_later, archive_candidate, delete_candidate.
- Store proposed actions/review packages locally.
- Explain why the action was recommended.
- Improve draft generation using conversation summary, full thread context, contact relationship, and proposed action type.
- Ensure simple acknowledgement messages can correctly produce "no response needed".
- Add UI for review packages: summary, recommendation, draft if needed, confidence, and actions to approve/reject/edit locally.
- Add tests for scenarios including dinner cancellation acknowledgements, renewal reminders, obvious newsletters, client requests, and vague emails.

Out of scope:

- Actually sending, deleting, archiving, unsubscribing, or creating calendar events externally.

## Phase 07 — Sent-mail learning, VIP inference, and voice calibration

Primary outcome: make the assistant learn how Rohan actually communicates.

Scope:

- Ingest Gmail Sent Mail metadata and selected sent-message content for learning.
- Infer likely VIP contacts from sent frequency, recency, reply patterns, and manual corrections.
- Learn greeting/name preferences per contact, such as first-name only, nickname, no greeting, or formal name.
- Learn tone patterns by relationship type: friend, close friend, client, vendor, family, system/newsletter.
- Store voice examples and derived style notes without exposing them in logs.
- Add a voice profile calibration screen.
- Improve draft generation to avoid unnatural generic phrases and avoid full names for friends unless historically used.
- Add tests for inferred salutation, friend tone, client tone, and VIP inference.

Out of scope:

- Sending email.
- Calendar write actions.

## Phase 08 — Bulk triage and noise automation

Primary outcome: make the app useful for a 7,000+ email backlog.

Scope:

- Add bulk backlog mode with pagination and progress tracking.
- Add triage batches beyond the current top 100 items.
- Add bulk reviewed/noise/important actions with undo where practical.
- Detect repeated low-value senders and newsletter patterns.
- Detect likely unsubscribe links and present unsubscribe review candidates.
- Detect never-opened or never-replied sender patterns if data is available.
- Add safe candidate lists for archive/delete/noise/unsubscribe, with reasons and confidence.
- Add explicit approval workflow for destructive or external actions.
- Add tests for bulk pagination, status progression, and candidate generation.

Out of scope:

- Performing actual delete/archive/unsubscribe against Gmail unless split into an approved execution subphase.

## Phase 09 — Calendar availability and scheduling recommendations

Primary outcome: recommend scheduling actions with real availability context.

Scope:

- Add Google Calendar read-only availability integration.
- Add Outlook Calendar read-only availability integration if Microsoft auth exists or is introduced.
- Detect date/time proposals in conversations.
- Show availability/conflict reasoning.
- Prepare proposed calendar actions locally.
- Support reminder suggestions, such as ICBC renewal reminder one week before due date.
- Add tests with mocked calendar data.

Out of scope:

- Creating or sending calendar events externally.

## Phase 10 — Approved outbound execution

Primary outcome: execute communication actions only after explicit approval.

Scope:

- Add execution engine for approved proposed actions.
- Send Gmail replies after explicit approval.
- Create Gmail drafts externally if selected.
- Create calendar events/invitations after explicit approval.
- Add optional Gmail label/archive actions after explicit approval.
- Add duplicate-execution prevention.
- Add audit log for what was executed, when, by whom, and from which proposed action.
- Add final confirmation screen for send/delete/archive/unsubscribe/calendar writes.
- Add tests with mocked Gmail/Calendar write APIs.

Out of scope:

- Fully autonomous unsupervised sending/deleting.

## Phase 11 — Microsoft 365 and additional communication connectors

Primary outcome: expand sources after Gmail intelligence is useful.

Scope:

- Add Microsoft Graph OAuth/configuration path.
- Add Outlook mail ingestion.
- Add Teams message ingestion if permissions allow.
- Normalize messages into the existing source/thread/message model.
- Add optional phone notification webhook for SMS/WhatsApp/Messenger-style notification summaries.
- Add source confidence indicators for notification-derived records.
- Add connector tests with mocked responses.

Safety boundary:

- Do not scrape private platforms or bypass platform restrictions.
- Do not reply through notification-only sources.

## Phase 12 — Deployment, authentication, and production hardening

Primary outcome: make the app safe to run beyond local development.

Scope:

- Add application authentication.
- Move from SQLite to Azure SQL or another managed DB if selected.
- Add environment-specific configuration.
- Add structured logging without sensitive content.
- Add backup/restore guidance.
- Add CI workflow for tests/linting.
- Add deployment documentation.
- Add production security checklist.

## Backlog ideas

- Browser extension for quick triage.
- Mobile-friendly approval console.
- Notification digest.
- Local LLM option for analysis and drafting.
- Vector search over approved reply examples.
- Contact/project/client tagging.
- SLA-like reminders for important contacts.
- Natural-language command bar, e.g. "show me everything from Michael that I owe a response to".
