# Phase 30 — Outlook Integration Smoke Completion and Omnichannel Planning

## Goal

Resume after the Phase 29 pause by finishing Outlook smoke testing and deciding the practical path for WhatsApp, Facebook Messenger, Instagram Messaging, and SMS.

This is not a deployment phase. Do not create a production release candidate here.

## Operating stance

Move fast. This phase should answer: "Can I trust Outlook integration enough to build on it, and what channel architecture are we implementing next?"

Avoid a giant test matrix. Run focused tests and targeted route/provider smoke. Full validation is useful at the end only if code changes were made.

## Required reading

- `README.md`
- `docs/RESUME_HANDOFF.md`
- `docs/LLM_SESSION_GUIDE.md`
- `docs/PHASE_PLAN.md`
- `docs/PHASE_STATUS.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/MICROSOFT_GRAPH_LOCAL_SMOKE.md`
- `docs/phases/PHASE_29_OUTLOOK_DRAFT_WRITE_PARITY.md`

## Scope

### 1. Repo and validation checkpoint

- Check current git status.
- Re-run focused tests around Outlook/provider/execution only.
- Re-check the three pre-existing Phase 29 full-suite failures and decide whether they are cheap to fix now.
- Do not run repeated full suites after doc-only edits.

### 2. Outlook smoke completion

Smoke the Phase 29 Microsoft Graph work with safe defaults first.

Required checks:

- `/api/graph/test` delegated Graph status.
- Token state and required scopes:
  - `User.Read`
  - `Mail.Read`
  - `Mail.ReadWrite`
  - `Mail.Send`
  - `Calendars.ReadWrite`
  - `offline_access`
- Outlook read sync still works.
- `/providers` reports four Microsoft write surfaces correctly:
  - draft creation;
  - send/reply;
  - mail modify;
  - calendar write.
- `/operational-smoke` shows accurate Microsoft readiness/boundary state.
- Outlook-originated execution records route to Microsoft Graph, not Gmail.
- Disabled flags block clearly.
- Dry-run returns audit-friendly provider results without external writes.
- Live flags remain off by default.
- Reauthorization script/guidance still works after scope changes.

### 3. Fix smoke blockers when practical

If smoke finds obvious blockers, fix them in this phase rather than punting tiny follow-up phases.

Examples:

- stale scope documentation;
- wrong provider status key;
- broken execution detail template;
- stale dashboard string assertion;
- backup test drift from earlier phases;
- missing recovery guidance;
- token reauth wording that no longer matches required scopes.

### 4. Omnichannel strategy decision

Document the practical implementation strategy for:

- WhatsApp;
- Facebook Messenger;
- Instagram Messaging;
- SMS text messages.

The output should decide whether Phase 31 starts with:

- provider-neutral webhook ingestion first;
- Meta Graph integration first;
- Twilio or another SMS/WhatsApp provider first;
- notification-summary ingestion as a bridge;
- or a hybrid.

Keep it grounded in implementation realities:

- account/API prerequisites;
- webhook verification;
- message identifiers and deduplication;
- thread/contact mapping;
- inbound vs outbound capability;
- approval/audit requirements for outbound replies;
- privacy and local storage posture.

### 5. Update docs

Update:

- `README.md` if current status changes;
- `docs/RESUME_HANDOFF.md` if the resume point changes;
- `docs/PHASE_STATUS.md`;
- `docs/PHASE_PLAN.md`;
- `docs/IMPLEMENTATION_LOG.md`;
- `docs/LESSONS_LEARNED.md`;
- `docs/HELP.md` if user-facing smoke/runbook steps change;
- Phase 31 file if the omnichannel decision changes its scope.

## Acceptance criteria

- Outlook smoke checklist completed or each blocker is explicitly documented with next action.
- Any cheap smoke blockers are fixed in this phase.
- Current test failure posture is documented accurately.
- Omnichannel architecture direction is documented and actionable.
- Phase 31 scope is adjusted to the chosen strategy.
- No deployment/release-candidate work is started.
- No external write flags are enabled by default.

## Validation guidance

Use focused validation first:

```powershell
python -m ruff check app tests
python -m pytest tests/test_phase_29_outlook_write_parity.py -q
python -m pytest tests/test_provider_status.py tests/test_operational_workflow.py -q
python -m alembic upgrade head
```

Run route smoke for:

```text
/
/operational-smoke
/providers
/review-packages
/executions
/drafts
/assistant-profile
/about
/admin
/healthz
```

Run full suite once at the end if code changed materially:

```powershell
python -m pytest -q
```

## Status

Planned / next.
