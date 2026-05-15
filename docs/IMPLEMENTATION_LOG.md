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
