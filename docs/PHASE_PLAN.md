# RTH CommsDesk Phase Plan

This plan breaks the build into bounded phases suitable for separate LLM sessions. Each session should complete one phase, update documentation, and stop.

## Phase 01 — Usability and structured feedback loop

Primary outcome: make the current Gmail MVP usable and teachable.

Scope:

- Improve dashboard layout and message detail layout.
- Replace raw free-text-only corrections with structured feedback labels.
- Make corrections update classification and attention score immediately.
- Improve rules for job alerts, newsletters, renewal reminders, insurance, invoices, taxes, bills, due dates, expiry dates, and payment deadlines.
- Add clearer actions: Important, Needs Reply, Noise, Reviewed, Details, VIP.
- Add tests for correction behavior and key examples.

Out of scope:

- New connectors.
- AI-generated replies.
- Sending/archive/delete behavior.

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

## Phase 04 — Safe draft reply generation and voice profiles

Primary outcome: generate review-only draft suggestions that fit context.

Scope:

- Implement provider-neutral AI draft service.
- Keep drafts local and unsent.
- Add voice profiles for client, friend, partner, vendor, and short acknowledgement.
- Add approved-example storage if available.
- Add prompt templates that include classification, contact relationship, and user voice guidance.
- Add tests using a mock AI provider.

Safety boundary:

- No auto-send.
- No external Gmail draft creation unless a later phase explicitly approves it.

## Phase 05 — Microsoft 365 connectors: Outlook and Teams

Primary outcome: ingest work communications from Microsoft 365.

Scope:

- Add Microsoft Graph OAuth/configuration path.
- Add read-only Outlook mail ingestion.
- Add Teams message ingestion if permissions allow.
- Normalize messages into the existing source/thread/message model.
- Preserve privacy defaults.
- Add connector tests with mocked Graph responses.

## Phase 06 — Additional notification-source ingestion

Primary outcome: ingest low-risk local notification summaries for channels that do not have clean APIs.

Scope:

- Define a local webhook endpoint for a phone notification bridge.
- Store source as notification-derived, not full-fidelity connector.
- Add dedupe rules for repeated notifications.
- Add channel/source confidence indicators.
- Document limitations clearly.

Safety boundary:

- Do not scrape private platforms.
- Do not attempt to bypass platform restrictions.

## Phase 07 — Search, reporting, and daily briefing

Primary outcome: turn triage data into practical daily workflow.

Scope:

- Add search by contact, source, label, status, and date.
- Add daily briefing view.
- Add neglected-contact detector.
- Add waiting-on-me and waiting-on-them concepts if enough data exists.
- Add export or printable summary.
- Add tests for briefing generation.

## Phase 08 — Deployment, authentication, and production hardening

Primary outcome: make the app safe to run beyond local development.

Scope:

- Add application authentication.
- Move from SQLite to Azure SQL or another managed DB if selected.
- Add environment-specific configuration.
- Add structured logging without sensitive content.
- Add backup/restore guidance.
- Add CI workflow for tests/linting.
- Add deployment documentation.

## Backlog ideas

These are not assigned to a phase yet:

- Calendar-aware importance scoring.
- Client/project tagging.
- Automatic grouping of similar newsletters.
- Mobile-friendly dashboard.
- Browser extension for quick triage.
- Notification digest.
- Vector search over approved reply examples.
- Local LLM option for draft generation.
