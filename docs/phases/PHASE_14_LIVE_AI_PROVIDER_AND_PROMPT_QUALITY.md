# Phase 14 — Live AI Provider Integration and Prompt Quality

## Objective

Move from deterministic/mock analysis to a real provider-neutral AI path that can generate useful summaries, recommendations, and drafts from full conversation context while retaining a mock provider for tests and local fallback.

The goal is not to make the app magical; it is to make the outputs specific, grounded, and reviewable.

## Required implementation

- Add a real AI provider implementation behind the existing provider-neutral analysis/draft interfaces.
- Support configuration through environment variables without hard-coding secrets.
- Keep `mock` as the default safe local provider.
- Add provider selection diagnostics to the UI so the user can tell whether mock or live AI is being used.
- Build prompt templates that include:
  - full conversation timeline
  - selected message
  - sender/recipient roles
  - contact relationship
  - approved voice guidance
  - recent user corrections
  - known proposed action types
  - strict instruction to avoid generic filler
- Require structured AI output, such as JSON, with fields for summary, action type, explanation, confidence, draft body, detected dates, and caveats.
- Validate and sanitize AI output before storing it.
- Add fallback behavior when the AI provider fails or returns invalid output.
- Add regression tests around prompt construction, output parsing, provider fallback, and examples from real smoke tests.
- Add a small prompt-quality evaluation fixture set with expected outputs.

## Product behavior examples

### Friend acknowledgement

A friend acknowledges a cancellation inside a thread. Expected result: no response needed, with no forced draft.

### Client request

A client asks for help with a specific issue. Expected result: concise summary, reply recommendation, and a draft that mentions the actual request.

### Renewal reminder

A service provider gives a due date. Expected result: reminder recommendation with detected date and proposed lead time.

## Out of scope

- External send/calendar execution changes.
- New connectors.
- Large-scale vector search or embeddings unless required for prompt quality.

## Documentation updates required

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `.env.example`
- This phase file with completion notes

## Acceptance criteria

- `python -m ruff check .` passes.
- `python -m pytest -q` passes.
- Mock provider remains the default.
- Live provider can be enabled through configuration.
- AI output is structured, validated, and safely stored.
- The UI indicates which provider generated a review package or draft.
- The core smoke-test examples produce specific, non-generic outputs.
