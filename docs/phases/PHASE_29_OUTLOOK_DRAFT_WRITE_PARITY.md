# Phase 29 — Outlook Draft Write and Cross-Provider Parity

## Goal

Add safe Outlook draft creation after the daily operator loop is usable. This phase is draft-only Microsoft write parity. It is not Outlook send and not Outlook calendar write.

## Scope

- Add Microsoft Graph Outlook draft creation behind explicit feature flags.
- Route draft execution by source provider.
- Gmail source messages continue to use Gmail draft creation.
- Outlook source messages use Outlook draft creation only when configured and enabled.
- If Outlook draft writing is disabled, block cleanly before mutation.
- Add provider-specific readiness diagnostics.
- Add audit entries for every Outlook draft attempt.

## Required config

```env
OUTLOOK_DRAFT_CREATE_ENABLED=false
OUTLOOK_SEND_ENABLED=false
OUTLOOK_CALENDAR_WRITE_ENABLED=false
```

Do not enable Outlook send. Do not enable Outlook calendar write. Do not enable Teams write.

## Safety requirements

Outlook draft creation must use the same external-action lane:

```text
prepare → approve → final confirmation → execute → audit
```

Also preserve:

- operational test mode where applicable;
- feature flags;
- provider readiness checks;
- allowlist/test recipient rules where relevant;
- dry-run/live distinction if supported;
- immutable execution attempts;
- clear recovery guidance.

## Acceptance criteria

- Outlook-originated messages never attempt Gmail draft creation.
- Outlook draft creation blocks clearly when disabled.
- Outlook draft creation works only when enabled and authorized.
- Gmail draft behavior is unchanged.
- Provider mismatch is covered by tests.
- Outlook send remains disabled.
- Outlook calendar write remains disabled.
- Audit trail clearly shows provider, action, readiness, confirmation, and result.

## Required validation

```powershell
python -m ruff check .
python -m pytest -q
python -m alembic upgrade head
```

Run route smoke for drafts, executions, providers, operational smoke, and health.
