# Phase 20 — Assistant Intelligence, Voice, and Calendar Reasoning Quality

## Objective

Make CommsDesk behave more like the operator's assistant by improving recommendation quality, personal writing style, and calendar reasoning after the operational workflow and test-execution lane have been proven.

Phase 19 proved that controlled Gmail draft execution and calendar execution paths can be gated by operational test mode and allowlisted recipients. Phase 20 should now fix the quality issues exposed by live smoke testing:

- Drafts must stop using generic placeholders such as `[Your Name]`.
- Drafts should learn and apply the operator's natural sign-off from sent mail, especially `Cheers, Rohan.` when the evidence supports it.
- Scheduling intelligence must not create reminders or events in the past.
- A meeting request with no time should not invent a timed event. It should prefer a clarifying reply or, if appropriate, an all-day tentative calendar candidate.
- Review packages must show evidence and correction controls so bad recommendations are teachable.

## Product intent

The app should consistently answer:

- Does this message need attention?
- Is a reply owed?
- What is the next action?
- Is this noise?
- Is a calendar action needed?
- Is there enough detail to create a calendar event, or should the assistant ask a clarifying question?
- Is the proposed draft written in the operator's voice?

## Scope

### Assistant identity and voice learning

Improve the sent-mail learning and draft-generation loop so the assistant can organically learn stable writing traits from the operator's sent mail.

Focus areas:

- Detect common sign-offs/signatures from sent mail.
- Store/approve reusable voice traits where the existing voice calibration model supports it, or add a minimal durable structure if needed.
- Apply approved sender-level or global operator voice guidance to draft generation.
- Prevent generic placeholders such as `[Your Name]`, `[Your signature]`, or fake formal closings from appearing in send-ready drafts.
- Preserve contact-specific guidance where it already exists, but allow stable global traits to apply across professional and informal contexts.

Expected behavior after sufficient sent-mail learning:

```text
Cheers,
Rohan.
```

should be a preferred closing when the learned/approved evidence supports it.

### Calendar and scheduling reasoning

Improve scheduling recommendations so date/time behavior is sensible.

Rules:

- Never propose a reminder/event in the past unless explicitly reviewing historical records.
- Interpret relative dates such as "this coming Friday" relative to the message received date and current operator date.
- If a meeting request contains a date but no time, do not invent a timed meeting.
- Prefer `ask_clarifying_question` when the time is missing and a response is needed.
- If a date-only calendar candidate is still useful, represent it as an all-day tentative candidate, not a timed reminder.
- If a clear time exists, create a timed event candidate with timezone-safe start/end values.
- Distinguish reminders from meetings. A request to chat/meet should not become a reminder by default.

### Test scenario fixtures

Add reusable fixture conversations for the most important product cases:

- Client asks for action.
- Friendly update where no reply is needed.
- Scheduling request with clear date and time.
- Scheduling request with date but no time.
- Scheduling request using relative date text such as "this coming Friday".
- Renewal, invoice, tax, insurance, or deadline reminder.
- Newsletter, marketing, or noise.
- Vague actionable message such as "can you look at this?".
- Thread where the latest message changes the required action.
- Sent-mail examples that demonstrate the operator's recurring closing/signature style.

### Review package correction loop

Improve correction capture directly on review packages:

- Correct action type.
- This does or does not need reply.
- Better summary.
- Better draft instruction.
- Correct calendar interpretation.
- Mark as noise or not noise.
- Optional note explaining the correction.

Corrections should be structured enough to feed future scoring and prompt context.

### Prompt and rule tuning

- Improve analysis prompt inputs using actual failure patterns.
- Keep output structured and validated.
- Preserve mock fallback behavior.
- Avoid generic filler in summaries, explanations, and drafts.
- Use full conversation timeline where available.
- Use contact relationship and approved voice guidance where available.
- Use recent structured corrections.
- Treat live AI output as untrusted and sanitize it before storage/execution.

### Quality display

In review package detail, make the recommendation understandable without reading internal classifier text:

- Plain-language reason.
- Action confidence.
- Evidence behind the recommendation.
- Calendar interpretation evidence where relevant.
- What would happen if executed/prepared.
- Current correction state if corrected.
- Correction controls near the recommendation.

## Out of scope

- New live AI provider work.
- Vector search.
- Outlook send, Outlook calendar, or Teams expansion.
- Fully automated execution.
- Production analytics dashboard.
- Direct `.env` editing from the UI.
- Any relaxation of Phase 19 operational test-mode or allowlist enforcement.

## Acceptance criteria

Automated validation must pass:

```powershell
python -m ruff check .
python -m pytest -q
python -m alembic upgrade head
```

Quality checks:

- Add or update tests for all key fixture scenarios.
- Fixture expected outcomes should cover action type, reply/no-reply, noise/not-noise, reminder/scheduling detection, draft/no-draft behavior, and calendar date/time correctness.
- Calendar candidates must not be generated in the past.
- Date-only meeting requests should become clarification or all-day tentative candidates, not invented timed reminders.
- Drafts must not contain `[Your Name]`, `[Your signature]`, internal review notes, duplicated `Subject:` lines, or AI boilerplate.
- Sent-mail learning should be able to infer and apply recurring approved signature/sign-off traits.
- Live AI failures must still fall back to mock behavior.
- Corrections must persist and affect later local scoring or prompt context where implemented.
- Review package detail must show operator-friendly recommendation evidence and correction controls.
- Phase 19 allowlist/test-execution enforcement must still pass.

## Documentation updates required

Update:

- `README.md` if needed
- `docs/HELP.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_STATUS.md`
- this phase file

## Codex notes

Do not chase perfect AI output in isolation. Tune against concrete examples and keep every recommendation explainable, correctable, and safely gated. The goal is the first visible step toward CommsDesk becoming the operator's assistant rather than a generic AI wrapper.

## Completion notes — 2026-05-19

Status: Completed for human review.

Implemented:

- Added/expanded recommendation-quality fixtures for client action, friendly no-reply, clear scheduling, date-only scheduling, relative Friday scheduling, renewal/tax/deadline reminders, newsletter/noise, vague actionable asks, latest-message-changes-action, and sent-mail sign-off examples.
- Improved sent-mail voice inference so repeated closings can become pending global operator guidance; approved global guidance can apply across contacts when no contact-specific guidance overrides it.
- Added draft cleanup for generic placeholders and applied approved preferred sign-off guidance to send-ready local drafts.
- Tightened calendar reasoning so past dates are not prepared, date-only meeting requests become clarifying replies with all-day tentative candidates, and clear date/time candidates stay timezone-safe.
- Added structured review-package corrections through `UserFeedback` and surfaced evidence, correction state, calendar interpretation evidence, and correction controls on review package detail.
- Preserved Phase 19 execution policy, allowlist enforcement, dry-run defaults, and disabled Microsoft write boundaries.

Validation:

- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 223 tests.
- `python -m alembic upgrade head` — passed.
- Route smoke returned HTTP 200 for `/`, `/operational-smoke`, `/providers`, `/review-packages`, `/executions`, `/bulk-triage`, `/contacts`, `/drafts`, `/voice-calibration`, `/admin`, and `/healthz`.

Human review notes:

- No new outbound execution behavior was added.
- Date-only calendar candidates use the existing calendar proposal model as all-day tentative review candidates.
- Phase 21 should make approved global voice/sign-off memory more visible and editable in a dedicated Assistant Profile console.
