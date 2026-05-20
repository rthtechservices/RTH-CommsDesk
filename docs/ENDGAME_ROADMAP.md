# RTH CommsDesk Endgame Roadmap

## Current position

Phase 27 is complete or in final smoke review. It should have cleaned up the Phase 26 friction: platform-aware drafts, draft lifecycle controls, execution filtering, Voice/Assistant repairs, complete local backup contents, and navigation/dashboard cleanup.

The project now moves into three large remaining sprints. No more endless phase train.

## End goal

RTH CommsDesk should be a local-first daily communications console:

1. sync Gmail and Outlook read surfaces;
2. show one practical operator queue;
3. recommend the next useful action;
4. prepare drafts, calendar actions, cleanup actions, or local review outcomes;
5. require approval and final confirmation before external changes;
6. execute through the correct provider;
7. audit every attempt;
8. provide backup, recovery, and reauth guidance;
9. show persistent life-to-date value metrics from the go-live baseline onward.

## Remaining phases

| Phase | Name | Purpose |
| --- | --- | --- |
| 28 | Daily-Use Cutover, Operator Console, and About Statistics | Consolidate the dashboard into the real morning workflow and add an About screen with persistent life-to-date statistics and estimated hours saved. |
| 29 | Outlook Draft Write and Cross-Provider Parity | Add safe Outlook draft creation only, behind flags and approval. Keep Outlook send/calendar/Teams write disabled. |
| 30 | Release Candidate and Production Readiness | Freeze scope, harden startup/backup/restore/reauth, clean docs/UI, validate route smoke, and prepare first daily-use release candidate. |

## About/statistics requirement

The release candidate should include `/about`, similar to a desktop app About screen. It should show basic app information plus life-to-date statistics from a durable SQLite baseline:

- Number of Emails Processed;
- Number of Emails Drafted;
- Number of Emails Deleted;
- Number of Senders Identified as Spam/Noise;
- Number of VIP Contacts;
- Number of AI-Provided Content Items;
- Number of Hours Saved.

The Hours Saved value must be a transparent configurable estimate, not magic confetti. Use audited activity, affected message counts, source/draft word counts where available, and configurable reading/typing/browser-overhead assumptions. Show the formula assumptions on the About page.

Stats must persist across future upgrades and begin from the go-live baseline timestamp.

## What not to do before release candidate

- Do not add Teams.
- Do not add Outlook send.
- Do not add Outlook calendar write.
- Do not add broad analytics dashboards.
- Do not create cosmetic-only phases.
- Do not expand the test matrix beyond focused regression coverage.

## Success state

The app is release-candidate ready when Rohan can open the dashboard, sync current mail, process the next important item, prepare/review/approve an action, execute it safely when needed, recover/audit what happened, and see persistent lifetime value metrics without digging through raw routes or logs.
