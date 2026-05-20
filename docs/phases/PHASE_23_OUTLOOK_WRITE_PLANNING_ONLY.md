# Phase 23 — Outlook Write Planning Only

## Objective

Prepare for Microsoft Outlook draft/send support without implementing it in this phase.

Outlook mail read is live through delegated Microsoft Graph. Gmail draft/send and Google Calendar execution are guarded by operational test mode, allowlists, provider flags, dry-run, approval, confirmation, and audit records. Outlook write support should not be added until the equivalent safety model is designed and reviewed.

## Scope

### Graph permissions and app registration review

Document required delegated permissions for future Outlook write features:

- `Mail.Read`
- `Mail.ReadWrite` for draft creation or mailbox updates
- `Mail.Send` for send
- `offline_access`
- `User.Read`

Confirm tenant/admin consent implications and local delegated behavior.

### Provider seam design

Design an Outlook execution provider seam that mirrors Gmail behavior:

- prepare
- approve
- confirm
- execute
- audit
- dry-run
- operational test mode
- allowlisted recipients
- clear provider errors

### Payload design

Document intended payload shapes for:

- Outlook draft creation
- Outlook reply send
- Outlook folder/archive candidate if ever needed

### UI guidance only

Provider Status and Operational Smoke may show disabled guidance for Outlook write readiness, but no real Outlook write controls should be exposed in this phase.

## Out of scope

- Implementing Outlook draft creation.
- Implementing Outlook send.
- Implementing Outlook calendar.
- Implementing Teams.
- Adding Graph write calls.
- Enabling Microsoft write feature flags.

## Acceptance criteria

- Design doc exists for future Outlook write behavior.
- Provider status still shows Outlook send disabled/not implemented.
- Operational smoke still shows Outlook write as unavailable.
- No new Graph write requests are made.
- Existing Gmail/Calendar execution tests remain passing.

## Documentation updates required

Update:

- `README.md` if needed
- `docs/HELP.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_STATUS.md`
- this phase file
