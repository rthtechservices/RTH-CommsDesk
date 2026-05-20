# Phase 28 — Daily-Use Cutover, Operator Console, and About Statistics

## Goal

Make RTH CommsDesk usable as the daily morning command center. Phase 28 should consolidate the existing capabilities into one fast operator workflow instead of adding more side screens.

Also add an application-style About screen with basic app information and persistent life-to-date productivity statistics.

## Target flow

```text
Open dashboard
→ check provider readiness
→ sync current mail
→ process next useful item
→ review recommendation and context
→ approve, dismiss, defer, or prepare action
→ execute only after confirmation when an external provider is changed
→ audit result
→ repeat
```

## Scope

Build one strong operator lane:

- unified queue across Gmail, Outlook read items, review packages, drafts, executions, calendar candidates, and cleanup candidates;
- `Process next` action that selects the highest-value actionable item;
- local actions for reviewed, important, noise, dismiss, and defer/snooze;
- prepare actions for draft reply, calendar candidate, and cleanup candidate;
- dashboard readiness panel that shows provider health, sync age, queue counts, pending executions, failed/blocked items, and last backup;
- one-click live smoke harness for safe provider status, route status, and write-readiness posture;
- startup/check script for the known local Windows paths;
- backup verification and restore guidance;
- stale-token/reauth guidance for Gmail, Google Calendar, and Microsoft Graph.

## About screen

Add a top-level About page, similar to an About dialog under the Help menu of a desktop application.

Suggested route and nav label:

```text
/about
About
```

The About page should show basic application information:

- app name;
- short product description;
- local environment/runtime mode;
- app version/build identifier if available;
- database path/status, redacted as needed;
- current provider summary;
- documentation/runbook links;
- current release/phase marker if available.

## Life-to-date statistics

The About page must also show persisted life-to-date statistics. These stats should survive future version upgrades because they are stored in the SQLite database, not derived only from transient UI state.

Required stats:

- Number of Emails Processed;
- Number of Emails Drafted;
- Number of Emails Deleted;
- Number of Senders Identified as Spam/Noise;
- Number of VIP Contacts;
- Number of AI-Provided Content Items;
- Number of Hours Saved.

Use existing database/audit records where possible. If a stat is not yet fully measurable, show `Not enough data yet` or `Tracking from <start timestamp>` rather than inventing values.

## Statistics persistence model

Add a durable stats/baseline model if one does not already exist.

Minimum fields/concepts:

- stat key;
- stat value;
- first tracked timestamp;
- last recalculated timestamp;
- source table/query or calculation notes;
- app/stat version.

Create a clear go-live baseline timestamp. Stats must begin from the selected go-live point and continue across future migrations.

Add an Admin/About control or documented configuration value to set/freeze the go-live baseline once:

```env
APP_STATS_GO_LIVE_AT=<ISO timestamp or blank until initialized>
```

Do not silently reset life-to-date stats during backup/restore, migrations, or app upgrades.

## Hours saved algorithm

Implement a transparent, configurable estimate. Do not pretend it is exact.

Create a small service such as `productivity_stats_service.py` that calculates time saved from audited app activity.

Use configurable default assumptions, for example:

```text
manual_review_seconds_per_email = 12
manual_bulk_cleanup_setup_seconds = 45
manual_bulk_cleanup_seconds_per_email = 3
manual_browser_open_thread_seconds = 8
reading_words_per_minute = 225
typing_words_per_minute = 40
manual_send_overhead_seconds = 20
ai_review_overhead_seconds = 10
```

Suggested calculation categories:

1. Mark reviewed / local process actions
   - Estimate time saved versus opening an email in Gmail/Outlook, glancing at it, and manually marking/clearing it.

2. Bulk triage / cleanup
   - Estimate time saved versus manually searching a sender/domain, selecting matching messages, and applying archive/delete/label actions.
   - Use actual affected message count from execution audit where available.

3. Draft generation / draft execution
   - Estimate manual reading time from source/thread word count.
   - Estimate manual typing time from generated draft word count.
   - Add basic browser/thread/send overhead.
   - Subtract AI/operator review overhead so the number is not nonsense-candy.

4. AI-provided content
   - Count summaries, draft suggestions, recommendation packages, and other AI-generated content records where the database has durable evidence.

Display:

```text
Estimated Hours Saved: X.X
Method: configurable estimate based on reviewed items, cleanup actions, draft word counts, and audited execution data.
```

Include an expandable explanation of the formula and assumptions on the About page.

## Safety requirements

Keep the existing external-action lane:

```text
prepare → approve → final confirmation → execute → audit
```

Do not enable new external-write capability by default. Outlook send, Outlook calendar write, and Teams write stay parked.

The About/statistics feature must be read-only except for an explicit admin/go-live baseline initialization action. It must not mutate Gmail, Outlook, Calendar, or provider data.

## Acceptance criteria

- Dashboard has a single practical operator flow.
- `Process next` works from the dashboard.
- Queue counts are visible and useful.
- Provider readiness is explicit.
- Pending/failed/blocked work is easy to find.
- Local dismiss/defer/review actions do not touch external providers.
- External actions remain gated and audited.
- Startup/check script works on the known local paths or gives clear guidance.
- Backup/restore guidance is visible from Admin or Help.
- `/about` returns HTML 200.
- About page shows app info and life-to-date stats.
- Hours Saved uses a transparent configurable estimate.
- Life-to-date stats persist in SQLite and are not reset by app restart.
- Go-live baseline can be initialized and is documented.
- Focused tests pass.

## Required validation

```powershell
python -m ruff check .
python -m pytest -q
python -m alembic upgrade head
```

Run route smoke for the dashboard, drafts, review packages, executions, bulk triage, assistant, voice, providers, smoke, admin, about, and health routes.
