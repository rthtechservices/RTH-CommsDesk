# Lessons Learned and Gotchas

Document durable project knowledge here. Keep entries concise and actionable.

## Local Python environment

- Use a project virtual environment. Installing into the user-level Python site-packages can create dependency conflicts with other Google/Gemini tooling.
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

- The app currently calls `init_db()` on startup. That can create tables before Alembic is run.
- If `python -m alembic upgrade head` fails with `table contacts already exists` on a disposable local database, delete the local SQLite DB and rerun migrations.
- A future phase should decide whether local startup should use Alembic, `init_db()`, or a clearly separated dev-only bootstrap path.

## Gmail OAuth

- Gmail sync requires a local OAuth client secrets JSON file.
- Default expected file path is `client_secret.json` in the repo root unless `GMAIL_CLIENT_SECRETS_FILE` is set.
- The token file is local-only and should never be committed.
- The app uses Gmail read-only scope.

## Classification lessons

- List-Unsubscribe and marketing headers are useful but not sufficient by themselves.
- Job alerts can look like work/client messages because they contain company names, job titles, and business words.
- Renewal reminders, insurance, bills, due dates, expiry dates, payment deadlines, and tax notices are often personally important even when they are automated.
- Importance should be a blend of message content, sender/contact history, explicit user corrections, and relationship context.

## UI lessons

- A raw list of scores and reasons is technically useful but not user-friendly.
- The dashboard should explain why something matters without requiring the user to understand internal scoring.
- Row actions should be limited and clear. Put secondary actions on the detail page.

## LLM handoff lessons

- Keep each LLM session bounded to one phase.
- Require documentation updates at the end of each phase.
- Preserve a clear smoke-test checklist so the human can verify behavior before assigning the next phase.
