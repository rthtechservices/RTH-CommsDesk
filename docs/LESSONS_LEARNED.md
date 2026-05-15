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

## Gmail conversation context lessons

- A single Gmail inbox message is not enough context for reply decisions; store and display the whole Gmail thread before expecting Phase 06 to infer whether a response is needed.
- Use Gmail `threadId` as the source conversation key and sort local timeline entries by `received_at` plus local id for deterministic display.
- Prefer `text/plain` MIME parts when available. When only HTML exists, strip tags and script/style content before storage or display.
- Preserve quoted lines and reply text in normalized bodies; they are often the only clue for who said what in a thread.
- Historical Gmail backfill must persist `nextPageToken`; otherwise the dashboard keeps cycling through the same recent window.
- Reviewed and dismissed/noise items should stay out of the default active queue so backlog triage can progress.

## AI analysis and review package lessons

- Keep AI analysis provider-neutral like draft generation. The default local path should remain deterministic/mock so tests and development do not require paid credentials.
- Store the analysis output as local review packages with source thread/message links, summary, action type, explanation, confidence, and local status. Do not treat recommendations as external execution.
- A no-response-needed recommendation should not create a draft by default. Draft creation can still be forced manually, but the generated text should make the override explicit.
- Draft generation can use full locally stored thread context in Phase 06, but it should still keep user correction history summarized rather than copying raw feedback notes into prompts.
- Reminder, archive, delete, unsubscribe, and calendar recommendations must remain candidates until a later approved-execution phase adds explicit external write behavior.

## Sent-mail learning and voice calibration lessons

- Keep sent-mail learning storage separate from inbound triage records so replaying learning does not mutate message-attention history.
- Store excerpted evidence for voice calibration review; avoid exposing full sent-message bodies in calibration lists.
- Use deterministic salutation/tone inference as a baseline, but always require explicit approve/reject/edit before guidance becomes active.
- Approved contact-level voice guidance should override generic voice-profile defaults. Relationship-level guidance should be fallback only.
- Draft generators should honor learned "avoid corporate filler" notes to remove stock phrasing when more natural contact-specific style exists.

## Bulk triage and automation candidate lessons

- Bulk backlog views should paginate from a queryable attention queue, not from a fixed top-N dashboard slice.
- Generate automation candidates with explicit reason/confidence text and keep execution local until later approved-execution phases.
- Keep candidate generation idempotent with per-message candidate-type upserts to avoid duplicate suggestion noise.
- Log bulk actions with reversible snapshots so "undo where practical" is explicit and auditable.
- Keep destructive recommendations (archive/delete/unsubscribe) in pending local candidate state until explicit user approval and execution flow exists.

## Calendar availability lessons

- Keep calendar availability provider-neutral. Use the mock provider for deterministic local tests and development defaults.
- Store calendar recommendations as local proposal records linked to review packages so reasoning/conflicts remain auditable.
- Separate action kind (create_reminder, create_meeting, offer_availability, ask_for_time_clarification) from high-level package action type where needed.
- Keep calendar integrations read-only in scheduling-recommendation phase; no external event creation should occur yet.
- Include suggested alternative windows when conflicts are detected so clarification drafts are concrete and actionable.

## UI lessons

- A raw list of scores and reasons is technically useful but not user-friendly.
- The dashboard should explain why something matters without requiring the user to understand internal scoring.
- Row actions should be limited and clear. Put secondary actions on the detail page.

## LLM handoff lessons

- Keep each LLM session bounded to one phase.
- Require documentation updates at the end of each phase.
- Preserve a clear smoke-test checklist so the human can verify behavior before assigning the next phase.
