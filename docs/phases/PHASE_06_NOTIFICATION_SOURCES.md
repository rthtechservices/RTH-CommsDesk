# Phase 06 — AI Summarization and Proposed Action Intelligence

## Objective

Start producing real intelligence from communication context. The app should summarize conversations, identify whether a response is actually needed, recommend the next action, and create a local review package.

This phase exists because generic draft text is not useful. If the app sees only "No worries, thanks for the heads up" inside a larger cancelled-dinner thread, it should understand the thread and recommend no response, not produce a vague acknowledgement.

## Required implementation

- Add a provider-neutral AI analysis service with a mock provider for tests.
- Keep a local deterministic/mock path so development and tests do not require paid AI credentials.
- Analyze full conversation context from Phase 05.
- Generate a concise conversation summary.
- Determine whether a response is needed.
- Recommend one or more proposed action types:
  - no_response_needed
  - reply
  - schedule_meeting
  - ask_clarifying_question
  - mark_noise
  - unsubscribe_review
  - create_calendar_reminder
  - follow_up_later
  - archive_candidate
  - delete_candidate
- Store proposed actions/review packages locally.
- Include reason/explanation, confidence, source message/thread, and created/updated timestamps.
- Improve draft generation so drafts are based on:
  - full thread context
  - conversation summary
  - sender/contact relationship
  - action type
  - importance score
  - user correction history
- Add a review package UI showing:
  - communication summary
  - recommendation
  - why the action was recommended
  - draft response if applicable
  - confidence level
  - local approve/reject/edit/snooze status
- Add tests for realistic cases:
  - dinner cancellation acknowledgement should produce no_response_needed
  - renewal reminder should produce create_calendar_reminder candidate
  - obvious newsletter should produce mark_noise or unsubscribe_review candidate
  - client request should produce reply candidate
  - vague message should produce ask_clarifying_question or review_needed

## Product behavior examples

### Dinner cancellation acknowledgement

Thread:

- Christian cancels dinner.
- Michael replies, "No worries, thanks for the heads up! ❤️"

Expected result:

- Summary: Michael acknowledged Christian's cancellation.
- Recommended action: no_response_needed.
- Explanation: the message is an acknowledgement and does not ask Rohan for anything.
- No draft should be generated unless the user explicitly forces one.

### ICBC renewal

Message:

- Registration is due on a detected date.

Expected result:

- Summary includes the due date.
- Recommended action: create_calendar_reminder.
- Explanation says the reminder should be scheduled before the due date.
- Calendar execution remains local/proposed only until a later phase.

### Never-opened marketing sender

Pattern:

- Repeated sender, low engagement, marketing/newsletter language.

Expected result:

- Recommended action: unsubscribe_review or mark_noise.
- Explanation includes the evidence available locally.

## Out of scope

- Actually sending email.
- Actually creating Gmail drafts externally.
- Actually deleting, archiving, labeling, unsubscribing, or creating calendar events externally.
- Sent-mail style learning; that belongs in Phase 07.
- New connectors.

## Documentation updates required

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- This phase file with completion notes

## Acceptance criteria

- `pytest -q` passes.
- AI analysis works with a mock provider.
- Conversation summaries are stored and visible.
- Proposed actions/review packages are stored and visible.
- The dinner-cancellation acknowledgement scenario recommends no_response_needed.
- Draft generation uses conversation summary and action type.
- Review packages are clearly local and do not modify external systems.
