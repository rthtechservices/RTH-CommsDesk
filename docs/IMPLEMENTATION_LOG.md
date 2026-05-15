# Implementation Log

Record completed work here at the end of every phase. Newest entries should be added at the top.

## Entry template

```markdown
## YYYY-MM-DD — Phase XX: <title>

### Summary
- 

### Files changed
- 

### Tests run
- `pytest -q` — pass/fail

### Smoke tests
- App startup:
- Dashboard:
- Key workflow:

### Documentation updated
- 

### Known issues
- 

### Recommended next actions
- 
```

## 2026-05-15 — Phase 11: Microsoft 365 and Additional Communication Connectors

### Summary
- Added Microsoft-source connector paths for Outlook and Teams ingestion, normalized into the existing message/thread model.
- Added notification-summary webhook ingestion for SMS/WhatsApp/Messenger-style payloads with duplicate-safe upsert behavior.
- Added source channel and source confidence metadata to stored messages with migration support.
- Added UI source-confidence indicators and source filters for connector-derived and notification-derived records.
- Added connector-focused tests for Outlook sync, Teams sync, and notification webhook duplicate handling.

### Files changed
- `app/models/entities.py`
- `alembic/versions/0011_connector_source_confidence.py`
- `app/connectors/base.py`
- `app/connectors/gmail/client.py`
- `app/connectors/outlook/client.py`
- `app/connectors/outlook/__init__.py`
- `app/connectors/teams/client.py`
- `app/connectors/teams/__init__.py`
- `app/connectors/notifications/webhook.py`
- `app/connectors/notifications/__init__.py`
- `app/services/gmail_sync_service.py`
- `app/services/external_connectors_service.py`
- `app/api/routes.py`
- `app/web/routes.py`
- `app/web/templates/dashboard.html`
- `app/web/templates/message_detail.html`
- `tests/test_external_connectors.py`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_11_CONNECTORS.md`
- `docs/PHASE_PLAN.md`
- `docs/PHASE_STATUS.md`
- `README.md`

### Tests run
- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 71 tests.

### Smoke tests
- App startup: not run manually in this phase.
- Dashboard: covered by route tests.
- Key workflow: automated tests cover Outlook ingestion, Teams ingestion, notification webhook dedupe, and source-confidence persistence.

### Documentation updated
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_11_CONNECTORS.md`
- `docs/PHASE_PLAN.md`
- `docs/PHASE_STATUS.md`
- `README.md`

### Known issues
- Outlook/Teams connectors currently rely on injected Graph-service adapters; full live OAuth client flows remain environment configuration work.
- Notification-source records are summary fidelity and should not be treated as full message context for high-risk actions.

### Recommended next actions
- Proceed to Phase 12: Deployment, authentication, and production hardening.

## 2026-05-15 — Phase 10: Approved Outbound Execution

### Summary
- Added an execution engine with explicit states: pending_review, approved, executing, executed, failed, cancelled.
- Added idempotent execution records with duplicate-prevention keys for draft and review-package actions.
- Added final confirmation flows in web/API for approved execution records before provider calls are run.
- Added audit logging for prepare/approve/confirm/executed/failed/cancelled events with actor and payload details.
- Added mocked execution provider coverage for external Gmail draft creation, Gmail reply send, calendar event/reminder creation, and label/archive actions.

### Files changed
- `app/models/entities.py`
- `alembic/versions/0010_execution_engine.py`
- `app/services/execution_service.py`
- `app/api/routes.py`
- `app/web/routes.py`
- `app/web/templates/dashboard.html`
- `app/web/templates/draft_review.html`
- `app/web/templates/review_package_detail.html`
- `app/web/templates/executions.html`
- `app/web/templates/execution_detail.html`
- `tests/test_execution_service.py`
- `tests/test_draft_generation.py`
- `tests/test_app_bootstrap.py`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_10_APPROVED_OUTBOUND_EXECUTION.md`
- `docs/PHASE_STATUS.md`

### Tests run
- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 68 tests.

### Smoke tests
- App startup: not run manually in this phase.
- Dashboard: covered by route tests.
- Key workflow: automated tests cover draft execution, reply execution, calendar execution, label/archive execution, duplicate-prevention behavior, and audit trail generation.

### Documentation updated
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_10_APPROVED_OUTBOUND_EXECUTION.md`
- `docs/PHASE_STATUS.md`

### Known issues
- Provider calls are currently mock-backed; real Gmail/Calendar write scopes and production credential wiring remain environment-dependent.
- Destructive delete/unsubscribe execution remains guarded by explicit confirmation token and is not surfaced as default UI workflow.

### Recommended next actions
- Proceed to Phase 11: Microsoft 365 and additional communication connectors.

## 2026-05-15 — Phase 09: Calendar Availability and Scheduling Recommendations

### Summary
- Added a provider-neutral calendar availability service with mock, Google-read-only, and Outlook-read-only provider shapes.
- Added local calendar action proposals tied to review packages with availability reasoning, conflicts, suggested windows, and reminder/meeting timing.
- Integrated calendar recommendation logic into conversation analysis for due-date reminders and scheduling requests.
- Added review package UI/API visibility for calendar proposal details and availability explanation.
- Added tests for reminder inference, free-slot offer-availability recommendations, and conflict-driven clarification recommendations.

### Files changed
- `app/models/entities.py`
- `alembic/versions/0009_calendar_action_proposals.py`
- `app/services/calendar_availability_service.py`
- `app/services/analysis_service.py`
- `app/api/routes.py`
- `app/web/templates/review_package_detail.html`
- `app/core/config.py`
- `tests/test_calendar_availability.py`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_09_CALENDAR_AVAILABILITY.md`
- `docs/PHASE_STATUS.md`

### Tests run
- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 62 tests.

### Smoke tests
- App startup: not run manually in this phase.
- Dashboard: covered by route tests.
- Key workflow: automated tests cover due-date reminder proposals, availability-offer responses, and conflict-aware clarification drafts.

### Documentation updated
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_09_CALENDAR_AVAILABILITY.md`
- `docs/PHASE_STATUS.md`

### Known issues
- Google/Outlook calendar providers are read-only shape integrations; live credential-backed availability checks still require environment-specific setup.
- Meeting date/time extraction remains deterministic and can be improved for more complex natural-language scheduling requests.

### Recommended next actions
- Proceed to Phase 10: Approved outbound execution.

## 2026-05-15 — Phase 08: Bulk Triage and Noise Automation

### Summary
- Added bulk triage mode with queue-specific pagination that can move beyond the first 100 attention items.
- Added local automation candidate generation for mark-noise, unsubscribe review, archive candidate, and delete candidate recommendations.
- Added queue controls for unreviewed, needs reply, important, proposed actions, noise candidates, unsubscribe candidates, and reviewed views.
- Added bulk actions for reviewed/noise/important, contact-relationship assignment, and local approval of no-response-needed review packages.
- Added undo support for logged bulk actions where practical through bulk action logs.

### Files changed
- `app/models/entities.py`
- `alembic/versions/0008_bulk_triage_candidates.py`
- `app/services/bulk_triage_service.py`
- `app/api/routes.py`
- `app/web/routes.py`
- `app/web/templates/dashboard.html`
- `app/web/templates/bulk_triage.html`
- `tests/test_bulk_triage.py`
- `tests/test_app_bootstrap.py`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_08_PRODUCTION_HARDENING.md`
- `docs/PHASE_STATUS.md`

### Tests run
- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 59 tests.

### Smoke tests
- App startup: not run manually in this phase.
- Dashboard: covered by route tests.
- Key workflow: automated tests cover backlog pagination, candidate generation, bulk status updates, and undo behavior.

### Documentation updated
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_08_PRODUCTION_HARDENING.md`
- `docs/PHASE_STATUS.md`

### Known issues
- Bulk undo currently restores tracked state transitions but does not attempt to rewind all derived scoring side effects.
- Candidate generation is deterministic and local; heuristic tuning can be expanded with more engagement history signals.

### Recommended next actions
- Proceed to Phase 09: Calendar availability and scheduling recommendations.

## 2026-05-15 — Phase 07: Sent-Mail Learning, VIP Inference, and Voice Calibration

### Summary
- Added Gmail Sent-mail learning ingestion and local storage that keeps learning records separate from inbound triage rows.
- Added inferred VIP candidates using sent frequency, recency, reply patterns, relationship type, and correction history.
- Added inferred voice guidance with salutation style, preferred name, and tone notes at both contact and relationship scope.
- Added a Voice Calibration screen with reviewable/editable approve/reject controls for VIP and voice guidance.
- Updated local mock draft generation to use approved guidance and avoid generic filler when learned tone notes request it.

### Files changed
- `app/models/entities.py`
- `alembic/versions/0007_sent_mail_learning.py`
- `app/connectors/base.py`
- `app/connectors/gmail/client.py`
- `app/services/voice_learning_service.py`
- `app/services/draft_service.py`
- `app/api/routes.py`
- `app/web/routes.py`
- `app/web/templates/dashboard.html`
- `app/web/templates/voice_calibration.html`
- `tests/test_voice_learning.py`
- `tests/test_app_bootstrap.py`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_07_SEARCH_BRIEFING.md`
- `docs/PHASE_STATUS.md`

### Tests run
- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 54 tests.

### Smoke tests
- App startup: not run manually in this phase.
- Dashboard: covered by route tests.
- Key workflow: automated tests cover sent-mail ingestion, VIP inference, inferred salutation, friend/client draft tone, and approved guidance usage.

### Documentation updated
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_07_SEARCH_BRIEFING.md`
- `docs/PHASE_STATUS.md`

### Known issues
- Sent-mail learning currently pulls only Gmail Sent messages; Microsoft sent-mail learning remains future connector scope.
- Inference uses excerpted local text and deterministic heuristics; additional tuning can improve edge-case salutation detection.

### Recommended next actions
- Proceed to Phase 08: Bulk triage and noise automation.

## 2026-05-15 — Phase 06: AI Summarization and Proposed Action Intelligence

### Summary
- Added a provider-neutral AI analysis service with a deterministic mock provider for local development and tests.
- Added local conversation summaries and proposed action review packages linked to source messages and threads.
- Added proposed action recommendations for no response, reply, clarification, newsletter/noise, unsubscribe review, calendar-reminder candidates, and fallback review.
- Improved local draft generation context so it can use full stored thread context, conversation summary, proposed action type, relationship, importance, and correction history.
- Added review-package UI and API routes showing summary, recommendation, explanation, confidence, optional draft response, and local approve/reject/edit/snooze status.
- Kept all recommendations local; no email send, Gmail draft creation, archive/delete/label/unsubscribe, or calendar-write behavior was added.

### Files changed
- `app/models/entities.py`
- `app/services/analysis_service.py`
- `app/services/draft_service.py`
- `app/api/routes.py`
- `app/web/routes.py`
- `app/web/templates/dashboard.html`
- `app/web/templates/message_detail.html`
- `app/web/templates/review_packages.html`
- `app/web/templates/review_package_detail.html`
- `alembic/versions/0006_ai_review_packages.py`
- `tests/test_ai_analysis.py`
- `tests/test_app_bootstrap.py`
- `README.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_06_NOTIFICATION_SOURCES.md`
- `README.md`

### Tests run
- `python -m pytest -q` — passed, 50 tests.

### Smoke tests
- App startup: `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8036` started successfully and `GET /` returned HTTP 200.
- Dashboard: startup smoke confirmed the dashboard renders with the new review-package panel.
- Key workflow: automated tests cover dinner cancellation acknowledgement, ICBC renewal reminder candidate, newsletter/unsubscribe review, client request draft specificity, vague clarification, draft context enrichment, and local-only review package status updates.

### Documentation updated
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_06_NOTIFICATION_SOURCES.md`

### Known issues
- The analysis provider is deterministic/mock-only for local development; no production AI provider is configured yet.
- Analysis uses the locally stored conversation context. Gmail full conversation fetch remains manual unless the user has already stored full thread content.
- Review package approval/rejection/edit/snooze is local status only and does not execute external actions.
- Sent-mail style learning and voice calibration remain Phase 07 scope.

### Recommended next actions
- Human review and smoke-test Phase 06 with real Gmail threads, especially the dinner-cancellation and ICBC renewal scenarios.
- After review, proceed to Phase 07: Sent-mail learning, VIP inference, and voice calibration.

## 2026-05-15 — Phase 05: Gmail Conversation Context and Full-Content Ingestion

### Summary
- Added Gmail conversation-context support so selected messages can fetch and store the full Gmail thread in read-only mode.
- Added normalized recipient and CC storage, full-thread fetched markers, and Gmail backlog pagination diagnostics.
- Improved Gmail MIME body extraction to prefer plain text, sanitize HTML fallback, and preserve quoted/reply text in stored bodies.
- Added a chronological conversation timeline to message detail pages, with the selected message highlighted in relation to the full thread.
- Added a manual “Fetch full conversation” action for Gmail messages whose full context is not stored yet.
- Added Gmail historical backfill controls that continue through Gmail `nextPageToken` instead of repeatedly showing only the first recent window.
- Added attention queue filters for active/unreviewed, needs reply, important, noise, reviewed, date range, sender/contact, and source.
- Kept external mailbox behavior read-only; no send, archive, delete, unsubscribe, label, or calendar-write behavior was added.

### Files changed
- `app/connectors/base.py`
- `app/connectors/gmail/client.py`
- `app/models/entities.py`
- `app/services/attention_service.py`
- `app/services/conversation_service.py`
- `app/services/gmail_sync_service.py`
- `app/api/routes.py`
- `app/web/routes.py`
- `app/web/templates/dashboard.html`
- `app/web/templates/message_detail.html`
- `alembic/versions/0005_gmail_conversation_context.py`
- `tests/test_app_bootstrap.py`
- `tests/test_gmail_conversation_context.py`
- `README.md`
- `docs/PROJECT_TRACKING.md`
- `docs/PHASE_PLAN.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_05_MICROSOFT_365_CONNECTORS.md`

### Tests run
- `python -m pytest -q` — passed, 43 tests.

### Smoke tests
- App startup: `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8028` started successfully and `GET /` returned HTTP 200.
- Dashboard: startup smoke confirmed the dashboard renders with sync/backfill diagnostics and queue filters.
- Key workflow: mocked tests cover full Gmail thread fetch, plain-text and HTML body extraction, conversation timeline ordering, reviewed/noise queue progression, and historical pagination.

### Documentation updated
- `README.md`
- `docs/PROJECT_TRACKING.md`
- `docs/PHASE_PLAN.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_05_MICROSOFT_365_CONNECTORS.md`

### Known issues
- Full conversation fetch is manual from the message detail page unless full body storage is enabled for sync.
- Phase 05 exposes thread context but does not improve AI summarization or recommendation quality.
- Sent-mail learning and outbound execution remain out of scope.

### Recommended next actions
- Human review and smoke-test Phase 05 with real Gmail threads, including the Christian/Michael dinner-cancellation scenario.
- After review, proceed to Phase 06: AI summarization and proposed action intelligence.

## 2026-05-15 — Phase 04: Safe Draft Reply Generation and Voice Profiles

### Summary
- Replaced the placeholder draft generator with a provider-neutral draft service and deterministic mock provider.
- Added local review-only draft generation from message detail pages with voice profile selection.
- Seeded the required short acknowledgement voice profile alongside client, friend, partner, and vendor profiles.
- Built compact draft context from message subject, sender/contact, relationship, contact importance/status, classification, attention score/reason, recommended action, and correction/profile feedback summaries.
- Added local draft list and draft review pages that clearly state drafts are suggestions only, not sent, and not created in Gmail.
- Added focused tests for draft creation, voice-profile-specific mock output, context construction, and the web draft review flow.

### Files changed
- `app/models/entities.py`
- `app/services/draft_service.py`
- `app/services/voice_seed.py`
- `app/api/routes.py`
- `app/web/routes.py`
- `app/web/templates/dashboard.html`
- `app/web/templates/message_detail.html`
- `app/web/templates/drafts.html`
- `app/web/templates/draft_review.html`
- `tests/test_draft_generation.py`
- `README.md`
- `docs/PROJECT_TRACKING.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_04_DRAFTS_AND_VOICE.md`

### Tests run
- `python -m pytest -q` — passed, 37 tests.

### Smoke tests
- App startup: `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8014` started successfully and `GET /` returned HTTP 200.
- Dashboard: dashboard route rendered during startup smoke.
- Key workflow: automated web test generated a local draft from a message detail route, redirected to the draft review page, and confirmed there are no send controls.

### Documentation updated
- `README.md`
- `docs/PROJECT_TRACKING.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_04_DRAFTS_AND_VOICE.md`

### Known issues
- Draft generation is intentionally deterministic/mock-only for local development; no production AI provider is wired in this phase.
- Drafts are stored as local suggestions only. Editing, approval workflows, and external draft creation remain future work.

### Recommended next actions
- Human review and smoke-test Phase 04 with real local message examples.
- After review, proceed to Phase 05: Microsoft 365 connectors: Outlook and Teams.

## 2026-05-15 — Phase 03: Contact Intelligence and Relationship-Aware Triage

### Summary
- Added alias-aware contact resolution so Gmail sync and message corrections can match sender aliases to an existing contact profile instead of creating duplicate contacts.
- Expanded relationship-aware scoring for partner, close_friend, friend, family, client, prospect, vendor, newsletter, system, and unknown relationship types.
- Added contact profile create/edit flows with display name, primary email, aliases, relationship type, importance tier, preferred channel, notes, and normal/VIP/noise status.
- Added dashboard access to contact management, contact edit links from message detail pages, and contact importance context on message detail pages.
- Recalculate existing message attention scores when contact aliases, relationship, importance tier, preferred channel, notes, or VIP/noise status change.
- Persist contact profile creation/update history in `user_feedback` and show contact history on contact and message detail pages.

### Files changed
- `app/models/entities.py`
- `app/services/contact_service.py`
- `app/services/attention_service.py`
- `app/services/gmail_sync_service.py`
- `app/services/feedback_service.py`
- `app/web/routes.py`
- `app/web/templates/dashboard.html`
- `app/web/templates/message_detail.html`
- `app/web/templates/contacts.html`
- `app/web/templates/contact_detail.html`
- `alembic/versions/0004_contact_alias_index.py`
- `tests/test_app_bootstrap.py`
- `tests/test_contact_intelligence.py`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_03_CONTACT_INTELLIGENCE.md`

### Tests run
- `python -m pytest -q` — passed, 33 tests.

### Smoke tests
- App startup: `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8013` started successfully.
- Dashboard: `GET http://127.0.0.1:8013/` returned HTTP 200.
- Contact management: `GET http://127.0.0.1:8013/contacts` returned HTTP 200.
- Key workflow: automated tests cover relationship-aware scoring, alias matching during Gmail sync, contact profile edit recalculation, contact history persistence, and contact management page rendering.

### Documentation updated
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_03_CONTACT_INTELLIGENCE.md`

### Known issues
- Contact preferred channel is profile metadata only; it does not add Outlook, Teams, SMS, WhatsApp, Messenger, or notification ingestion.
- Contact alias editing can reassign an existing alias to the edited contact when the user explicitly saves that alias on the profile.

### Recommended next actions
- Human review and smoke-test Phase 03 with real contact examples.
- After review, proceed to Phase 04: Safe draft reply generation and voice profiles.

## 2026-05-15 — Phase 02: Durable Gmail Sync and Local Data Reliability

### Summary
- Added persistent per-account Gmail sync state with high-water metadata and latest sync diagnostics.
- Made normal sync incremental with a small high-water overlap and added a safe recent resync path.
- Kept repeat sync idempotent by updating existing message metadata, skipping duplicate inserts, and adding database-level duplicate protection for attention items.
- Recalculated thread unread count, latest-message timestamp, normalized subject, and max attention score after touched sync threads.
- Replaced startup `create_all()` behavior with Alembic-managed migration startup and kept explicit migration/reset commands documented.
- Added dashboard/API visibility for fetched, inserted, duplicate-skipped, thread-updated, and last-error sync results.

### Files changed
- `app/services/gmail_sync_service.py`
- `app/models/entities.py`
- `app/api/routes.py`
- `app/web/routes.py`
- `app/web/templates/dashboard.html`
- `app/core/database.py`
- `app/main.py`
- `alembic/env.py`
- `alembic/versions/0003_sync_state_reliability.py`
- `tests/test_sync_and_recalc.py`
- `tests/test_app_bootstrap.py`
- `README.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_02_GMAIL_SYNC_RELIABILITY.md`

### Tests run
- `python -m pytest -q` — passed, 29 tests.
- `.\.venv\Scripts\python.exe -m pytest -q` — could not run because the repo `.venv` Python executable is invalid on this OS platform.

### Smoke tests
- App startup: `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8012` returned dashboard HTTP 200.
- Dashboard: startup smoke confirmed the dashboard route renders after Alembic startup migration.
- Key workflow: tests cover incremental watermark reuse, duplicate message/attention protection, thread metadata updates, and Alembic bootstrap to current head.

### Documentation updated
- `README.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_02_GMAIL_SYNC_RELIABILITY.md`

### Known issues
- The local `.venv` still appears stale or invalid; system Python 3.14 was used for validation.
- Gmail sync remains recent-inbox only and read-only.

### Recommended next actions
- Human review and smoke-test Phase 02 with the real Gmail account.
- After review, proceed to Phase 03: Contact intelligence and relationship-aware triage.

## 2026-05-15 — Phase 01: Usability and structured feedback loop

### Summary
- Reworked the dashboard into a readable attention queue with score, sender, status, tags, reasons, dates, and focused actions.
- Expanded the message detail page with message facts, contact status, classification tags, attention score, grouped actions, structured correction controls, and feedback history.
- Added structured feedback fields and a correction service that persists corrections, updates classification, recalculates attention, and dismisses noise/ignore items immediately.
- Improved deterministic rules for job alerts, newsletters, insurance/renewal reminders, invoices, taxes, bills, due dates, expiry dates, and payment deadlines.
- Added contact reset behavior and made VIP/noise actions mutually clear.

### Files changed
- `app/web/templates/dashboard.html`
- `app/web/templates/message_detail.html`
- `app/web/routes.py`
- `app/api/routes.py`
- `app/services/feedback_service.py`
- `app/services/attention_service.py`
- `app/services/contact_service.py`
- `app/triage/deterministic_classifier.py`
- `app/models/entities.py`
- `alembic/versions/0002_structured_feedback.py`
- `tests/`
- `docs/`

### Tests run
- `.\.venv\Scripts\python.exe -m pytest -q` — passed, 25 tests, 2 existing FastAPI `on_event` deprecation warnings.

### Smoke tests
- App startup: `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010` returned dashboard HTTP 200.
- Dashboard: in-app browser render check on `http://127.0.0.1:8011/` confirmed page title, Attention Queue, Sync Gmail, and VIP Contacts rendered.
- Key workflow: unit tests cover important, needs reply, noise, structured feedback persistence, job alerts, renewal reminders, VIP/noise recalculation, dashboard route, and message detail route.

### Documentation updated
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_01_USABILITY_FEEDBACK.md`
- `README.md`

### Known issues
- FastAPI startup still uses deprecated `on_event`; Phase 02 already tracks startup/database lifecycle cleanup.
- Local `.venv` had to be repaired because it referenced a missing Python 3.14 interpreter path.

### Recommended next actions
- Complete Phase 02: Durable Gmail sync and local data reliability.

## 2026-05-14 — Phase 00: Gmail MVP foundation

### Summary
- Created the initial Gmail-first, read-only CommsDesk MVP.
- Added local FastAPI/Jinja dashboard.
- Added SQLAlchemy models, Alembic baseline migration, Gmail connector, deterministic classification, attention scoring, contact VIP/noise actions, reviewed queue status, and placeholder draft generation.
- Confirmed local smoke test was able to sync Gmail and show attention items.

### Files changed
- Initial app structure under `app/`.
- Alembic baseline migration under `alembic/versions/`.
- Tests under `tests/`.
- README and environment configuration.

### Tests run
- `python -m pytest -q` — passed locally with 18 tests and 2 FastAPI deprecation warnings.

### Smoke tests
- Virtual environment created successfully.
- Editable install succeeded.
- Gmail OAuth credential error was clear when `client_secret.json` was missing.
- After setup, dashboard displayed Gmail-derived attention items.
- User corrected example categories and marked ICBC sender as VIP/important.

### Known issues
- Dashboard is visually raw.
- Correction labels are not yet structured enough to drive learning.
- Classifier over-promotes some job alerts/newsletters as work/client-like.
- Local database lifecycle has a conflict risk if `init_db()` creates tables before Alembic migration is applied.
- Startup uses deprecated FastAPI `on_event` rather than lifespan.

### Recommended next actions
- Complete Phase 01: Usability and structured feedback loop.
