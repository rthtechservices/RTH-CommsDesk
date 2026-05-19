# Phase 18 — Operational Inbox Workflow Smoke and Fast-Path UX

## Objective

Turn the existing Gmail, Outlook, AI analysis, review package, draft, and execution pieces into a practical daily workflow that can be smoke-tested end-to-end with test emails.

This phase should make RTH CommsDesk feel operational, not demo-like. Do not add another major connector. Make the current product path obvious and usable.

## Product intent

The near-term target is:

```text
Sync Gmail/Outlook test inboxes
→ see what needs attention
→ analyze selected conversations
→ review proposed actions
→ generate or inspect draft/action payloads
→ prepare execution
→ approve/confirm dry-run or test-provider execution
→ inspect the audit trail
```

## Current Microsoft Graph local configuration reference

For delegated Outlook read smoke testing, use the locally registered Entra application:

```env
MICROSOFT_TENANT_ID=1ce279ff-f48b-4959-86d5-e9f16a768e6a
MICROSOFT_CLIENT_ID=31f0d287-5142-49b9-a3eb-3d06b50506d9
MICROSOFT_CLIENT_SECRET=
MICROSOFT_ACCOUNT=me
MICROSOFT_GRAPH_ENABLED=true
MICROSOFT_GRAPH_AUTH_MODE=delegated
MICROSOFT_GRAPH_SCOPES=User.Read Mail.Read offline_access
MICROSOFT_GRAPH_TOKEN_FILE=./microsoft_graph_token.json
MICROSOFT_GRAPH_OUTLOOK_MAIL_ENABLED=true
MICROSOFT_GRAPH_TEAMS_ENABLED=false
MICROSOFT_GRAPH_OUTLOOK_CALENDAR_READ_ENABLED=false
MICROSOFT_GRAPH_BASE_URL=https://graph.microsoft.com/v1.0
```

No Microsoft client secret or certificate is required for the delegated device-code path. A secret or certificate is only required for app-only/client-credentials mode, which is not the current local smoke-test path.

If the device-code flow fails with a public-client error, verify the Entra app registration allows public client/device-code flows under Authentication / Advanced settings.

## Scope

### Workflow consolidation

- Add or refine a single operational dashboard path for the daily smoke workflow.
- Make Gmail and Outlook messages appear consistently in the queue and detail views.
- Make source filters obvious: all, Gmail, Outlook, notification-derived.
- Add visible counts for:
  - Gmail sync status.
  - Outlook sync status.
  - unreviewed attention items.
  - pending review packages.
  - ready/waiting execution records.
  - provider warnings.
- Add clear next-step links/buttons from each dashboard section.

### Fast-path UX for test workflows

- Add a "Process next" style path from an attention item or review package to the next useful item.
- Add an "Analyze selected" or equivalent queue-level action where safe and practical.
- Add a clear path from review package detail to draft/action preparation.
- Reduce dead-end pages and repeated navigation.
- Keep external writes gated by existing execution controls, but reduce needless navigation friction.

### Smoke-test surface

Add an operational smoke page or dashboard panel that reports the status of the core local workflow:

- Gmail configured/read sync available.
- Outlook delegated Graph test available.
- Outlook sync enabled/disabled.
- Azure OpenAI live provider configured/test status link.
- Execution provider mode.
- Dry-run state.
- Gmail write flags.
- Google Calendar write flag.
- Pending token/authorization issues.

This should help the operator quickly answer: "Can I use this right now? If not, what exact flag/token/provider is blocking me?"

### Provider diagnostics

- Preserve existing sanitized diagnostics.
- Do not expose tokens, secrets, raw Authorization headers, or private message bodies in diagnostics or docs.
- Provider failures should be plain-language and action-oriented.

## Out of scope

- Outlook send.
- Outlook calendar read/write.
- Teams sync/write.
- New AI model/provider work.
- Vector search.
- Browser extension/mobile approval console.
- Production deployment changes.

## Acceptance criteria

Automated validation must pass:

```powershell
python -m ruff check .
python -m pytest -q
python -m alembic upgrade head
```

Local route smoke must be run against Uvicorn:

```powershell
python -m uvicorn app.main:app --reload
```

Manual smoke checklist:

1. `POST /api/graph/test` returns sanitized delegated Graph status.
2. Gmail sync works against the local test mailbox.
3. Outlook sync works against delegated Graph when configured.
4. Dashboard shows Gmail and Outlook source items clearly.
5. A test message can be opened, analyzed, and converted into a review package.
6. A review package can generate or expose a usable draft/action payload.
7. An execution record can be prepared from the draft/review package.
8. Approval/confirmation flow reaches dry-run or configured test execution.
9. Execution detail shows an audit trail and provider result/error.
10. No Microsoft write actions are enabled.

## Documentation updates required

Update:

- `README.md`
- `docs/HELP.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_STATUS.md`
- this phase file

## Codex notes

Keep this phase focused on the operator workflow. Prefer small, obvious UI improvements and smoke-test diagnostics over new back-end surfaces. If a feature is already present but hard to find, improve discoverability instead of rebuilding it.
