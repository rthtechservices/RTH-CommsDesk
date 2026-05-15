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
