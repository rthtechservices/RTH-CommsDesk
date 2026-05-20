# Resume Handoff — Pause After Phase 29

## Why this file exists

Development is paused after Phase 29 because credits are low. This is the restart point for the next agent/session.

Do not infer that the next step is deployment. It is not.

## Current state

Phase 29 was implemented and added Microsoft Graph write parity behind feature flags:

- Outlook draft creation;
- Outlook send/reply;
- Outlook mail modify/category/read/archive seams;
- Outlook calendar event creation;
- provider-aware routing;
- readiness display;
- execution detail provider routing;
- approval/confirmation/audit integration.

However, Outlook integration was only half smoke-tested. Treat Microsoft write parity as implemented but not operationally trusted until smoke testing finishes.

## Resume sequence

1. Read `README.md` and this file first.
2. Read `docs/PHASE_STATUS.md` and `docs/PHASE_PLAN.md`.
3. Read `docs/phases/PHASE_30_OUTLOOK_SMOKE_AND_OMNICHANNEL_PLANNING.md`.
4. Check git status locally.
5. Run the existing focused validation commands only as needed.
6. Finish Outlook smoke testing before starting new channels.

## Immediate smoke priorities

Verify these with local safe settings first:

- `/api/graph/test` delegated Microsoft Graph status.
- Token scope freshness after Phase 29 added `Mail.ReadWrite`, `Mail.Send`, and `Calendars.ReadWrite`.
- Outlook read sync still works.
- `/providers` correctly reports Outlook draft/send/mail modify/calendar readiness.
- `/operational-smoke` reports Microsoft boundary/write state accurately.
- Outlook-originated draft/action execution does not attempt Gmail fallback.
- Dry-run Microsoft execution records create useful audit entries without external writes.
- Disabled flags block clearly.
- Reauthorization instructions are correct.

## Required safe defaults

```env
EXECUTION_PROVIDER=mock
EXTERNAL_WRITE_DRY_RUN=true
OPERATIONAL_TEST_MODE=false
EXECUTION_TEST_EMAIL_ALLOWLIST=
OUTLOOK_DRAFT_CREATE_ENABLED=false
OUTLOOK_SEND_ENABLED=false
OUTLOOK_MAIL_MODIFY_ENABLED=false
OUTLOOK_CALENDAR_WRITE_ENABLED=false
```

Enable one surface at a time during smoke testing. Keep dry-run on until the exact provider/action path has been verified.

## Do not make Phase 30 deployment

Phase 30 must be Outlook smoke completion and omnichannel planning. The app is missing additional channels:

- WhatsApp;
- Facebook Messenger;
- Instagram Messaging;
- SMS text messages.

The production/release-candidate phase moves later, after Outlook smoke and a practical omnichannel strategy/implementation are in place.

## Acceleration rule

The next work should be done in large chunks.

Bad next phases:

- rename a button;
- add one status card;
- write docs only;
- run the whole test suite repeatedly without changing code;
- produce another tiny visibility-only Microsoft status pass.

Good next phases:

- complete Outlook smoke and produce exact remediation work;
- add normalized channel ingestion for multiple messaging providers in one sprint;
- add live adapter plumbing for the selected provider family;
- extend review/execution to messaging replies with approval/confirmation/audit.

## Known validation note from Phase 29

Phase 29 reported:

- Ruff passed.
- Focused Phase 29 tests passed.
- Alembic upgrade passed.
- Full suite had 382 passed and 3 pre-existing failures.

Before starting new implementation, re-check whether the three pre-existing failures still exist and either fix them in Phase 30 if cheap or document them accurately.

## Agent reminder

Move fast, but keep the external-action safety contract intact:

```text
prepare → approve → confirm → execute → audit
```

No hidden live sends. No provider fallback that pretends success. No external-write flags on by default.
