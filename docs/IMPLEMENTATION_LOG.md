# Implementation Log

Record completed work here at the end of every phase. Newest entries should be added at the top.

## 2026-05-19 — Phase 24: Mailbox Cleanup Live Hardening, Real-Inbox Smoke, and Operator Trust Pass

### Summary
- Added `scripts/smoke-mailbox-cleanup.ps1` for real-inbox mailbox cleanup smoke with safe defaults: optional migrations, Gmail sync/backfill guidance, cleanup refresh call, posture reporting, and summary counts.
- Added API endpoints `POST /api/mailbox-cleanup/refresh` and `GET /api/mailbox-cleanup/summary` for non-destructive smoke/readiness automation.
- Hardened mailbox cleanup candidate quality logic in `mailbox_cleanup_service`: stricter repeated-evidence thresholds, conservative protection for client-work and recent personal exchanges, and stricter delete-candidate gating.
- Hardened execution/payload behavior for cleanup batches: unsupported cleanup modes now fail closed; label-required modes enforce `cleanup_label_name`; cleanup execution readiness is explicitly modeled in test policy.
- Extended operational smoke/readiness with lightweight mailbox cleanup checks (table presence, count readiness timing, cleanup execution posture) and added `/bulk-triage/mailbox-cleanup` to route smoke coverage.
- Improved cleanup UI trust copy on mailbox cleanup list/detail and operational smoke pages; dashboard Start Here Today cleanup counters stay visible.
- Preserved hard safety rules: no direct Gmail mutation from cleanup pages, no permanent delete, no Microsoft write implementation, and cleanup execution remains prepare -> approve -> confirm -> execute -> audit.

### Files changed
- `app/services/mailbox_cleanup_service.py`
- `app/services/external_provider_clients.py`
- `app/services/execution_service.py`
- `app/services/execution_test_policy.py`
- `app/services/operational_status_service.py`
- `app/services/operational_smoke_runner.py`
- `app/api/routes.py`
- `app/web/routes.py`
- `app/web/templates/mailbox_cleanup.html`
- `app/web/templates/mailbox_cleanup_detail.html`
- `app/web/templates/dashboard.html`
- `app/web/templates/operational_smoke.html`
- `scripts/smoke-mailbox-cleanup.ps1`
- `tests/test_mailbox_cleanup.py`
- `tests/test_execution_test_policy.py`
- `tests/test_phase_22_daily_operations.py`
- `tests/test_operational_workflow.py`
- `README.md`
- `docs/PHASE_PLAN.md`
- `docs/PHASE_STATUS.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_24_MAILBOX_CLEANUP_LIVE_HARDENING.md`

### Focused tests run during implementation
- `python -m pytest tests/test_mailbox_cleanup.py -q` — passed, 46 tests.
- `python -m pytest tests/test_execution_test_policy.py -q` — passed, 11 tests.
- `python -m pytest tests/test_execution_service.py -q` — passed, 11 tests.
- `python -m pytest tests/test_phase_22_daily_operations.py -q` — passed, 7 tests.
- `python -m pytest tests/test_operational_workflow.py -q` — passed, 12 tests.

### Script syntax validation
- `pwsh -NoProfile -Command "[System.Management.Automation.Language.Parser]::ParseFile('scripts/smoke-mailbox-cleanup.ps1', [ref]$null, [ref]$null)"` — parser reported no syntax errors.

### Final validation
- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 282 tests.
- `python -m pytest -q` (second run for flaky triage) — passed, 282 tests.
- `python -m alembic upgrade head` — passed.

### Route smoke
- TestClient route smoke returned HTTP 200 for `/`, `/operational-smoke`, `/providers`, `/review-packages`, `/executions`, `/bulk-triage`, `/bulk-triage/mailbox-cleanup`, `/contacts`, `/drafts`, `/voice-calibration`, `/assistant-profile`, `/admin`, and `/healthz`.

### Flaky test triage
- A pre-existing flaky test was not reproducible in Phase 24 validation.
- Observed failure in this phase: none (full suite passed twice).
- Recommended follow-up: if the previously reported intermittent failure reappears, capture the exact failing test name and stack trace from that run and add a targeted stabilization issue/phase item.

## 2026-05-20 — Phase 23: Mailbox Cleanup, Sender Noise Automation, and Outlook Write Planning

### Summary
- Added `MailboxCleanupCandidate` and `MailboxCleanupActionLog` ORM models to `entities.py` with `MailboxCleanupStatus` and `MailboxCleanupAction` enums.
- Created Alembic migration `0015_mailbox_cleanup_candidates.py` with String-based status/action columns for SQLite compatibility.
- Built `app/services/mailbox_cleanup_service.py` with full sender-level rollup analysis: protection detection (VIP, client/partner/vendor, requires-reply, human-personal), confidence scoring (0.0–0.95), label recommendation, evidence summary, and five action types.
- All external Gmail cleanup operations go through `execution_service` (prepare → approve → confirm → execute → audit). No direct Gmail API calls from cleanup pages.
- Extended `execution_service` with `apply_gmail_label_archive_batch` on all three provider classes (Protocol, Mock, Guarded). Updated `_execute_with_provider` to route payloads with `cleanup_mode` key to the batch handler.
- Extended `GmailWriteClient` with `apply_label_archive_batch` and `_ensure_label_exists` methods supporting `cleanup_label`, `cleanup_archive`, and `cleanup_label_and_archive` modes.
- Added 12 new web routes under `/bulk-triage/mailbox-cleanup/` including list view, detail view, refresh, mark-noise, mark-protected, mark-not-noise, prepare-label, prepare-archive, prepare-label-and-archive, mark-delete-candidate.
- Added `_cleanup_label_posture()` helper for unified posture display across cleanup pages.
- Created `app/web/templates/mailbox_cleanup.html` and `app/web/templates/mailbox_cleanup_detail.html` with execution posture bar, confidence indicators, classification mix, evidence summary, and full action log.
- Updated dashboard to include cleanup stats (total candidates, high-confidence, protected, pending execution) in Start Here Today section and backlog_stats dict.
- Added Mailbox Cleanup button to bulk triage page and dashboard.
- Added 43-test suite `tests/test_mailbox_cleanup.py` covering rollup scoring, protection rules, local actions, execution preparation, feature flag gates, provider routing, dashboard stats, routes, and Outlook write disabled confirmation.
- Outlook write remains planning-only; cleanup page includes explicit planning note.

### Files changed / created
- `app/models/entities.py` — `MailboxCleanupStatus`, `MailboxCleanupAction`, `MailboxCleanupCandidate`, `MailboxCleanupActionLog`
- `alembic/versions/0015_mailbox_cleanup_candidates.py` — new migration
- `app/services/mailbox_cleanup_service.py` — new file
- `app/services/execution_service.py` — `apply_gmail_label_archive_batch` on Protocol/Mock/Guarded, `_execute_with_provider` cleanup routing
- `app/services/external_provider_clients.py` — `apply_label_archive_batch`, `_ensure_label_exists`
- `app/web/routes.py` — 12 new cleanup routes, `_cleanup_label_posture`, dashboard cleanup stats
- `app/web/templates/mailbox_cleanup.html` — new
- `app/web/templates/mailbox_cleanup_detail.html` — new
- `app/web/templates/bulk_triage.html` — cleanup link added
- `app/web/templates/dashboard.html` — cleanup stats in Start Here Today
- `tests/test_mailbox_cleanup.py` — new, 43 tests

## 2026-05-20 — Phase 22: Daily Operations Hardening and Persistent Smoke Sprint

### Summary
- Added `OperationalSmokeRun` and `OperationalSmokeCheck` persistence with sanitized summary/detail JSON and an explicit `external_write_performed=false` default.
- Added `app/services/operational_smoke_runner.py` for route, provider, sync, execution audit, voice memory, database/Alembic, token guidance, backup readiness, and Microsoft boundary checks.
- Added smoke APIs: `POST /api/operational-smoke/run`, `GET /api/operational-smoke/runs`, `GET /api/operational-smoke/runs/{run_id}`, and startup-mode API.
- Enhanced `/operational-smoke` with Run Smoke Now, latest status, recent history, and smoke detail pages.
- Added sanitized local backup service, admin backup API/UI, and backup metadata from filesystem scan.
- Added Windows scripts for startup, smoke, backup, and token reauthorization.
- Added dashboard Start Here Today lane with last smoke, last Gmail/Outlook sync, pending review/execution/guidance counts, provider blockers, and daily action buttons.
- Improved provider guidance with exact reauth commands and required Gmail, Google Calendar, and Microsoft Graph scopes.
- Kept Gmail/Calendar write controls intact and kept Outlook send, Outlook Calendar write, and Teams disabled/not implemented.

### Files changed
- `app/models/entities.py`
- `alembic/versions/0014_operational_smoke_persistence.py`
- `app/services/operational_smoke_runner.py`
- `app/services/backup_service.py`
- `app/services/provider_status_service.py`
- `app/api/routes.py`
- `app/web/routes.py`
- `app/web/templates/operational_smoke.html`
- `app/web/templates/operational_smoke_run.html`
- `app/web/templates/admin.html`
- `app/web/templates/dashboard.html`
- `app/web/templates/providers.html`
- `scripts/start-commsdesk.ps1`
- `scripts/smoke-commsdesk.ps1`
- `scripts/backup-commsdesk.ps1`
- `scripts/reauth-commsdesk.ps1`
- `tests/test_phase_22_daily_operations.py`
- `README.md`
- `docs/HELP.md`
- `docs/PHASE_PLAN.md`
- `docs/PHASE_STATUS.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/phases/PHASE_22_DAILY_OPERATIONS_HARDENING.md`

### Tests run
- Focused tests: `python -m pytest tests/test_phase_22_daily_operations.py -q` — passed, 6 tests.
- Focused ruff on changed files — passed.
- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 234 tests.
- `python -m alembic upgrade head` — passed.

### Smoke tests
- TestClient route smoke returned HTTP 200 for `/`, `/operational-smoke`, `/providers`, `/review-packages`, `/executions`, `/bulk-triage`, `/contacts`, `/drafts`, `/voice-calibration`, `/assistant-profile`, `/admin`, and `/healthz`.

### Known issues
- Smoke runner checks route registration/readiness and persisted metadata; browser-level rendering is still covered by route smoke.
- Backup restore is intentionally not implemented in this phase.

### Recommended next actions
- Human review of Phase 22 daily operations flow after final validation.

## 2026-05-20 — Phase 21: Product Acceleration Sprint

### Summary
- Added `/assistant-profile` with preferred sign-off visibility, approved/pending/rejected/disabled voice guidance, relationship overrides, evidence counts, safe excerpts, and edit/approve/reject/disable/reset controls.
- Added a local Assistant Profile draft preview that uses approved voice memory in memory only. It does not create a local draft row, execution record, Gmail draft, send, calendar item, or external provider call.
- Enhanced `/operational-smoke` with an operator smoke checklist and direct route smoke links for AI, Microsoft Graph, Outlook sync, Gmail draft dry-run/live readiness, Google Calendar readiness, execution audit checks, dry-run state, operational test mode, and allowlist state.
- Kept Outlook send, Outlook Calendar, and Teams disabled/not implemented; documentation records write planning only.
- Refreshed the operator help/runbook for daily startup, sync/testing workflow, OAuth reauthorization, test allowlist use, dry-run/live posture, and safe-mode rollback.

### Files changed
- `app/services/voice_learning_service.py`
- `app/services/operational_status_service.py`
- `app/web/routes.py`
- `app/web/templates/base.html`
- `app/web/templates/dashboard.html`
- `app/web/templates/assistant_profile.html`
- `app/web/templates/operational_smoke.html`
- `tests/test_phase_21_assistant_profile.py`
- `docs/HELP.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_STATUS.md`
- `docs/phases/PHASE_21_PRODUCT_ACCELERATION_SPRINT.md`

### Tests run
- `python -m pytest tests/test_phase_21_assistant_profile.py -q` — passed, 5 tests.
- `python -m ruff check tests\test_phase_21_assistant_profile.py app\web\routes.py app\services\voice_learning_service.py app\services\operational_status_service.py` — passed.
- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 228 tests.
- `python -m alembic upgrade head` — passed.

### Smoke tests
- Focused route smoke in tests returned HTTP 200 for `/`, `/assistant-profile`, `/operational-smoke`, `/providers`, `/review-packages`, `/executions`, `/bulk-triage`, `/contacts`, `/drafts`, `/voice-calibration`, `/admin`, and `/healthz`.
- TestClient route smoke returned HTTP 200 for `/`, `/assistant-profile`, `/operational-smoke`, `/providers`, `/review-packages`, `/executions`, `/bulk-triage`, `/contacts`, `/drafts`, `/voice-calibration`, `/admin`, and `/healthz`.

### Known issues
- Smoke results are displayed as a sanitized checklist rather than persisted in a new schema table. This was kept intentionally light for Phase 21.
- The Assistant Profile lifecycle uses the existing `VoiceGuidance` statuses plus `is_active`; no new vector memory or CRM-style profile model was added.

### Recommended next actions
- Human review of Phase 21.
- Run a real local operator smoke with `/api/ai/test`, `/api/graph/test`, Outlook sync, Gmail draft dry-run, and Calendar dry-run using only allowlisted test data.

## 2026-05-19 — Phase 20: Assistant Intelligence, Voice, and Calendar Reasoning Quality

### Summary
- Added realistic recommendation-quality fixtures for action, no-reply, scheduling, reminders, noise, vague asks, latest-message-change, and sent-mail sign-off learning.
- Improved sent-mail learning to infer recurring global operator sign-off guidance and let approved global guidance flow into draft generation.
- Sanitized send-ready draft output so generic placeholders such as `[Your Name]`, `[Your signature]`, `[your name]`, and `[signature]` are removed before execution preparation.
- Applied approved sign-off guidance to mock/local drafts and prevented learned sign-offs from being replaced by stock formal closings.
- Tightened calendar reasoning so date-only meeting requests become clarifying replies with all-day tentative candidates, clear date/time requests stay timezone-safe, relative Fridays are anchored to the message date, and past reminders/events are not prepared.
- Added review-package correction persistence and compact correction controls/evidence display on review package detail.
- Preserved Phase 19 execution gating and Microsoft write boundaries.

### Files changed
- `app/services/analysis_service.py`
- `app/services/calendar_availability_service.py`
- `app/services/draft_service.py`
- `app/services/feedback_service.py`
- `app/services/voice_learning_service.py`
- `app/web/routes.py`
- `app/web/templates/review_package_detail.html`
- `tests/conftest.py`
- `tests/fixtures/prompt_quality_cases.json`
- `tests/test_ai_analysis.py`
- `tests/test_calendar_availability.py`
- `tests/test_draft_generation.py`
- `tests/test_voice_learning_quality.py`
- `README.md`
- `docs/HELP.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_STATUS.md`
- `docs/phases/PHASE_20_INBOX_INTELLIGENCE_QUALITY_PASS.md`

### Tests run
- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 223 tests.
- `python -m alembic upgrade head` — passed.

### Smoke tests
- Temporary Uvicorn route smoke on port 8765 returned HTTP 200 for `/`, `/operational-smoke`, `/providers`, `/review-packages`, `/executions`, `/bulk-triage`, `/contacts`, `/drafts`, `/voice-calibration`, `/admin`, and `/healthz`.

### Known issues
- This phase does not add a dedicated Assistant Profile console; Phase 21 remains the right place for richer voice-memory management.
- Date-only calendar candidates are represented with the existing calendar proposal fields as all-day tentative review candidates; no new external calendar behavior was added.

### Recommended next actions
- Human review of Phase 20 quality behavior.
- Next recommended phase: Phase 21 — Voice Memory and Assistant Personalization Console.

## 2026-05-19 — Phase 19: Test Email Execution Enablement

### Summary
- Added explicit `OPERATIONAL_TEST_MODE` and `EXECUTION_TEST_EMAIL_ALLOWLIST` settings with `.env.example`, README, and Help documentation.
- Added centralized `execution_test_policy` parsing/readiness logic for exact email and explicit `@domain` allowlist entries.
- Enforced the policy immediately before external Gmail/Google Calendar provider execution so non-allowlisted live writes fail closed instead of downgrading to mock success.
- Gated Gmail draft, Gmail send, and Google Calendar test execution with operational test mode, external provider mode, per-action flags, dry-run rules, and allowlist checks where applicable.
- Added Test Execution Readiness UI on execution detail, operational smoke, dashboard ready-execution widgets, draft review, and review package detail while preserving Phase 18.7 styling semantics.
- Preserved Microsoft boundaries: Outlook send, Outlook calendar, and Teams remain disabled/not implemented.

### Files changed
- `app/core/config.py`
- `app/services/execution_test_policy.py`
- `app/services/execution_service.py`
- `app/services/operational_status_service.py`
- `app/services/provider_status_service.py`
- `app/web/routes.py`
- `app/api/routes.py`
- `app/web/templates/dashboard.html`
- `app/web/templates/operational_smoke.html`
- `app/web/templates/execution_detail.html`
- `app/web/templates/review_package_detail.html`
- `app/web/templates/draft_review.html`
- `.env.example`
- `tests/conftest.py`
- `tests/test_execution_test_policy.py`
- `tests/test_execution_service.py`
- `tests/test_operational_workflow.py`
- `README.md`
- `docs/HELP.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_STATUS.md`
- `docs/phases/PHASE_19_TEST_EMAIL_EXECUTION_ENABLEMENT.md`

### Tests run
- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 215 tests.
- `python -m alembic upgrade head` — passed.

### Smoke tests
- Temporary Uvicorn route smoke on port 8765 returned HTTP 200 for `/`, `/operational-smoke`, `/providers`, `/review-packages`, `/executions`, `/bulk-triage`, `/contacts`, `/drafts`, `/voice-calibration`, `/admin`, and `/healthz`.

### Known issues
- Live Gmail/Google writes were not executed during this implementation pass; dry-run and policy enforcement were validated by tests.
- Gmail send remains blocked while `EXTERNAL_WRITE_DRY_RUN=true` by design.

### Recommended next actions
- Human review of Phase 19 controlled test lane.
- Next recommended phase: Phase 20 — Inbox Intelligence Quality Pass.

## 2026-05-20 — Phase 18.7: Interaction Hierarchy, Triage Ergonomics & RTH Palette Alignment

### Summary
- UI/UX-only pass. No new backend services, no schema changes, no new outbound behavior.
- Replaced old ad-hoc color variables in `ui.css` with the full RTH/TaskDesk palette: blue, sky, cyan, teal, green, amber, orange, red, pink, purple, indigo. Added semantic tokens: `--ok`, `--warn`, `--bad`, `--info`, `--ai`, `--calendar`.
- Darkened background from `#0c1117` to `#11161D`.
- Changed workflow rail semantics: `.done` = past stage (subtle green), `.active` = current stage (amber glow). Previously the active stage used green, which was misleading (current stage = pending work, not success).
- Added Next Best Action (NBA) strip to dashboard: tier-based amber/red/green color with primary + secondary action buttons.
- Added `_compute_next_best_action()` helper to `routes.py` that computes the most important next step from backlog stats.
- Improved information hierarchy: Command Center numbers colored amber (non-zero) or green (zero). Attention queue score cells use tier color classes (urgent/high/medium/low). Source badge classes (src-gmail, src-outlook). Action badge classes (act-reply, act-schedule, act-review, act-noise). Row action hierarchy: Open=primary, Important=amber, Reviewed=outline.
- Updated workflow rail stages on 7 pages: message_detail (Analyze active), review_packages/detail (Review active), executions/detail (Execute active), providers+operational_smoke (Audit active).
- Polished providers.html: Microsoft write boundary callout-grey cards, semantic badge states.
- Polished operational_smoke.html: callout-red blockers summary at top, callout-green if clear.
- Polished executions.html: semantic badge colors, empty state guidance text.
- Polished review_packages.html: callout-amber local-recommendations notice, semantic badge states.
- Added `tests/test_phase_18_7_interaction_hierarchy.py` with 36 tests covering NBA strip, status sections, action hierarchy, workflow stage semantics, and regression guards for existing boundary strings.
- Updated `test_operational_workflow.py` workflow assertions to match new `done`/`active` stage semantics.
- All 202 tests pass. Ruff: no errors.

### Files changed
- `app/web/ui.css`
- `app/web/routes.py`
- `app/web/templates/dashboard.html`
- `app/web/templates/message_detail.html`
- `app/web/templates/review_packages.html`
- `app/web/templates/review_package_detail.html`
- `app/web/templates/executions.html`
- `app/web/templates/execution_detail.html`
- `app/web/templates/providers.html`
- `app/web/templates/operational_smoke.html`
- `tests/test_phase_18_7_interaction_hierarchy.py` (new)
- `tests/test_operational_workflow.py` (updated assertions)
- `docs/phases/PHASE_18_7_INTERACTION_HIERARCHY_TRIAGE_ERGONOMICS.md` (new)


### Summary
- Completely rewrote `app/web/ui.css` as a dark "mission control" design system with a retro-futuristic 1990s feel. Color palette: `--bg:#0c1117`, dark surface layers, brand green `#1cba8b`, accent blue `#4a8ff5`, status traffic lights.
- Created `app/web/templates/base.html` as a shared Jinja2 base template with sticky dark topbar, nav links, and `{% block %}` slots for all pages.
- Rewrote all 17 page templates to extend `base.html` and use the dark design system, removing all inline CSS and per-page boilerplate.
- Templates rewritten: dashboard, message_detail, review_packages, review_package_detail, executions, execution_detail, providers, operational_smoke, bulk_triage, contacts, voice_calibration, admin, drafts, login, contact_detail, draft_review.
- Added connected pill-segment workflow rail on all applicable pages showing the current step in the Sync → Triage → Analyze → Review → Prepare → Execute → Audit flow.
- Added `tests/test_phase_18_6_visual_design.py` with 20 tests covering dark theme presence, nav structure, grouped action panels, Microsoft write boundary strings, section headers, and route smoke.
- Fixed admin template to use actual route variables (`message_body_count`, `sent_excerpt_count`, `audit_count`) instead of nonexistent `system_info`.
- Fixed message_detail to show "Reset contact normal" button for VIP/noise contacts.
- Fixed multiple template strings to satisfy existing test assertions ("AI analysis provider", "Azure/OpenAI analysis", "Gmail full-body sync", "was not created in Gmail", "Prepare external Gmail draft execution", "Review-only local suggestion", "Edit Contact", "Local recommendation only").

### Files changed
- `app/web/ui.css` (completely rewritten)
- `app/web/templates/base.html` (new)
- `app/web/templates/dashboard.html`
- `app/web/templates/message_detail.html`
- `app/web/templates/review_packages.html`
- `app/web/templates/review_package_detail.html`
- `app/web/templates/executions.html`
- `app/web/templates/execution_detail.html`
- `app/web/templates/providers.html`
- `app/web/templates/operational_smoke.html`
- `app/web/templates/bulk_triage.html`
- `app/web/templates/contacts.html`
- `app/web/templates/voice_calibration.html`
- `app/web/templates/admin.html`
- `app/web/templates/drafts.html`
- `app/web/templates/login.html`
- `app/web/templates/contact_detail.html`
- `app/web/templates/draft_review.html`
- `tests/test_phase_18_6_visual_design.py` (new)
- `docs/PHASE_STATUS.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_18_6_VISUAL_DESIGN_SYSTEM_POLISH.md` (new)

### Tests run
- `python -m pytest -q` — 158 passed, 0 failed.
- `python -m ruff check .` — passed.
- `python -m alembic upgrade head` — passed.

## 2026-05-19 — Phase 18.5: Dashboard and Workflow UI Polish

### Summary
- Added a shared UI stylesheet with compact panels, workflow breadcrumbs, status lights, badges, responsive layouts, and configuration cards.
- Consolidated the dashboard into operational status, command-center, and source/runtime cards with clear green/amber/red/grey status cues and next-step links.
- Reworked the attention queue into denser rows showing score, source, sender/contact, subject, recommended action, status/date, and primary actions.
- Made right-side dashboard insights denser dashboard widgets.
- Rebuilt message detail action layout into Message, Conversation/AI, Contact, and Draft/execution sections.
- Fixed the message detail timeline/body overflow behavior with bounded wrapping and scrolling inside the main content column.
- Added context-aware contact actions so redundant VIP/noise/reset buttons are hidden based on contact state.
- Added concise workflow help/breadcrumb text to dashboard, message detail, review packages, executions, provider status, operational smoke, and detail pages.
- Added provider/operational configuration guidance panels without implementing `.env` editing.

### Files changed
- `app/web/ui.css`
- `app/web/templates/dashboard.html`
- `app/web/templates/message_detail.html`
- `app/web/templates/review_packages.html`
- `app/web/templates/review_package_detail.html`
- `app/web/templates/executions.html`
- `app/web/templates/execution_detail.html`
- `app/web/templates/providers.html`
- `app/web/templates/operational_smoke.html`
- `tests/test_operational_workflow.py`
- `README.md`
- `docs/HELP.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_STATUS.md`
- `docs/phases/PHASE_18_5_DASHBOARD_WORKFLOW_UI_POLISH.md`

### Tests run
- `python -m pytest tests/test_app_bootstrap.py tests/test_operational_workflow.py tests/test_provider_status.py -q` — passed, 21 tests.
- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 129 tests.
- `python -m alembic upgrade head` — passed.

### Smoke tests
- Temporary Uvicorn route smoke on port 8765 returned HTTP 200 for `/`, `/operational-smoke`, `/providers`, `/review-packages`, `/executions`, `/admin`, and `/healthz`.

### Documentation updated
- `README.md`
- `docs/HELP.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_STATUS.md`
- `docs/phases/PHASE_18_5_DASHBOARD_WORKFLOW_UI_POLISH.md`

### Known issues
- This phase does not add or streamline live outbound execution. Phase 19 remains responsible for controlled test-email/calendar execution enablement.
- Provider and operational pages give copy/paste guidance only; they do not edit `.env` or restart the app.

### Recommended next actions
- Stop for human review of Phase 18.5.
- Next recommended phase: Phase 19 — Test Email Execution Enablement.

## 2026-05-19 — Phase 18: Operational Inbox Workflow Smoke and Fast-Path UX

### Summary
- Added an operational smoke status service plus `/operational-smoke` page for Gmail read config, Outlook delegated Graph readiness, Outlook sync state, Azure/OpenAI readiness, execution provider mode, dry-run, write flags, source counts, workflow counts, and plain-language blockers.
- Updated the dashboard into a clearer operator workflow with operational smoke status, source counts, all/Gmail/Outlook/notification-derived source filters, process-next entry points, and clearer links to review packages and execution approvals.
- Added process-next routes for attention items, pending review packages, and execution records waiting for approval or confirmation.
- Added fast-path links from message detail, review package detail, execution list, execution detail, provider status, and dashboard.
- Removed Teams from the dashboard sync actions while keeping Teams, Outlook send, and Outlook Calendar disabled/not implemented in provider status.
- Added execution error sanitization for token/secret/header markers without converting failed live execution into mock success.

### Files changed
- `app/services/operational_status_service.py`
- `app/services/attention_service.py`
- `app/services/execution_service.py`
- `app/services/provider_status_service.py`
- `app/web/routes.py`
- `app/web/templates/dashboard.html`
- `app/web/templates/operational_smoke.html`
- `app/web/templates/message_detail.html`
- `app/web/templates/review_package_detail.html`
- `app/web/templates/executions.html`
- `app/web/templates/execution_detail.html`
- `app/web/templates/providers.html`
- `tests/test_operational_workflow.py`
- `README.md`
- `docs/HELP.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_STATUS.md`
- `docs/phases/PHASE_18_OPERATIONAL_INBOX_WORKFLOW_SMOKE.md`

### Tests run
- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 124 tests.
- `python -m alembic upgrade head` — passed.
- Focused preflight: `python -m pytest tests/test_operational_workflow.py tests/test_provider_status.py tests/test_app_bootstrap.py -q` — passed, 21 tests.

### Smoke tests
- Temporary Uvicorn route smoke on port 8765 returned HTTP 200 for `/`, `/providers`, `/review-packages`, `/bulk-triage`, `/executions`, `/admin`, `/healthz`, and `/operational-smoke`.
- `POST /api/graph/test` returned delegated `success=true`, account `me`, HTTP 200, and sanitized status fields only.
- `POST /api/sync/outlook` returned `source_type=outlook`, fetched 100, inserted 0, skipped duplicates 100, updated threads 1, and errors 0.

### Documentation updated
- `README.md`
- `docs/HELP.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_STATUS.md`
- `docs/phases/PHASE_18_OPERATIONAL_INBOX_WORKFLOW_SMOKE.md`

### Known issues
- Outlook send, Outlook Calendar, and Teams remain disabled/not implemented by design.
- Live external Gmail/Google Calendar execution remains guarded by existing feature flags, dry-run, approval, and final confirmation.

### Recommended next actions
- Stop for human review of Phase 18.
- Next recommended phase: Phase 19 — Test Email Execution Enablement.

## 2026-05-19 — Live Microsoft Graph Delegated Outlook Smoke

### Summary
- Completed live local delegated Microsoft Graph authorization after enabling public client flows on the `RTH-CommsDesk` Entra app registration.
- Confirmed `POST /api/graph/test` succeeds with sanitized output: delegated auth mode, account `me`, configured tenant/client, no client secret, HTTP 200, and no token/secret leakage.
- Confirmed `POST /api/sync/outlook` performs live Outlook mail read through Graph and normalizes records into the existing local message/thread model.

### Smoke results
- `POST /api/graph/test` — success `true`, HTTP 200.
- `POST /api/sync/outlook` — fetched 100, inserted 100, skipped duplicates 0, updated threads 79, errors empty.

### Lessons
- Delegated device-code Graph auth requires the Entra app registration to allow public client/native client flows. Without that setting, token polling can fail with `AADSTS7000218` asking for a client assertion or client secret.
- `MICROSOFT_CLIENT_SECRET` should remain blank for the delegated local smoke path.
- Outlook send, Outlook calendar, and Teams remain disabled/not implemented.

## 2026-05-19 — Phase 17: Microsoft Graph Delegated OAuth and Outlook Mail Smoke

### Summary
- Added delegated Microsoft Graph OAuth support for local development with `MICROSOFT_GRAPH_AUTH_MODE=delegated`, configurable scopes, and a local `MICROSOFT_GRAPH_TOKEN_FILE`.
- Preserved the existing app-only Microsoft Graph client-credentials seam.
- Added sanitized `POST /api/graph/test` diagnostics for auth mode, account, configured booleans, success/failure, HTTP status, and sanitized error category/message.
- Implemented read-only Outlook mail sync through Graph `/me/messages` or `/users/{MICROSOFT_ACCOUNT}/messages`, using `$select` and safe paging.
- Updated provider status rows so Microsoft Graph delegated auth and Outlook mail read are visible while Outlook send, Outlook Calendar, and Teams remain disabled/not implemented.

### Files changed
- `app/core/config.py`
- `app/services/microsoft_graph_client.py`
- `app/services/provider_status_service.py`
- `app/api/routes.py`
- `.env.example`
- `.gitignore`
- `tests/test_microsoft_graph_client.py`
- `tests/test_provider_status.py`
- `README.md`
- `docs/HELP.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_PLAN.md`
- `docs/PHASE_STATUS.md`
- `docs/phases/PHASE_17_MICROSOFT_GRAPH_DELEGATED_OAUTH_OUTLOOK_MAIL.md`

### Tests run
- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed.
- `python -m pytest tests/test_microsoft_graph_client.py tests/test_provider_status.py tests/test_external_connectors.py -q` — passed, 14 tests.

### Smoke tests
- Automated validation used mocked Graph HTTP tests for delegated `/me/messages` paging, app-only `/users/{account}/messages`, device-code startup, sanitized test output, and the `/api/graph/test` route.
- Follow-up live local smoke succeeded after Phase 17: `POST /api/graph/test` returned HTTP 200 success, and `POST /api/sync/outlook` fetched 100 Outlook messages, inserted 100, skipped 0 duplicates, and updated 79 threads.

### Documentation updated
- `.env.example`
- `README.md`
- `docs/HELP.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_PLAN.md`
- `docs/PHASE_STATUS.md`
- `docs/phases/PHASE_17_MICROSOFT_GRAPH_DELEGATED_OAUTH_OUTLOOK_MAIL.md`

### Known issues
- Outlook send, Outlook Calendar, and Teams remain disabled/not implemented by design.

### Recommended next actions
- Proceed to Phase 18: Operational Inbox Workflow Smoke and Fast-Path UX.

## 2026-05-19 — Live External Gmail/Calendar Execution Fixes

### Summary
- Replaced one-record-per-source execution behavior with immutable attempt records, including attempt numbers and prepare-new/rerun/clone controls.
- Added send-ready draft fields and execution payload sanitization so review notes stay in CommsDesk and external Gmail drafts receive only the clean subject/body.
- Fixed live Google Calendar execution payloads so reminder and scheduled-event writes include `timeZone` on both `start` and `end`, defaulting to `America/Vancouver`.
- Added configurable `GOOGLE_CALENDAR_TIME_ZONE` and documented it in setup/deployment help.
- Improved live Gmail insufficient-scope handling so execution failures record a clear `gmail_token.json` reauthorization instruction instead of a generic provider error.
- Preserved mock execution and external dry-run behavior, and made tests force mock execution defaults so local `.env` live-provider settings do not leak into the test suite.

### Files changed
- `app/core/config.py`
- `app/services/external_provider_clients.py`
- `app/services/draft_service.py`
- `app/models/entities.py`
- `app/web/routes.py`
- `app/web/templates/execution_detail.html`
- `app/web/templates/executions.html`
- `app/web/templates/draft_review.html`
- `app/api/routes.py`
- `alembic/versions/0013_execution_attempts_send_ready_drafts.py`
- `.env.example`
- `tests/conftest.py`
- `tests/test_external_provider_clients.py`
- `tests/test_execution_service.py`
- `README.md`
- `docs/DEPLOYMENT.md`
- `docs/HELP.md`
- `docs/LESSONS_LEARNED.md`
- `docs/IMPLEMENTATION_LOG.md`

### Tests run
- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 113 tests.
- `python -m pytest tests/test_execution_service.py tests/test_external_provider_clients.py tests/test_draft_generation.py -q` — passed, 20 tests.

### Smoke tests
- Not run against live external writes after the fix; no real email or calendar write was executed during this patch.

### Known issues
- Existing live Gmail tokens created with read-only scopes must be deleted and reauthorized before live compose/send/modify actions can succeed.

## Entry template

```markdown
## YYYY-MM-DD — Phase XX: <title>

### Summary
- 

### Files changed
- 

### Tests run
- `pytest -q` — pass/fail

### Smoke tests
- App startup:
- Dashboard:
- Key workflow:

### Documentation updated
- 

### Known issues
- 

### Recommended next actions
- 
```
