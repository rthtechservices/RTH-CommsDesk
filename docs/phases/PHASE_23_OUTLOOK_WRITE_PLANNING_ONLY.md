# Phase 23 — Mailbox Cleanup, Sender Noise Automation, and Outlook Write Planning

## Objective

Turn the existing local bulk-triage/noise foundation into an operator-facing mailbox cleanup workflow that helps Rohan identify mailbox-filling crap by sender/domain, review the evidence quickly, and approve safe bulk cleanup actions.

This phase also retains the original Outlook write planning work, but Outlook write remains planning-only. Do not split mailbox cleanup into a new phase and do not implement Microsoft write behavior in this phase.

Primary outcome:

```text
Synced mailbox data
→ sender/domain cleanup rollups
→ confidence-scored noise/spam/marketing candidates
→ evidence and sample messages
→ operator-approved bulk label/archive/delete preparation
→ gated Gmail execution where implemented
→ audit trail
```

The point is to reduce mailbox size and visual noise. Outbound drafting is important, but mailbox cleanup is now a first-class daily-use workflow.

## Current baseline

The repository already has a useful foundation:

- Message classifications can identify newsletters, marketing, group noise, system notifications, low-engagement messages, and messages that require replies.
- `AutomationCandidate` already supports `mark_noise`, `unsubscribe_review`, `archive_candidate`, and `delete_candidate` style recommendations.
- `/bulk-triage` exists and can generate candidates, apply local bulk actions, and undo local bulk actions.
- Current bulk triage is mostly local-state triage. It does not yet provide a strong sender/domain cleanup console, Gmail label/archive/delete execution path, or a one-click "this sender is garbage" workflow.

Phase 23 should close that product gap.

## Scope A — Mailbox cleanup intelligence

Add a mailbox cleanup service, for example:

```text
app/services/mailbox_cleanup_service.py
```

It should analyze synced Gmail messages first. Outlook can be included as read-only rollup data if the local message schema already supports it cleanly, but external Outlook cleanup/write actions are out of scope.

Create sender/domain rollups with at least:

- sender email
- sender display name when available
- sender domain
- source system counts: Gmail, Outlook if present
- total synced messages
- unread count
- oldest received date
- newest received date
- estimated stored body/snippet availability
- marketing/newsletter count
- group-noise count
- system-notification count
- unsubscribe-language count
- requires-reply count
- human-personal count
- VIP/client/important-contact count
- existing contact status: normal, VIP, noise
- already-reviewed/dismissed counts if available
- cleanup confidence score
- recommended cleanup action
- recommended Gmail label name where applicable
- explanation / evidence summary

Recommended cleanup actions should include:

- `review_only`
- `mark_sender_noise_local`
- `apply_gmail_label`
- `archive_gmail`
- `label_and_archive_gmail`
- `prepare_delete_candidate`
- `skip_protected_sender`

Use conservative protection rules:

- Never recommend delete/archive for VIP contacts.
- Never recommend delete/archive for contacts marked client, partner, vendor, professional, or otherwise important unless explicitly reviewed.
- Never recommend delete/archive where any message from the sender requires reply.
- Never recommend delete/archive where the sender has recent human-personal messages.
- Prefer label-only when confidence is moderate.
- Prefer label-and-archive when confidence is high and no protection flags are present.
- Use delete only as a prepared candidate, not an immediate mailbox mutation.

Example confidence logic:

- High confidence: repeated sender, mostly marketing/newsletter/system/group-noise, unsubscribe language present, no requires-reply, no VIP/client/protected contact markers.
- Medium confidence: repeated low-value sender but mixed classifications.
- Low confidence: not enough messages, unknown relationship, mixed personal/business content.
- Protected: VIP/client/important sender, requires reply, recent direct human conversation, or user previously marked important.

## Scope B — Mailbox cleanup UI

Enhance or extend `/bulk-triage` rather than creating a disconnected console. If the page becomes too crowded, add a sub-route such as:

```text
/bulk-triage/mailbox-cleanup
/bulk-triage/mailbox-cleanup/{sender_key}
```

The UI should show sender/domain cleanup cards or table rows with:

- sender/domain
- total message count
- unread count
- oldest/newest dates
- cleanup confidence
- classification mix
- recommendation
- protection flags
- evidence summary
- sample subjects/snippets, sanitized and compact
- proposed label
- action buttons

Required operator actions:

- Refresh cleanup candidates.
- View sender evidence.
- Mark sender as noise locally.
- Mark sender as protected / not noise.
- Prepare Gmail label action.
- Prepare Gmail archive action.
- Prepare Gmail label-and-archive action.
- Prepare Gmail delete-candidate action.

The UI must make clear whether an action is:

- local only
- Gmail dry-run
- Gmail live capable but gated
- blocked by missing flags/scopes/allowlist/provider readiness

Do not bury the operator in single-message rows when the useful object is clearly the sender/domain. This workflow should answer: "Who is filling my mailbox with crap, and what can I safely do about it?"

## Scope C — Gmail cleanup execution

Use the existing execution safety model. Do not create direct Gmail mutations from the cleanup page.

Bulk Gmail cleanup actions should become execution records where practical:

```text
prepare → approve → confirm → execute → audit
```

Allowed Gmail cleanup actions for this phase:

1. Label messages from a sender/domain with a clear cleanup label.
2. Archive messages from a sender/domain.
3. Label and archive messages from a sender/domain.
4. Prepare delete candidates.

Preferred labels:

```text
RTH-Cleanup/Noise
RTH-Cleanup/Marketing
RTH-Cleanup/Newsletter
RTH-Cleanup/Delete Candidate
```

Deletion policy:

- Do not silently hard-delete mail.
- If delete is implemented, use Gmail trash/move-to-trash semantics only, never permanent delete.
- Delete must require a prepared execution record, approval, confirmation, operational test mode, allowlist/safe policy where applicable, and audit.
- It is acceptable for Phase 23 to implement label/archive execution and leave delete as a prepared/review-only candidate if that is faster and safer.

Gmail write behavior must preserve all existing controls:

- `GMAIL_WRITE_ENABLED`
- `GMAIL_LABEL_ARCHIVE_ENABLED`
- `EXECUTION_PROVIDER`
- `EXTERNAL_WRITE_DRY_RUN`
- `OPERATIONAL_TEST_MODE`
- approval/confirmation/audit
- provider status readiness

If Gmail label/archive currently operates only on a single payload shape, extend the payload intentionally and add focused tests. Do not bypass `execution_service`.

## Scope D — Candidate persistence and audit

If existing `AutomationCandidate` is sufficient, extend it carefully. If sender-level cleanup needs durable state, add a small dedicated model/migration, for example:

```text
MailboxCleanupCandidate
MailboxCleanupActionLog
```

Store:

- sender/domain key
- source type
- message count snapshot
- confidence score
- recommendation
- status: pending, approved, rejected, protected, executed, failed, undone
- reason/evidence summary
- associated execution record where applicable
- created/updated timestamps

Do not store unnecessary full message bodies in cleanup candidate tables. Use existing message records for drill-in.

Actions must be auditable and reversible where local-only. External Gmail operations should be auditable through existing execution records.

## Scope E — Learning from cleanup decisions

When Rohan marks a sender as noise/protected/not-noise:

- update contact status where appropriate
- use existing feedback/correction patterns where available
- suppress future cleanup recommendations for protected senders
- boost future confidence for repeatedly approved noise senders/domains
- keep this local and explainable

Do not create a black-box spam classifier. Use transparent rules, evidence, and operator corrections.

## Scope F — Dashboard and daily operations integration

Update the dashboard Start Here Today lane or nearby dashboard card to include:

- cleanup candidates count
- high-confidence noise sender count
- protected/blocker count
- prepared cleanup executions count
- link to mailbox cleanup view

Update operational smoke only if useful:

- Gmail label/archive readiness
- cleanup label readiness
- cleanup execution dry-run/live status

Do not turn smoke into a giant mailbox scan. Smoke should check readiness, not do heavy cleanup analysis unless explicitly triggered.

## Scope G — Outlook write planning retained

The original Outlook write planning remains in this phase, but it is secondary and planning-only.

Document required delegated permissions for future Outlook write features:

- `Mail.Read`
- `Mail.ReadWrite` for draft creation or mailbox updates
- `Mail.Send` for send
- `offline_access`
- `User.Read`

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

Document intended payload shapes for:

- Outlook draft creation
- Outlook reply send
- Outlook folder/archive candidate if ever needed

Provider Status and Operational Smoke may show disabled guidance for Outlook write readiness, but no real Outlook write controls should be exposed in this phase.

## Out of scope

- Implementing Outlook draft creation.
- Implementing Outlook send.
- Implementing Outlook calendar write.
- Implementing Teams write.
- Adding Graph write calls.
- Enabling Microsoft write feature flags.
- Permanent Gmail deletion.
- Unreviewed destructive cleanup.
- Hidden mock fallback for live-provider failures.
- A black-box spam classifier with no evidence trail.

## Testing expectations

Do not run the full suite after every edit. Use focused tests during implementation and full validation once at the end.

Add focused tests for:

- sender/domain cleanup rollup scoring
- protected sender rules
- requires-reply protection
- VIP/client protection
- unsubscribe/noise evidence detection
- label-only vs label-and-archive recommendations
- delete candidates are not executed directly
- cleanup action preparation creates execution records where applicable
- Gmail cleanup actions preserve dry-run/test-mode/feature-flag gates
- `/bulk-triage` or mailbox cleanup route renders
- dashboard cleanup counts render
- Outlook write remains disabled/not implemented

Final validation:

```powershell
python -m ruff check .
python -m pytest -q
python -m alembic upgrade head
```

Route smoke when UI/routes change:

```text
/
/operational-smoke
/providers
/review-packages
/executions
/bulk-triage
/contacts
/drafts
/voice-calibration
/assistant-profile
/admin
/healthz
```

## Documentation updates required

Update only what materially changed:

- `README.md` if setup, flags, or capabilities materially change
- `docs/HELP.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_STATUS.md`
- `docs/PHASE_PLAN.md`
- this phase file

## Acceptance criteria

- Mailbox cleanup view exists under or adjacent to `/bulk-triage`.
- Sender/domain cleanup rollups are available from synced mailbox data.
- High-confidence noise/marketing/newsletter senders are clearly separated from protected/legitimate senders.
- Each recommendation includes evidence and a plain-English reason.
- Operator can mark sender noise/protected/not-noise.
- Operator can prepare Gmail label/archive/label-and-archive cleanup actions where gates allow.
- Delete is either prepared as a review-only candidate or implemented only as move-to-trash through the full execution gate. No permanent deletion.
- Cleanup actions never bypass `execution_service`.
- External Gmail cleanup remains dry-run/live gated by existing flags and audit records.
- Dashboard shows cleanup candidate counts and links to cleanup workflow.
- Outlook write planning doc exists/updated, but no Microsoft write calls are implemented.
- Final validation passes.
