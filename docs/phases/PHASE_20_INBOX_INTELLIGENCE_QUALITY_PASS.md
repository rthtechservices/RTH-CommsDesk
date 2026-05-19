# Phase 20 — Inbox Intelligence Quality Pass

## Objective

Improve the usefulness and trustworthiness of AI and rules-based recommendations after the core workflow has been proven operational.

This phase should tune CommsDesk using real or realistic test-email scenarios, not theoretical prompt polishing.

## Product intent

The app should consistently answer:

- Does this message need attention?
- Is a reply owed?
- What is the next action?
- Is this noise?
- Is a calendar action needed?
- Is the proposed draft usable after quick review?

## Scope

### Test scenario fixtures

Add reusable fixture conversations for the most important product cases:

- Client asks for action.
- Friendly update where no reply is needed.
- Scheduling request with clear time options.
- Scheduling request with missing or ambiguous time details.
- Renewal, invoice, tax, or deadline reminder.
- Newsletter, marketing, or noise.
- Vague actionable message such as "can you look at this?".
- Thread where the latest message changes the required action.

### Review package correction loop

Improve correction capture directly on review packages:

- Correct action type.
- This does or does not need reply.
- Better summary.
- Better draft instruction.
- Mark as noise or not noise.

Corrections should be structured enough to feed future scoring and prompt context.

### Prompt and rule tuning

- Improve analysis prompt inputs using actual failure patterns.
- Keep output structured and validated.
- Preserve mock fallback behavior.
- Avoid generic filler in summaries, explanations, and drafts.
- Use full conversation timeline where available.
- Use contact relationship and approved voice guidance where available.

### Quality display

In review package detail, make the recommendation understandable without reading internal classifier text:

- Plain-language reason.
- Action confidence.
- Evidence behind the recommendation.
- What would happen if executed.
- Correction controls near the recommendation.

## Out of scope

- New live AI provider work.
- Vector search.
- Outlook send, Outlook calendar, or Teams expansion.
- Fully automated execution.
- Production analytics dashboard.

## Acceptance criteria

Automated validation must pass:

```powershell
python -m ruff check .
python -m pytest -q
python -m alembic upgrade head
```

Quality checks:

- Add or update tests for all key fixture scenarios.
- Fixture expected outcomes should cover action type, reply/no-reply, noise/not-noise, reminder/scheduling detection, and draft/no-draft behavior.
- Live AI failures must still fall back to mock behavior.
- Corrections must persist and affect later local scoring or prompt context where implemented.
- Review package detail must show operator-friendly recommendation evidence and correction controls.

## Documentation updates required

Update:

- `README.md`
- `docs/HELP.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_STATUS.md`
- this phase file

## Codex notes

Do not chase perfect AI output in isolation. Tune against concrete examples and keep every recommendation explainable and correctable by the operator.
