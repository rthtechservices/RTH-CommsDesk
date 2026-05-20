# RTH CommsDesk

RTH CommsDesk is a local-first communications operations console for high-volume personal and business communication triage.

The app is not production-ready yet. Development is intentionally paused after Phase 29 because the next work needs to resume with smoke testing and a larger omnichannel implementation push before any deployment/release-candidate phase.

## Resume status

**Current state:** Phase 29 implemented; Outlook integration is only half smoke-tested.

**Resume here first:** finish Outlook smoke testing, especially Microsoft Graph delegated auth, Outlook read sync, Outlook draft/write readiness, and the guarded Microsoft write surfaces added in Phase 29.

**Do not make Phase 30 a deployment phase.** The app is still missing additional communication channels that should be considered before production:

- WhatsApp
- Facebook Messenger
- Instagram Messaging
- SMS text messages

The next phases must move in large implementation chunks. Avoid small visibility-only phases and avoid burning credits on repeated full-suite runs for copy-only/doc-only work. Use focused tests for changed behavior, then run full validation only at meaningful cut points.

## Required reading for any agent session

Before assigning work to Codex, Copilot, or another LLM session, read in this order:

1. `README.md`
2. `docs/RESUME_HANDOFF.md`
3. `docs/LLM_SESSION_GUIDE.md`
4. `docs/PROJECT_TRACKING.md`
5. `docs/PHASE_PLAN.md`
6. The assigned phase file under `docs/phases/`
7. `docs/IMPLEMENTATION_LOG.md`
8. `docs/LESSONS_LEARNED.md`
9. `docs/HELP.md`
10. `docs/MICROSOFT_GRAPH_LOCAL_SMOKE.md` when testing delegated Microsoft Graph locally

## Current capability snapshot

Implemented/local capabilities include:

- Gmail read sync/backfill/full-thread fetch.
- Outlook mail read via delegated Microsoft Graph.
- Azure OpenAI live AI provider with mock fallback.
- Provider status, operational smoke, route smoke, and persisted sanitized smoke history.
- Local review packages, draft suggestions, voice/sign-off learning, and Assistant Profile.
- Bulk triage and mailbox cleanup candidates.
- Guarded Gmail draft/send/label/archive seams.
- Guarded Google Calendar freebusy/write seams.
- Phase 29 Microsoft Graph write seams: Outlook draft creation, Outlook send/reply, Outlook mail modify, and Outlook calendar creation.
- Execution lifecycle: prepare → approve → confirm → execute → audit.
- Operational test mode, allowlist, feature flags, dry-run mode, and provider-aware routing.
- About page with durable app statistics baseline.

## Current blockers / incomplete work

- Outlook Phase 29 smoke testing is incomplete. Do not assume Microsoft write parity is operational until Graph auth, scopes, dry-run behavior, and execution audit are smoke-tested locally.
- Phase 29 docs report three pre-existing test failures. Re-check these before starting new feature work:
  - stale dashboard text assertion around the old provider matrix label;
  - two backup exclusion tests from Phase 22/27.
- WhatsApp, Facebook Messenger, Instagram Messaging, and SMS are not yet implemented as first-class channels.
- Teams remains disabled/not implemented unless a later explicit phase opens read-only Teams work.
- External writes must remain disabled by default.
- No deployment/release-candidate work should start until Outlook smoke and the omnichannel plan are complete.

## Safe local setup

```powershell
.\.venv\Scripts\Activate.ps1
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Useful smoke commands/routes:

```powershell
python -m ruff check .
python -m pytest -q
python -m alembic upgrade head
.\scripts\smoke-commsdesk.ps1
.\scripts\smoke-mailbox-cleanup.ps1
```

```text
/
/operational-smoke
/providers
/review-packages
/executions
/bulk-triage
/bulk-triage/mailbox-cleanup
/contacts
/drafts
/voice-calibration
/assistant-profile
/about
/admin
/healthz
```

## Safety defaults

Never commit secrets, OAuth tokens, `.env`, local SQLite data, or private message data.

External writes are disabled by default and must remain gated by:

```env
EXECUTION_PROVIDER=mock
EXTERNAL_WRITE_DRY_RUN=true
OPERATIONAL_TEST_MODE=false
EXECUTION_TEST_EMAIL_ALLOWLIST=
GMAIL_WRITE_ENABLED=false
GMAIL_DRAFT_CREATE_ENABLED=false
GMAIL_SEND_ENABLED=false
GMAIL_LABEL_ARCHIVE_ENABLED=false
GOOGLE_CALENDAR_WRITE_ENABLED=false
OUTLOOK_DRAFT_CREATE_ENABLED=false
OUTLOOK_SEND_ENABLED=false
OUTLOOK_MAIL_MODIFY_ENABLED=false
OUTLOOK_CALENDAR_WRITE_ENABLED=false
```

Do not set `EXTERNAL_WRITE_DRY_RUN=false` until the specific provider, scopes, feature flags, allowlist/test posture, approval, confirmation, and audit behavior have been verified.

## Project structure

```text
/app
  /api
  /connectors
    /gmail
    /outlook
    /teams
    /notifications
  /core
  /models
  /services
  /triage
  /voice
  /web
/alembic
/tests
/docs
  /phases
```

## Current phase status

Phases 01 through 29 are implemented. Phase 29 is not fully smoke-tested. Phase 30 is now **Outlook Integration Smoke Completion and Omnichannel Planning**, not deployment.
