# Phase 21 — Voice Memory and Assistant Personalization Console

## Objective

Turn voice learning from hidden inference into a visible, editable assistant-personalization system.

Phase 20 should improve the intelligence layer and teach CommsDesk to infer durable writing traits. Phase 21 should make those traits inspectable and governable so the operator can see why the assistant sounds a certain way and correct it without editing code or prompts.

## Product intent

CommsDesk should become recognizably the operator's assistant, not a generic AI wrapper. The operator should be able to review and control:

- preferred sign-off
- tone and brevity preferences
- avoided phrases
- professional/informal consistency
- relationship-specific overrides
- evidence that caused a trait to be inferred

## Scope

### Assistant Profile / Voice Memory page

Add a page for global and contact/relationship-specific voice memory.

Show:

- approved global writing traits
- pending inferred writing traits
- preferred sign-off / signature
- tone notes
- greeting/salutation tendencies
- phrases to avoid
- relationship-specific overrides
- evidence counts and limited safe excerpts
- last refreshed date

### Trait lifecycle

Support:

- approve
- reject
- edit
- disable temporarily
- reset to default

Keep changes auditable where practical.

### Draft preview

Add a small preview tool:

- Select or enter a sample context.
- Generate a draft preview using current voice memory.
- Show which traits influenced the result.
- Do not create external Gmail drafts from this preview.

### Privacy and safety

- Do not expose full sent-mail bodies unless explicitly opened from a detail view that already exists.
- Prefer small evidence snippets and counts.
- Do not auto-approve inferred voice traits.
- Do not bypass Phase 19 execution controls.

## Out of scope

- Outlook send.
- Outlook calendar.
- Teams.
- Vector memory/search.
- Direct `.env` editing.
- Auto-send or auto-execution.

## Acceptance criteria

- Assistant Profile / Voice Memory page exists and is linked from the dashboard/nav.
- Global writing traits can be reviewed, approved, edited, rejected, and disabled.
- Preferred sign-off/signature can be inspected and edited.
- Draft generation uses approved traits only.
- Draft preview shows trait influence without creating external drafts.
- Tests cover trait lifecycle, preview behavior, and draft use of approved traits.
- Existing Phase 19 test execution gating remains intact.

## Documentation updates required

Update:

- `README.md` if needed
- `docs/HELP.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_STATUS.md`
- this phase file
