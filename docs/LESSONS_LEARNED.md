# Lessons Learned and Gotchas

Document durable project knowledge here. Keep entries concise and actionable.

## Local Python environment

- Use a project virtual environment. Installing into the user-level Python site-packages can create dependency conflicts with other Google/Gemini tooling.
- If the local `.venv` was created with a Python version that is no longer installed, recreate or repair it before testing. Stale compiled wheels, especially `pydantic-core`, may need a force reinstall after changing interpreters.
- Prefer these commands from the repo root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev,gmail]"
python -m pytest -q
```

- Use `python -m pytest`, `python -m alembic`, and `python -m uvicorn` to avoid PATH issues with scripts installed inside `.venv`.

## SQLite and Alembic

- Startup now runs Alembic migrations instead of SQLAlchemy `create_all()`. Keep schema changes in Alembic migrations and use `python -m alembic upgrade head` as the explicit setup/reset command.
- Tests can still use `Base.metadata.create_all()` against disposable in-memory SQLite, but app startup should not use it for the real local database.
- If local SQLite migration behavior is confusing, stop the app, delete only the disposable `commsdesk.db`, rerun `python -m alembic upgrade head`, and restart. Do not delete OAuth files unless Gmail reauthorization is intended.

## Gmail OAuth

- Gmail sync requires a local OAuth client secrets JSON file.
- Default expected file path is `client_secret.json` in the repo root unless `GMAIL_CLIENT_SECRETS_FILE` is set.
- The token file is local-only and should never be committed.
- The app uses Gmail read-only scope.

## Gmail sync reliability

- Persist Gmail sync state per source/account. The high-water mark should be used for normal sync, with a small overlap so same-time messages are not missed.
- Manual resync should ignore the high-water mark but remain duplicate-safe by checking source message ids before insert.
- Existing duplicate messages may still need local metadata updates, especially unread state, snippet, subject, attachment flag, and thread counts.
- Attention items need database-level duplicate protection in addition to service-level upsert logic.

## Classification lessons

- List-Unsubscribe and marketing headers are useful but not sufficient by themselves.
- Job alerts can look like work/client messages because they contain company names, job titles, and business words.
- Non-free sender domains alone should not be treated as client work when the message has automated, newsletter, job alert, receipt, or system-notice signals.
- Renewal reminders, insurance, bills, due dates, expiry dates, payment deadlines, and tax notices are often personally important even when they are automated.
- Importance should be a blend of message content, sender/contact history, explicit user corrections, and relationship context.

## Feedback loop lessons

- Structured corrections should be the single path for UI and API changes so the app stores feedback, updates classification, and recalculates attention consistently.
- Noise and ignore corrections should dismiss the current item, while newsletter and job-alert corrections should lower priority without changing external Gmail state.

## Contact intelligence lessons

- Resolve contacts through both primary email and aliases before creating a new contact during sync; otherwise one person can become multiple local profiles.
- Contact profile updates should recalculate attention for messages matched by either `message_threads.contact_id` or any normalized sender email on the profile.
- Store contact profile changes as feedback/history records so future tuning can distinguish message classification corrections from contact relationship corrections.
- Relationship-aware scoring should include explicit negative weights for newsletter and system contacts, not only positive boosts for close relationships.

## Draft generation lessons

- Keep draft generation provider-neutral by passing a compact context object into a provider interface; routes should not know whether the provider is mock, local, or cloud.
- Draft context should use metadata, subject, classification, attention reason, contact profile, and feedback summaries. Do not pass full message bodies by default.
- Feedback summaries used for draft context should summarize labels and corrected values, not raw free-text feedback that may contain private content.
- Local mock draft generation is a required fallback so the app remains usable without paid AI credentials.
- Review pages must keep the safety boundary visible: local suggestions only, not sent, and not created in Gmail.

## UI lessons

- A raw list of scores and reasons is technically useful but not user-friendly.
- The dashboard should explain why something matters without requiring the user to understand internal scoring.
- Row actions should be limited and clear. Put secondary actions on the detail page.

## LLM handoff lessons

- Keep each LLM session bounded to one phase.
- Require documentation updates at the end of each phase.
- Preserve a clear smoke-test checklist so the human can verify behavior before assigning the next phase.
