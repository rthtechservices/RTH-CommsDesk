# Phase 18.7 — Interaction Hierarchy, Triage Ergonomics & RTH Palette Alignment

## Objective

A UI/UX-only pass to improve information hierarchy, visual clarity, and ergonomics across all pages. No new execution behavior. No new backend services. No schema changes. No outbound actions.

**Scope constraint**: This phase is purely cosmetic and layout-focused. All Phase 19 execution behaviors (Gmail send, approval workflow execution) remain off-limits.

---

## Changes Made

### `app/web/ui.css` — Full RTH/TaskDesk palette overhaul

- Replaced old ad-hoc color variables with full RTH palette:
  - `--blue: #3B82F6`, `--sky: #0EA5E9`, `--cyan: #38BDF8`, `--teal: #14B8A6`, `--green: #10B981`
  - `--amber: #F59E0B`, `--orange: #F97316`, `--red: #E11D48`, `--pink: #EC4899`, `--purple: #A855F7`, `--indigo: #6366F1`
- Added semantic tokens: `--ok`, `--warn`, `--bad`, `--info`, `--ai`, `--calendar`
- Darkened background to `--bg: #11161D`
- Workflow rail: `.done` = subtle green tint (past stage), `.active` = amber glow (current/pending stage)
- Source badge classes: `.badge.src-gmail` (cyan), `.badge.src-outlook` (blue), `.badge.src-notification` (purple)
- Action badge classes: `.badge.act-reply` (amber), `.badge.act-schedule` (teal), `.badge.act-review` (purple), `.badge.act-noise` (indigo)
- NBA strip: `.nba-strip` (amber), `.nba-strip.nba-blocker` (red), `.nba-strip.nba-clear` (green)
- Score tier classes: `.score-urgent` (red), `.score-high` (amber), `.score-medium` (cyan), `.score-low` (muted)
- Attention row accent borders: `.attention-row.urgent`, `.attention-row.high`, `.attention-row.medium`
- Callout cards: `.callout`, `.callout-amber`, `.callout-red`, `.callout-green`, `.callout-grey`
- Widget accent classes: `.widget-header`, `.widget-priority`, `.widget-ai`, `.widget-muted`, `.widget-empty`
- Button variants: `.button.amber` (pending/review work), `.button.outline` (secondary/muted)

### `app/web/routes.py` — `_compute_next_best_action()`

- Added helper function returning `{ tier, message, primary_label, primary_url, secondary: [...] }`
- Priority tiers: `blocker` → `pending` (review packages) → `triage` (unreviewed attention) → `clear`
- Dashboard context now passes `next_best_action` to the template

### `app/web/templates/dashboard.html` — Full rewrite

- Workflow rail: Sync=done, Triage=active
- NBA strip at top, tier-based CSS class and button color
- Status grid (3 columns, rebalanced): Operational Status | Command Center | Sources
- Command Center numbers colored amber (non-zero) or green (zero) using `.cc-number`
- Attention table: score tier classes, source badge classes, action badge classes
- Row action hierarchy: Open=primary, Important=amber, Reviewed=outline
- Widget sidebar: Proposed Actions=purple accent (`.widget-priority.widget-ai`), Ready For Approval=amber accent (`.widget-priority`)

### Workflow rail updates (7 templates)

| Template | Workflow state |
|---|---|
| `message_detail.html` | Sync done, Triage done, Analyze active |
| `review_packages.html` | Sync done, Triage done, Analyze done, Review active |
| `review_package_detail.html` | Sync done, Triage done, Analyze done, Review active |
| `executions.html` | All prior stages done, Execute active |
| `execution_detail.html` | All prior stages done, Execute+Audit active |
| `providers.html` | Audit active |
| `operational_smoke.html` | Audit active |

### `providers.html` — Polished with callout cards

- Replaced `<p class="notice">` with `.callout.callout-grey` for Microsoft boundary blocks
- Provider badge states: ok/amber/grey/bad (replaced warn→amber, added grey for disabled/not_implemented)
- Added individual callout cards for each Microsoft boundary (Outlook send, calendar, Teams)
- Added "This page observes configuration only" note as explicit muted text

### `operational_smoke.html` — Polished with callout cards

- Blockers section now displayed prominently at the top with `.callout-red` if present, `.callout-green` if clear
- Dry-run state section uses semantic amber/green badges
- Disabled Microsoft write boundaries now shown as individual `.callout-grey` cards

### `executions.html` — Polished

- Status badges now use semantic color classes: `ok` executed, `bad` cancelled/failed, `amber` approved/pending_confirmation, `info` pending_approval, `grey` default
- Empty state row uses `.empty` class with helpful guidance text

### `review_packages.html` — Polished

- Replaced `<p class="notice">` with `.callout.callout-amber` for the "local recommendations only" notice
- Status badges use proper color tiers: `ok` approved, `bad` rejected, `amber` pending, `grey` default
- Empty state uses `.empty` class with explicit guidance

---

## Design Rationale

### Workflow stage semantics (amber = pending work, not celebration)

Old design used green for the active/current stage. This was misleading: a highlighted "Triage" stage means triage work is pending — it should draw attention, not signal success.

New design:
- `.done` = subtle green tint (past stage, work completed)
- `.active` = amber glow (current stage = work is here right now)

### Pending counts should not look like success

Old design rendered attention queue counts in the same muted color whether the count was 0 or 50. New design:
- Non-zero pending counts → amber (`.cc-pending`)
- Zero counts → green (`.cc-ok`)
- Informational counts → cyan (`.cc-info`)

### Source and action visual identity

Each source (Gmail=cyan, Outlook=blue, Notification=purple) and recommended action (reply=amber, schedule=teal, noise=indigo, review=purple) now has a consistent color identity that persists across the attention table, widgets, and wherever badges appear.

---

## Acceptance Criteria

- [ ] All routes return 200 (ruff and pytest pass)
- [ ] Dashboard shows NBA strip with correct tier class based on live backlog stats
- [ ] Dashboard score cells use tier-colored classes (urgent/high/medium/low)
- [ ] Dashboard source badges use `.badge.src-*` classes
- [ ] Dashboard recommended action badges use `.badge.act-*` classes
- [ ] Dashboard action hierarchy: Open=primary, Important=amber, Reviewed=outline
- [ ] `review_packages.html` renders the callout-amber notice
- [ ] `providers.html` renders Microsoft boundary callout-grey cards
- [ ] `operational_smoke.html` shows callout-red if blockers, callout-green if clear
- [ ] Workflow stages correctly indicate done/active on all 7 updated templates
- [ ] Existing test strings from `test_phase_18_6_visual_design.py` still pass
- [ ] `python -m ruff check .` passes
- [ ] `python -m pytest -q` passes

---

## Files Changed

- `app/web/ui.css`
- `app/web/routes.py`
- `app/web/templates/dashboard.html`
- `app/web/templates/message_detail.html`
- `app/web/templates/review_packages.html`
- `app/web/templates/review_package_detail.html`
- `app/web/templates/executions.html`
- `app/web/templates/execution_detail.html`
- `app/web/templates/providers.html`
- `app/web/templates/operational_smoke.html`
- `tests/test_phase_18_7_interaction_hierarchy.py` (new)
- `docs/phases/PHASE_18_7_INTERACTION_HIERARCHY_TRIAGE_ERGONOMICS.md` (this file)
