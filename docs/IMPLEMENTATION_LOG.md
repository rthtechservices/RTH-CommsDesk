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
