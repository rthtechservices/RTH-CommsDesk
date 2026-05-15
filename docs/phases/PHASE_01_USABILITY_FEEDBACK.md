# Phase 01 — Usability and Structured Feedback Loop

## Objective

Make the existing Gmail MVP easier to use and more teachable. The app should clearly show what needs attention, why it matters, and how the user can correct the system.

## Current observed problems

- Dashboard is raw HTML and hard to scan.
- The Attention Queue shows internal reasons without enough user-friendly context.
- Too many row-level buttons make the interface noisy.
- Message detail pages are sparse.
- Corrections are vague free text and do not create a useful structured learning record.
- Job alerts and newsletters can be over-promoted as work/client-like.
- Important automated reminders, such as insurance renewals, need a higher-priority path.

## Required implementation

### 1. Dashboard usability

- [x] Replace raw bullet lists with a clean page layout.
- [x] Use lightweight CSS only; do not add a heavy frontend framework.
- [x] Make Attention Queue the main section.
- [x] Display useful columns or card fields:
  - Subject
  - Sender
  - Score
  - Status
  - Friendly classification label or tags
  - Short reason
  - Received date if available
  - Primary actions
- [x] Make high-priority items visually prominent.
- [x] Mute likely newsletters/noise.
- [x] Keep row actions minimal. Prefer Details plus one or two primary actions.
- [x] Add clear empty states.

### 2. Message detail usability

The detail page should show:

- [x] Subject
- [x] Sender name and email
- [x] Received date
- [x] Snippet
- [x] Body stored mode
- [x] Classification flags/tags
- [x] Attention score if available
- [x] Contact status: VIP, noise, or normal

Group actions clearly:

- [x] Mark important
- [x] Mark needs reply
- [x] Mark reviewed
- [x] Mark contact VIP
- [x] Mark sender as noise
- [x] Correct classification
- [x] Generate draft placeholder

### 3. Structured corrections

- [x] Add or enhance feedback storage so corrections can capture:

- message_id
- contact_id if available
- original classification summary
- corrected_label
- corrected_importance
- corrected_requires_reply
- corrected_is_noise
- corrected_is_newsletter
- corrected_is_client_work
- notes
- created_at

Suggested correction labels:

- important
- needs_reply
- personal
- client_work
- job_alert
- newsletter
- receipt
- system_notice
- marketing
- noise
- ignore

- [x] Use dropdowns or buttons rather than relying on free text only.

### 4. Corrections must affect current message immediately

When the user corrects a message:

- [x] Persist structured feedback.
- [x] Update the message classification fields where appropriate.
- [x] Recalculate the attention score.
- [x] Update the reason and recommended action.
- [x] Important should boost the item.
- [x] Needs reply should set `requires_reply` and recommended action to `Reply`.
- [x] Newsletter/noise/ignore should lower or dismiss the item.
- [x] Job alert should be low priority unless the sender/contact is VIP or the user marks it important.
- [x] Receipt/system notice should generally stay lower priority unless important or requires reply.

### 5. Improve deterministic classification examples

Add or improve rules so:

- [x] LinkedIn/Google-style job alerts are not treated as client work by default.
- [x] Newsletters with unsubscribe/list headers are low priority unless VIP or corrected important.
- [x] Renewal reminders, insurance, invoices, taxes, bills, expiry dates, due dates, and payment deadlines get an importance boost.
- [x] ICBC-style insurance renewal reminders can become high priority when marked important or when sender is VIP.

### 6. Contact status actions

- [x] VIP should recalculate existing sender messages upward.
- [x] Noise should recalculate or dismiss existing sender messages downward.
- [x] Add a normal/reset contact status action if straightforward.

### 7. Tests

Add or update tests for:

- [x] Correcting a message as important increases score.
- [x] Correcting a message as needs reply sets `requires_reply` and recommended action.
- [x] Correcting a message as newsletter/noise lowers or dismisses it.
- [x] Job alert classification is not client work by default.
- [x] Insurance/renewal reminders receive a priority boost.
- [x] VIP recalculation works.
- [x] Noise recalculation works.
- [x] Dashboard route loads.
- [x] Message detail route loads.
- [x] Structured feedback persists.

## Completion notes

Completed on 2026-05-15. Structured corrections are implemented through `app/services/feedback_service.py` and shared by web/API routes. `alembic/versions/0002_structured_feedback.py` adds the feedback fields. Tests pass with 25 tests and 2 existing FastAPI `on_event` deprecation warnings.

## Out of scope

- Outlook connector.
- Teams connector.
- Additional notification sources.
- AI-generated replies.
- Sending, archiving, deleting, or modifying external messages.
- Production deployment.

## Documentation updates required

At completion, update:

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- This phase file with completion notes

## Acceptance criteria

- `pytest -q` passes.
- App starts with `uvicorn app.main:app --reload`.
- Dashboard is substantially more readable.
- Attention Queue is understandable without reading raw internal reasons.
- Correcting a message updates its classification and score immediately.
- Job alerts/newsletters are not over-promoted as client work by default.
- Important renewal/insurance reminders can be promoted correctly.
- No send/archive/delete behavior is introduced.
