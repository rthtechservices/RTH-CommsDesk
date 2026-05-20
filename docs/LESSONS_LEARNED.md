# Lessons Learned and Gotchas

Document durable project knowledge here. Keep entries concise and actionable.

## Jinja2 template writing via PowerShell

- PowerShell `python -c "..."` inline scripts break when template content contains semicolons, CSS properties, or special characters — PowerShell interprets semicolons as statement separators.
- Solution: write templates to disk using the `create_file` tool as `.py` script files, then run `python script.py`, then delete the script.
- `execution_subagent` has the same PowerShell inline limitation.

## Jinja2 template variable alignment

- Always verify the exact variable names passed by the route before writing a template. The route context dict is the source of truth.
- `providers.html` must use `provider_rows` (not `rows`) and `row.label`, `row.state`, `row.mode`, `row.detail` (not `row.provider`, `row.capability`, `row.status`).
- `operational_smoke.html` must use a single `smoke_status` dict, not separate variables like `gmail_status`, `graph_status`.
- `admin.html` uses `message_body_count`, `sent_excerpt_count`, `audit_count`, `retention_result`, `cache_result` — not `system_info`.

## Test helper generators as context managers

- A generator function (using `yield`) cannot be used as a context manager with `with` unless decorated with `@contextmanager` from `contextlib`.
- Always import and apply `@contextmanager` when writing test helpers that yield a client inside a `with` block.

## Model field names

- `MessageThread` and `Message` both use `source_type` (not `source_system`).
- `DraftReply` uses `draft_text` (not `body`) and `provider_name` (not `provider`).
- Check `app/models/entities.py` when writing test fixtures or templates.

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
- Review-package corrections should be structured feedback, not just notes. Store action/reply/noise/summary/draft/calendar corrections so later prompt context can learn from them.
- When the latest message supersedes an earlier ask, avoid letting older thread scheduling language create a stale calendar recommendation.

## Sent-mail learning and voice calibration lessons

- Keep sent-mail learning storage separate from inbound triage records so replaying learning does not mutate message-attention history.
- Store excerpted evidence for voice calibration review; avoid exposing full sent-message bodies in calibration lists.
- Use deterministic salutation/tone inference as a baseline, but always require explicit approve/reject/edit before guidance becomes active.
- Approved contact-level voice guidance should override generic voice-profile defaults. Relationship-level guidance should be fallback only.
- Draft generators should honor learned "avoid corporate filler" notes to remove stock phrasing when more natural contact-specific style exists.
- Recurring operator sign-offs belong in the same approved voice-guidance path as tone guidance. Infer them from repeated sent-mail evidence, store them as pending guidance, and apply them only after approval.
- Send-ready draft bodies must be sanitized for generic placeholders such as `[Your Name]`, `[Your signature]`, `[your name]`, and `[signature]` before any execution payload is prepared.
- Assistant Profile should remain a practical view over existing `VoiceGuidance`, not a separate memory system. Use status plus `is_active` for approve/reject/disable/reset unless a future phase proves a richer lifecycle is needed.
- Draft preview surfaces must stay read-only: generate from an in-memory context and do not create `DraftReply`, `ExecutionRecord`, audit rows, Gmail drafts, sends, calendar events, or external provider calls.

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
- A date-only request to meet/chat is not a timed meeting. Treat it as a clarifying-reply case and, if useful, store an all-day tentative candidate rather than inventing an hour.
- Calendar interpretation should be anchored to the message received date and should not prepare reminders/events in the past.

## Approved execution lessons

- Execution should be a staged workflow (prepare -> approve -> confirm -> execute) rather than a single-click action.
- Execution records should be immutable attempts. Use new attempt records for retries, re-runs, clones, and regenerated payloads instead of overwriting a previous result.
- Store the exact outbound payload and provider result on execution records for auditability and postmortems.
- Write audit rows for every lifecycle step (prepared, approved, confirm_started, executed, failed, cancelled).
- Keep destructive actions behind an explicit confirmation token and visible warnings even when mock providers are used.
- Review notes stay in CommsDesk; external Gmail drafts must be send-ready.
- Keep review_text/explanation/caveats separate from send_ready_subject and send_ready_body so Gmail never receives internal review narrative or duplicated Subject lines.

## Connector expansion lessons

- Keep non-Gmail connectors normalized into the same source/thread/message pipeline so attention scoring, review packages, and execution prep remain connector-agnostic.
- For notification webhooks, store summary/snippet fidelity with explicit source confidence instead of treating payloads as full messages.
- Connector sync state should be tracked per source/account even for webhook-like sources so failures and recency remain auditable.
- UI should always display message source and confidence to avoid over-trusting low-fidelity notification summaries.
- Microsoft Graph delegated OAuth should be validated with a sanitized status endpoint before attempting mailbox sync.
- Preserve app-only Microsoft Graph seams while adding delegated local-development auth; the mode switch belongs in configuration, not in the Outlook connector.
- Outlook mail read should use Graph `$select`, paging limits, and the existing normalized message/thread model.
- Outlook send, Outlook calendar, and Teams should stay disabled until a future explicit write/read phase opens those scopes.

## Production hardening lessons

- Keep authentication optional for local-only development but mandatory by configuration for exposed/staging/production environments.
- Enforce separate web-session auth and API token auth so browser and automation surfaces are both protected.
- Use structured logs with explicit redaction filters; never rely on callers to avoid sensitive strings consistently.
- Treat retention as an active control surface with explicit cleanup commands and auditable result counts, not as passive documentation.
- Keep admin cleanup operations local-data-only to avoid accidental external account modifications.
- Use the current `templates.TemplateResponse(request, template_name, context, ...)` call style consistently. The old positional style can pass the context dict as the template name under newer Starlette/Jinja versions and break routes such as `/admin` or auth-enabled `/login`.

## Stabilization smoke lessons

- When testing `uvicorn --reload`, restart the process after route/template edits before trusting browser results. The reloader can briefly serve a mismatched template and route context during smoke testing.
- Record Gmail sync and backfill smoke results as counts and cursor behavior only. Avoid logging private subjects, snippets, or body text in phase docs.
- Backfill is one Gmail result page per click/run. The page size is controlled by `GMAIL_READ_MAX_RESULTS`, and forward progress depends on the persisted Gmail `nextPageToken`.
- For real-data queue progression tests, use reversible local actions such as bulk action undo where practical so Phase 13 validation does not leave unnecessary triage state changes behind.
- Provider status belongs in the main workflow. Showing mock/live/local storage state on the dashboard helps prevent deterministic mock providers from being mistaken for live external integrations.

## Live AI provider and prompt-quality lessons

- Keep live AI enablement explicit: `AI_PROVIDER=mock` remains the safe default, and live analysis/drafts should require environment-provided API key and model values.
- Treat live AI output as untrusted input. Require structured JSON, validate supported action types and confidence, strip control characters, cap stored text length, and drop drafts for no-response/noise/reminder recommendations.
- Wrap live providers with deterministic mock fallback so review-package generation and local draft creation continue when a provider times out, fails, or returns invalid JSON.
- Prompt-quality tests should exercise product examples, not only parser behavior: friend acknowledgements, client requests, renewal reminders, newsletters/noise, and vague actionable messages catch regressions that generic unit tests miss.
- Store and display provider names for generated review packages and drafts so mock, live, and fallback outputs are auditable during real-data smoke testing.
- Treat OpenAI-compatible and Azure OpenAI endpoints as different provider shapes. OpenAI-compatible mode appends `/chat/completions` to `AI_BASE_URL` and uses a bearer token; Azure OpenAI mode must build `/openai/deployments/<deployment>/chat/completions?api-version=<version>` from `AZURE_OPENAI_ENDPOINT` and use the `api-key` header.
- Provider test endpoints should expose sanitized failure categories and HTTP status codes without hiding direct diagnostic failures behind mock fallback. Normal analysis/draft generation should still use mock fallback.

## Real provider wiring lessons

- External provider status should distinguish provider shape from runtime state. A connector can be partially wired but still disabled, missing configuration, or dry-run at runtime.
- Keep `EXECUTION_PROVIDER=mock` as the default even after live provider clients exist. Live provider selection, feature flags, approval, confirmation, and `EXTERNAL_WRITE_DRY_RUN=false` should all be deliberate choices.
- Dry-run execution should still require the relevant feature flag so it proves the operator intentionally selected that action family without modifying external systems.
- Streamlined test execution needs a separate operational test-mode policy in addition to provider flags. `EXECUTION_PROVIDER=external` is not enough; require `OPERATIONAL_TEST_MODE=true`, action flags, and allowlisted test recipients before Gmail writes.
- Keep allowlist parsing centralized. Routes, templates, and provider execution should all read the same readiness result so UI copy cannot drift from the actual enforcement path.
- Microsoft Graph mail, Teams, and Outlook Calendar require tenant-specific app registration and permissions. Status should fail closed and document prerequisites instead of pretending the adapter is live.
- Gmail write scopes can require token reauthorization. Do not reuse a read-only smoke result as evidence that draft/send/modify scopes are available.
- Google Calendar `dateTime` payloads using naive local timestamps must include `timeZone` on both `start` and `end`; default local operator time zone is `America/Vancouver`.

## UX consolidation lessons

- Provider warnings belong near the top of the daily dashboard because they change what actions the user should trust.
- Review packages work best as the central unit of work when they show item position, recommendation, evidence, timeline, contact context, draft/action payload, and local review controls together.
- Keep existing specialized pages, but make the dashboard point to the next useful workflow: attention items, proposed actions, approval queue, calendar candidates, noise candidates, or provider setup.
- Operational smoke should aggregate readiness across sync, AI, execution mode, dry-run, write flags, and disabled connector boundaries so the operator does not have to infer readiness from several pages.
- Smoke harnesses can be useful without a new persistence schema. A sanitized checklist with route links and explicit dry-run/test-mode/allowlist state is enough until repeated smoke history becomes a real product need.
- Process-next links are useful glue for smoke testing because they preserve the existing detail pages while removing repeated dashboard/list navigation.
- Do not surface disabled future connectors as primary dashboard actions. A disabled provider row is enough until the phase explicitly opens that connector.
- Dense operator dashboards need explicit status semantics. Use green for operational, amber for mock/dry-run/manual setup, red for blockers, and grey for disabled/not implemented.
- Provider and operational guidance can be actionable without becoming a config editor: show current state, env var names, copy/paste snippets, and restart guidance, but leave `.env` mutation manual until an explicit phase opens it.
- Message detail action sidebars should hide impossible/redundant contact actions. Showing both "Mark VIP" and "Reset normal" for an already-VIP contact makes the workflow look unsafe.
- Long conversation timelines need `min-width: 0`, wrapping, and card-level scrolling in grid layouts; otherwise body text can escape the main column and overlap the action column.

## UI lessons

- A raw list of scores and reasons is technically useful but not user-friendly.
- The dashboard should explain why something matters without requiring the user to understand internal scoring.
- Row actions should be limited and clear. Put secondary actions on the detail page.
- Workflow stage color semantics matter: amber = current/pending work (draws attention), green = past stage (completed, no action needed). Do NOT use green for the current/active stage — it looks like success when it should signal "work is here."
- Pending counts (review packages, ready executions, attention queue size) should visually distinguish zero (green = nothing to do) from non-zero (amber = action needed). Using the same muted color for 0 and 50 makes the UI useless for quick triage.
- A Next Best Action strip at the top of the dashboard is the single most ergonomic addition: it collapses the decision of "where do I start?" into one sentence and one button, reducing cognitive load on every open.
- Source and action visual identity: assign a stable color to each source (Gmail=cyan, Outlook=blue) and each action type (reply=amber, schedule=teal, noise=indigo, review=purple). Users learn these associations quickly when they are consistent across all badges.
- Existing tests are the spec for exact label text. When renaming UI labels for brevity, check first whether any test asserts the old string literally. Preserve or update the test, never silently break it.

## LLM handoff lessons

- Keep each LLM session bounded to one phase.
- Require documentation updates at the end of each phase.
- Preserve a clear smoke-test checklist so the human can verify behavior before assigning the next phase.
