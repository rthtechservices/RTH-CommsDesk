# Phase 25: Controlled Live Gmail Cleanup Execution and Recovery

## Status

Completed — 2026-05-21

## Goal

Enable safe, controlled, operator-verified Gmail cleanup execution: label and/or archive messages from noise senders through the standard prepare → approve → confirm → execute → audit pipeline, with full batch robustness, clear operator-facing confirmation details, large-batch warnings, and recovery guidance throughout.

## Non-negotiable safety rules preserved

- No permanent Gmail delete. Cleanup actions apply labels and/or move messages out of inbox (archive). Nothing is trashed or deleted.
- No direct Gmail mutation from the cleanup list or detail pages. All mutations route through `execution_service` and require an explicit execution record with approve + confirm.
- No Microsoft write implementation. Outlook send, Outlook Calendar, and Teams remain disabled.
- `prepare → approve → confirm → execute → audit` lifecycle is preserved and unchanged.
- Feature flags remain mandatory: `GMAIL_WRITE_ENABLED`, `GMAIL_LABEL_ARCHIVE_ENABLED`, `EXECUTION_PROVIDER=external`, `OPERATIONAL_TEST_MODE`, `EXTERNAL_WRITE_DRY_RUN`.
- No hidden mock fallback on live provider failure.

## Deliverables

### 1. Batch operation robustness (`app/services/external_provider_clients.py`)

- **Deduplication**: `source_message_ids` are deduplicated (preserving order via `dict.fromkeys`) before any API call, preventing double-labelling or double-archiving.
- **Chunked processing**: Messages are processed in chunks of 50 (`_BATCH_CHUNK_SIZE = 50`). Avoids overwhelming the Gmail API for large sender histories.
- **Partial failure surfacing**: Returns `attempted_count`, `succeeded_count`, `failed_count`, `error_count`. Status is `"applied"` only when all messages succeed; `"partial"` when some fail; `"failed"` when all fail.
- **Empty list safety**: `source_message_ids=[]` or `None` returns `{"status": "skipped", "reason": "no_message_ids", ...}` without calling Gmail.
- **Audit-clean results**: `label_id` is omitted from the result dict; errors are capped at 5 entries with no private content.

### 2. Mock provider update (`app/services/execution_service.py`)

`MockExecutionProvider.apply_gmail_label_archive_batch` updated to match the new result shape: deduplicates IDs and returns `attempted_count`, `succeeded_count`, `failed_count`, `applied_count`.

### 3. Recovery guidance and large-batch threshold (`app/services/mailbox_cleanup_service.py`)

- `LARGE_BATCH_THRESHOLD = 50` constant: the threshold above which an extra operator confirmation warning is shown.
- `cleanup_execution_details(payload, posture)` helper: returns structured operator-facing confirmation data for the execution detail template. Keys: `sender_email`, `sender_domain`, `message_count`, `cleanup_mode`, `label_name`, `is_label`, `is_archive`, `permanent_delete` (always `False`), `dry_run_mode`, `posture_label`, `large_batch_warning`, `audit_statement`, `recovery_guidance`.

### 4. Execution detail page (`app/web/templates/execution_detail.html`)

- **Gmail Cleanup Confirmation section**: rendered when `cleanup_details` is non-empty. Shows all confirmation fields: sender, domain, messages affected, mode badge, label applied (yes/no + name), archive applied (yes/no), permanent delete (explicitly NO), provider posture (dry-run or live), recovery guidance panel, audit statement.
- **Large-batch warning block**: visible when `cleanup_details.large_batch_warning` is `True` (message count >50). Full-width amber warning block above the confirmation table.
- **Sidebar extra copy**: when the record is in `approved` state and `cleanup_details.large_batch_warning` is `True`, the confirm button area shows a brief reminder of the message count and mode.

### 5. Execution detail route update (`app/web/routes.py`)

- Imports `cleanup_execution_details` from `mailbox_cleanup_service`.
- Parses `record.payload_json` safely (try/except).
- Calls `cleanup_execution_details(payload, posture)` only when `payload.cleanup_mode` is present.
- Passes `cleanup_details` to the template context.

### 6. Operator script (`scripts/test-gmail-cleanup-execution.ps1`)

Read-only informational script that:
- Activates `.venv`.
- Loads `.env` values.
- Displays a flag matrix for all cleanup-relevant environment variables.
- Describes the current effective posture (mock / dry-run / live / blocked) in color.
- Prints the required `.env` configuration for live cleanup.
- Prints the 10-step cleanup operator workflow.
- Optionally calls `/api/smoke/status` when run with `-ShowSmoke`.
- Prints direct links to cleanup UI, executions, providers, and smoke pages.
- Never writes to Gmail or modifies any external system.

### 7. Phase 25 tests (`tests/test_phase_25_gmail_cleanup_execution.py`)

30 focused tests covering:
- Feature flag gate: blocked when `GMAIL_WRITE_ENABLED=false`, when `GMAIL_LABEL_ARCHIVE_ENABLED=false`, when provider is mock; allowed when all flags set.
- Dry-run: `GuardedExternalProvider` does not instantiate `GmailWriteClient` when `EXTERNAL_WRITE_DRY_RUN=true`; result reflects mode and count.
- Payload routing: `cleanup_label`, `cleanup_archive`, `cleanup_label_and_archive` all produce the correct payload keys.
- Mock provider handles all cleanup modes correctly with new result shape.
- Deduplication: mock and live client both deduplicate before processing.
- Empty/None IDs: live client returns `skipped` for empty or `None` ID list.
- Partial failures: live client returns `partial` status with correct `succeeded_count`/`failed_count`; all-fail returns `failed`.
- Result hygiene: `label_id` not in result; no tokens/secrets in result string.
- `cleanup_execution_details()`: tested for all three modes, large-batch warning, dry-run flag pass-through, audit statement.
- Cleanup execution posture: mock/blocked/dry-run/live correctly mapped.
- Operational smoke: smoke status includes `mailbox_cleanup_execution_posture` with required keys; `test_execution_readiness.gmail_cleanup` entry present.
- Outlook write disabled: three provider rows confirmed disabled/not-implemented.
- `LARGE_BATCH_THRESHOLD` constant is exactly 50; boundary conditions tested.

### 8. Documentation

- `docs/HELP.md`: new "Daily Gmail cleanup runbook" section (10-step flow, flag reference, recovery instructions, rollback config).
- `docs/IMPLEMENTATION_LOG.md`: Phase 25 entry at top.
- `docs/LESSONS_LEARNED.md`: Phase 25 lessons (batch result shape consistency, execution detail route integration, PowerShell operator scripts).
- `docs/PHASE_STATUS.md`: Phase 25 row added, Phase 24 date corrected to 2026-05-20.
- `docs/PHASE_PLAN.md`: active phase updated.
- `docs/phases/PHASE_25_CONTROLLED_LIVE_GMAIL_CLEANUP.md`: this file.

## Architecture notes

### Batch processing rationale

Gmail's per-message `messages.modify` API is simple and safe but inefficient at scale. The chunked approach (50 per chunk) means very large sender histories (200+ messages) are processed in ~4 API calls rather than one giant loop, reducing both memory and API load. If Gmail implements or exposes `batchModify` more reliably in future, the client can be updated to use it within the same interface.

### Why `label_id` is omitted from audit results

Label IDs are internal Gmail identifiers that can change across Google accounts, OAuth reauthorizations, or label renames. Storing them in the audit trail would produce meaningless non-reproducible values. The audit trail stores `label_name` (human-readable, stable) and omits `label_id`.

### Confirmation detail design

The `cleanup_execution_details()` helper is intentionally stateless — it takes only the execution payload dict and an optional posture dict. This makes it testable without a database session and safe to call from the route layer without additional DB queries. The posture is passed in from the route, which already calls `cleanup_execution_posture(settings)`.

### Recovery guidance specificity

Recovery guidance is mode-specific and includes the sender email and label name from the actual payload, not generic placeholders. This means the guidance shown on the execution detail page is directly actionable in Gmail search.

## Testing notes

Run focused tests:

```powershell
python -m pytest tests/test_phase_25_gmail_cleanup_execution.py -q
```

Run full suite to verify no regressions:

```powershell
python -m pytest -q
```

Run migrations:

```powershell
python -m alembic upgrade head
```

Verify operator script syntax:

```powershell
pwsh -NoProfile -Command "[System.Management.Automation.Language.Parser]::ParseFile('scripts/test-gmail-cleanup-execution.ps1', [ref]`$null, [ref]`$null)"
```
