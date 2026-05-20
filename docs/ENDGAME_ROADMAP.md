# RTH CommsDesk Endgame Roadmap

## Current position

Phase 28 is complete or in final smoke review. It added the `/about` life-to-date statistics page: persistent `app_stat_records` SQLite table, configurable transparent hours-saved estimate, go-live baseline support, and all-route navigation smoke coverage.

The project now moves into two large remaining sprints before release candidate. No more endless phase train.

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
| 29 | Microsoft Write Cutover and Provider Parity | Add real Microsoft Graph write parity for Outlook drafts, Outlook send, Outlook calendar, and mail modify seams behind explicit flags and the existing approval/confirmation/audit pipeline. |
| 30 | Release Candidate and Production Readiness | Freeze scope, harden startup/backup/restore/reauth, clean docs/UI, validate route smoke, and prepare first daily-use release candidate. |

## Phase 29 stance

Phase 29 is no longer a cautious Outlook-draft-only phase. It is the Microsoft write cutover sprint.

Ship the real seams now:

- Outlook draft creation;
- Outlook send;
- Outlook reply/send in the correct conversation where identifiers allow it;
- Outlook mail modify/category/archive or a clear blocked seam if Graph/data support is incomplete;
- Outlook calendar event creation;
- provider-aware routing so Microsoft-originated work never falls back to Gmail.

The approval/confirmation/audit lane remains because that is the app architecture, not a delay tactic.

## About/statistics requirement

The release candidate should include `/about`, similar to a desktop app About screen. It should show basic app information plus life-to-date statistics from a durable SQLite baseline:

- Number of Emails Processed;
- Number of Emails Drafted;
- Number of Emails Deleted;
- Number of Senders Identified as Spam/Noise;
- Number of VIP Contacts;
- Number of AI-Provided Content Items;
- Number of Hours Saved.

The Hours Saved value must be a transparent configurable estimate. Use audited activity, affected message counts, source/draft word counts where available, and configurable reading/typing/browser-overhead assumptions. Show the formula assumptions on the About page.

Stats must persist across future upgrades and begin from the go-live baseline timestamp.

## What not to do before release candidate

- Do not add Teams unless it is effectively free and does not delay Microsoft mail/calendar write parity.
- Do not add broad analytics dashboards.
- Do not create cosmetic-only phases.
- Do not expand the test matrix beyond focused regression coverage.

## Success state

The app is release-candidate ready when Rohan can open the dashboard, sync current mail, process the next important item, prepare/review/approve an action, execute it safely when needed across Gmail, Google Calendar, and Microsoft Graph where configured, recover/audit what happened, and see persistent lifetime value metrics without digging through raw routes or logs.
