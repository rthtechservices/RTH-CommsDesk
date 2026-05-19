# Phase 18.6 — Visual Design System and Dashboard Polish

**Status:** ✅ Completed  
**Date:** 2026-05-19  
**Scope:** Visual/UX redesign only. No new execution capability added.

---

## Objective

Upgrade the RTH CommsDesk web UI from a plain admin-style interface into a polished, modern command-center aesthetic with a subtle retro-futuristic 1990s feel. The goal is a "mission control / operations console" look — dark, information-dense, purposeful.

Hard constraints:
- No Phase 19 execution behavior
- No Outlook send / calendar / Teams
- No `.env` editing from UI
- All existing tests must remain green

---

## Design System

### Color Palette (`app/web/ui.css`)

| Variable | Value | Use |
|---|---|---|
| `--bg` | `#0c1117` | Page background |
| `--surface` | `#141b24` | Panel background |
| `--surface-2` | `#192131` | Nested surface |
| `--surface-3` | `#1e2840` | Hover / active |
| `--line` | `#243044` | Borders |
| `--line-strong` | `#354e6a` | Strong borders |
| `--text` | `#c8d8e8` | Primary text |
| `--muted` | `#7390a8` | Secondary text |
| `--brand` | `#1cba8b` | Brand green |
| `--brand-dark` | `#179972` | Brand hover |
| `--accent` | `#4a8ff5` | Accent blue |
| `--ok` | `#3ab96a` | Success / live |
| `--warn` | `#d4912a` | Warning / dry-run |
| `--bad` | `#e04842` | Error / disabled |
| `--disabled` | `#48607a` | Disabled states |

### Layout
- `.wrap` — 1280px max-width centered
- `.wide-wrap` — 1720px max-width centered
- Sticky dark topbar with RTH CommsDesk brand and nav links
- `.page-pad` — consistent vertical padding
- `.panel` — dark surface card with border
- `.subtle-panel` — lower-contrast info card

### Workflow Rail
Connected pill-segment breadcrumb showing current step in:  
`Sync → Triage → Analyze → Review → Prepare → Execute → Audit`

Active steps use brand green highlight.

### Status Dots
`.status-dot.{state}` — glow-colored dot indicators:
- `live` → green
- `dry_run` → amber
- `mock` → muted
- `disabled` / `failed` → red
- `missing_configuration` → red

---

## Files Changed

### New files
- `app/web/templates/base.html` — shared Jinja2 base template
- `tests/test_phase_18_6_visual_design.py` — 20 new visual design tests
- `docs/phases/PHASE_18_6_VISUAL_DESIGN_SYSTEM_POLISH.md` — this file

### Rewritten templates (17 total)
All templates now extend `base.html` and use the dark design system:

| Template | Notes |
|---|---|
| `dashboard.html` | Status grid, attention queue, command-center metrics |
| `message_detail.html` | 4 action panel sections, reset contact button |
| `review_packages.html` | Workflow rail active on Review step |
| `review_package_detail.html` | Two-column layout, approve/reject sidebar |
| `executions.html` | Execution queue table |
| `execution_detail.html` | Audit trail, attempt history, controls sidebar |
| `providers.html` | Provider matrix table, boundary text |
| `operational_smoke.html` | Section headers, smoke check display |
| `bulk_triage.html` | Candidate list |
| `contacts.html` | Filterable contact list |
| `voice_calibration.html` | Voice profiles + sent-mail learning |
| `admin.html` | Uses actual route variables (not `system_info`) |
| `drafts.html` | Draft list |
| `login.html` | Standalone dark login |
| `contact_detail.html` | Edit Contact (capital C) |
| `draft_review.html` | Review-only notice, Provider field |

### Modified
- `app/web/ui.css` — completely rewritten dark design system

---

## Tests

### New tests (`test_phase_18_6_visual_design.py`)
- Parametrized route smoke: 11 routes all return 200
- Dark theme CSS marker on dashboard
- `base.html` nav present on dashboard, review_packages, executions, bulk_triage, contacts, admin
- 4 grouped action panel headings in message_detail
- Microsoft write boundary strings in providers
- "This page observes configuration only" in providers
- 4 section headers in operational_smoke
- Workflow rail present on dashboard and review_packages

### Full suite result
```
158 passed in 5.17s
```
```
ruff check . → All checks passed
alembic upgrade head → passed
```

---

## What was NOT changed

- No execution logic modified
- No route handlers modified (except admin template variable alignment)
- No Outlook send / calendar / Teams added
- No `.env` editing from UI
- No Phase 19 work
