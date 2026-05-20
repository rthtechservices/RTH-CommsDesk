# RTH CommsDesk Endgame Roadmap

## Current position

Phase 27 is in progress and is expected to clean up the smoke-test friction from Phase 26: platform-aware drafts, draft lifecycle controls, execution filtering, Voice/Assistant repairs, complete local backup contents, and navigation/dashboard cleanup.

After Phase 27, the project should stop behaving like an endless phase train and move into three large remaining sprints.

## End goal

RTH CommsDesk should be a local-first daily communications console:

1. sync Gmail and Outlook read surfaces;
2. show one practical operator queue;
3. recommend the next useful action;
4. prepare drafts, calendar actions, cleanup actions, or local review outcomes;
5. require approval and final confirmation before external changes;
6. execute through the correct provider;
7. audit every attempt;
8. provide backup, recovery, and reauth guidance.

## Remaining phases

| Phase | Name | Purpose |
| --- | --- | --- |
| 28 | Daily-Use Cutover and Operator Console | Consolidate the dashboard into the real morning workflow: readiness, sync, process-next, queue counts, local review actions, and live smoke harness. |
| 29 | Outlook Draft Write and Cross-Provider Parity | Add safe Outlook draft creation only, behind flags and approval. Keep Outlook send/calendar/Teams write disabled. |
| 30 | Release Candidate and Production Readiness | Freeze scope, harden startup/backup/restore/reauth, clean docs/UI, validate route smoke, and prepare first daily-use release candidate. |

## What not to do before release candidate

- Do not add Teams.
- Do not add Outlook send.
- Do not add Outlook calendar write.
- Do not add broad analytics dashboards.
- Do not create cosmetic-only phases.
- Do not expand the test matrix beyond focused regression coverage.

## Success state

The app is release-candidate ready when Rohan can open the dashboard, sync current mail, process the next important item, prepare/review/approve an action, execute it safely when needed, and recover/audit what happened without digging through raw routes or logs.
