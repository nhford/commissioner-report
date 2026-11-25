# Trim complexity

Plan for one ingestion path, one schedule, and one feature list. Every live section stays. This document is the plan; it does not change runtime behavior.

Measured on 23 Nov 2026 against the working tree on `payout-runner-up` (including uncommitted files). Physical lines of `app/`, `components/`, `lib/`, `scrapers/`, `supabase/migrations/`, and `.github/workflows/`. Comments and blanks count. `node_modules`, `.next`, `.venv`, `.worktrees`, `package-lock.json`, and JSON data do not.

## Baseline

| Area | Lines | Share |
| --- | ---: | ---: |
| `scrapers/` | 10,856 | 57% |
| `components/` | 3,702 | 19% |
| `lib/` | 3,154 | 17% |
| `app/` | 547 | 3% |
| `supabase/migrations/` | 458 | 2% |
| `.github/workflows/` | 273 | 1% |
| **Total** | **18,990** | **100%** |

The largest files are real domain logic, and most of those lines should stay:

| File | Lines | What it is |
| --- | ---: | --- |
| `scrapers/superlative_ranks.py` | 4,188 | Award math. 1,227 of those lines are `self_test`. |
| `scrapers/trades.py` | 1,094 | Trade ingest. 248 lines are `self_test`. |
| `scrapers/superlatives.py` | 1,060 | ESPN week ingest, waivers, free agents, headshots, then rankings. |
| `lib/superlatives.ts` | 893 | Award copy, filters, and client-side board variants. |
| `scrapers/score_model.py` | 871 | Runtime Monte Carlo used by Median Watch. |
| `components/SuperlativeCard.tsx` | 666 | Award rendering. |
| `scrapers/immaculate_grid.py` plus `lib/grid*.ts` plus `components/ImmaculateGrid.tsx` | ~1,900 | A separate nflverse game, marked coming soon. |

Inline `self_test` blocks (ranks, trades, grid, nfl teams, waiver bids) are **1,631 lines, 8.6%** of the repo. Moving them under `scrapers/tests/` makes the modules easier to read and changes the line count by about zero. They stay.

`scrapers/calibrate_score_model.py` (402) and `scrapers/backtest_score_model.py` (479) are **881 lines, 4.6%**. No cron imports them. Median Watch reads `data/score_model_params.json`. They stay in the repo, in a lab folder, off the cron install.

Applied migrations stay as history. Squashing them does not simplify the running app.

## What actually sprawled

README’s “Adding another project” is the design: a migration, a scraper, a fetch in `lib/data.ts`, a page, a `lib/nav.ts` row, a new GitHub Action, and a path in `app/api/revalidate/route.ts`. Each feature grew its own driveway.

That produced seven workflow files that repeat the same checkout, Python 3.12, pip install, ESPN secrets, and Supabase URL. Five of them are scheduled. Three of them fire at the same minute:

| Workflow | Schedule (EST, fixed UTC−5) | Script |
| --- | --- | --- |
| `scrape-player-records.yml` | Tue 3:30am | `player_records.py` |
| `scrape-trades.yml` | Tue 3:30am | `trades.py` |
| `scrape-superlatives.yml` | Tue 3:30am | `superlatives.py` |
| `scrape-daily-archives.yml` | Daily 12:00pm | projections, then recent activity |
| `scrape-median-monday.yml` | Wed–Mon 8:00pm, plus Sun/Thu 11:30pm | `median_monday.py` |
| `scrape-fantasy-logos.yml` | manual | `fantasy_logos.py` |
| `scrape-immaculate-grid.yml` | manual | `immaculate_grid.py` |

Tuesday currently starts three runners. Each one checks out the repo and installs pandas, numpy, and scipy. Superlatives already imports `player_records` and rewrites player rows when names change, and it already reads the trades table. The records job is a second full walk of the same ESPN box scores.

The same facts are also copied in code:

- Owner lookup from `data/league.json` in `lib/owners.ts`, `scrapers/logo_utils.py`, `scrapers/player_records.py`, and `scrapers/superlative_ranks.py`.
- Week-1 Thursday as a Labor Day formula in `lib/grid.ts` and `scrapers/immaculate_grid.py`, and again as a hardcoded dict in `superlative_ranks.py`.
- Award id sets (`OWNER_AWARDS`, `HIDDEN_ON_OWNER`, zero-owner display strings) in both `lib/superlatives.ts` and `superlative_ranks.py`.
- `build_superlatives` (about 265 lines) is the same `_store(...)` call repeated per award, including four copied team-week variants for extremes and four more for stretches.
- Page chrome: title, stamp, and a mobile `<details>` plus a desktop paragraph, copied on Median Watch, Superlatives, Player Records, and Sam’s Stuff.

Sam’s Stuff and O-Gami are the shape to keep. They read `team_weeks` and `trades` and compute a view. They have no scraper and no cron.

## Target shape

```
data/league.json          owners, seasons, week-1 dates, feature list
scrapers/ingest/          one writer per fact table (weeks, trades, activity, waivers, projections)
scrapers/derive/          records rollup, superlative ranks, median sim
scrapers/lab/             calibrate + backtest, not installed by cron
app + components          one view per section, registered in one list
.github/workflows/scrape.yml
```

A new section is a view over a table that already exists, plus one row in the feature list. A new fact is one ingest module added to an existing schedule group. A new workflow file is no longer part of the checklist.

Schedule groups:

| Group | When | Steps, in order |
| --- | --- | --- |
| `tuesday` | Tue 3:30am EST | weeks → trades → waiver bids → records rollup → ranks → revalidate |
| `daily` | 12:00pm EST | projections → recent activity → revalidate |
| `median` | Wed–Mon 8:00pm, Sun/Thu 11:30pm | Median Watch sim → revalidate |
| `manual` | `workflow_dispatch` only | logos, immaculate grid, full backfill |

`workflow_dispatch` takes a `group` input so a person can run any group without a separate file. The grid workflow’s check against `github.event.schedule` goes away with that file; the workflow has no schedule.

Cron expressions go from **6 to 4**. Scheduled workflow files go from **5 to 1**. Tuesday ESPN sessions go from **3 to 1**, and that single session installs dependencies once. Workflow YAML goes from **273 lines to about 110**.

## Phases

Each phase is safe to ship alone. Later phases assume the earlier ones. Parity means the stored rows match a run of today’s scripts on the same database.

### 1. One workflow

Replace the seven YAML files with `scrape.yml`. Keep each Python entry point callable. Order the Tuesday steps so ranks run after weeks and trades are written.

Check: dispatch each group once; confirm the same tables update and revalidate still fires. Confirm the three old Tuesday crons are gone so they cannot double-write.

**Net about −160 lines (−0.8%).** The operational cut is the point of this phase.

### 2. One feature list and one page shell

Add `lib/features.ts` as the list of href, label, blurb, coming-soon flag, and revalidate path. `lib/nav.ts`, the home hub, and `app/api/revalidate/route.ts` read that list.

Add a `ReportPage` shell for the title, the updated line, and the how-it-works paragraph (collapsed on a phone, visible on a desktop). Median Watch, Superlatives, Player Records, and Sam’s Stuff use it.

**Net about −50 lines.** New sections stop touching four files.

### 3. One league module

Add `scrapers/league.py` that loads `data/league.json`: owners by season, first season, current season, and week-1 Thursday. Store the Thursday dates in `league.json` so Python and `lib/grid.ts` read the same values. Point `logo_utils.owner_for`, `player_records.owner_name`, and `superlative_ranks.owner_for_team` at that module.

Move chunked insert/delete into `supabase_client.py` and use it from the ingest scripts.

**Net about −130 lines.** Week-1 dates stop drifting between the grid formula, the grid scraper, and the activity-week dict.

### 4. An award registry

Keep one function per award that has its own rule (earnings, 6/7 games, FAAB, touchdown differential, closest matchup). Those functions are the product.

Replace the hand-written `_store` sequence in `build_superlatives` with a list of award specs: id, builder, whether an owner gets their own slice, whether the award hides on an owner board, and the zero-row display. Build the over/under pairs and the four team-week boards from one helper instead of copied blocks.

Put the shared id sets and zero-row strings in `data/awards.json`. `superlative_ranks.py` and `lib/superlatives.ts` both read it. Hint sentences stay in TypeScript; they are UI copy.

**Net about −310 lines (−1.6%).** This is the largest code cut that leaves every award in place.

### 5. Records from stored weeks

`player_records.py` walks ESPN matchups that `superlatives.py` already stores as `player_weeks` and `team_weeks` (starter flag, points, owner, regular vs consolation). After phase 1, the Tuesday group writes weeks first. Replace the records ESPN loop with a rollup over those tables, and keep title credit, season JSON, and headshots as the records step.

Gate: run the current scraper and the rollup against the same seasons and diff wins, losses, starts, and titles. Ship the rollup only when that diff is empty. If a field is missing from `team_weeks`, add the column in a new migration and keep the ESPN walk until the backfill matches.

**Net about −220 lines if the diff is empty. About 0 if it is not.** This phase is included in the headline percentage as the success case, and excluded from the low end of the range.

### 6. Split the cron install

Move `calibrate_score_model.py` and `backtest_score_model.py` to `scrapers/lab/`. Add `scrapers/requirements-lab.txt` for scipy’s extra lab use. Runtime `requirements.txt` keeps what Median Watch imports (`numpy`, `pandas`, `scipy`, because `median_monday.py` uses `scipy.stats.gamma`) and what the Tuesday and daily jobs import.

Tuesday and daily jobs install the smaller file. Line count of Python stays about the same (**about −10 lines of import-path edits, plus a short requirements file**). Cron minutes drop because Tuesday stops installing the lab stack’s unused pieces only where those imports are actually unused. Median Watch still installs scipy.

## Anticipated line change

Recommended plan is phases 1–5, with phase 5 succeeding the parity check.

| Phase | Net lines | Share of 18,990 |
| --- | ---: | ---: |
| 1. One workflow | −160 | −0.8% |
| 2. Feature list and page shell | −50 | −0.3% |
| 3. League module | −130 | −0.7% |
| 4. Award registry | −310 | −1.6% |
| 5. Records rollup | −220 | −1.2% |
| **Recommended** | **−870** | **−4.6%** |

Round that to **about a 5% reduction, roughly 900 lines**.

The honest range is **−3% to −6%**:

- **−3% (about −650 lines)** if the records diff is not empty and phase 5 waits, and the award registry only collapses the `_store` wiring.
- **−5% (about −870 lines)** is the plan as written.
- **−6% (about −1,200 lines)** if the award helpers and the records rollup both come in at the high end of what the duplicated blocks allow.

Phases 1–4 are the part to do even if phase 5 waits. That set is about **−650 lines, −3.4%**, and it removes the sprawl (one schedule, one feature list, one owner/calendar module, one award catalog).

### Optional cuts, separate from the 5%

These change the product or delete the ability to refit the model. They are not part of the recommended plan.

| Cut | Net lines | Additional share |
| --- | ---: | ---: |
| Delete the lab scripts and keep `data/score_model_params.json` | −881 | −4.6% |
| Remove the Immaculate Grid implementation (page, API, `lib/grid*.ts`, component, scraper, workflow). Leave the migration, since the tables may already exist. | about −2,010 | −10.6% |

Doing the recommended plan and deleting the lab scripts is about **−10%**. Doing the recommended plan and removing the grid implementation is about **−15%**. Doing all three is about **−20%**. The grid is built and only the cron is shelved; removing it is a product call.

## What this leaves alone

- Award math that is unique to one superlative. A generic ranking DSL would hide the rules.
- `score_model.py`. Median Watch runs it every evening.
- Sam’s Stuff and O-Gami as TypeScript views over shared tables.
- Inline tests. Relocate them when a module is already being edited; that is a reading aid, and it is not part of the percentage.
- Migrations already applied.
- Waiver Bids and Draft History nav entries. Waiver rows and draft picks are already written by the Tuesday ingest. Those pages, when they exist, should be views, the way O-Gami is.

## Order of work

1. Phase 1 on its own, and watch one Tuesday plus one median run.
2. Phases 2 and 3 together. They are mechanical and easy to review.
3. Phase 4 behind the existing `superlatives.py --self-test` output. The stored `superlatives` rows for the current scopes should match.
4. Phase 5 only after a season-by-season diff of player records.
5. Phase 6 whenever the workflow file is touched again.

Re-count with the same directories after each phase and record the actual delta next to the estimate in this file.

## Landed

Phases 1–4 are in this branch. Phase 5 is written and gated off. The 6/7 and touchdown-differential awards stay on their own pull request, and the trade ledger is not in this branch.

The schedule, the feature list, and the award catalog got smaller. The records rollup is new code that sits next to the ESPN walk, and Immaculate Grid moves onto the shared schedule, so the file total did not fall. A count of the same directories on the dirtier tree this plan was measured against went from 18,990 to 19,026 (+36, +0.2%).

Phase 5 gate, run against the live tables on 23 Nov 2026: 517 stored players, 517 rolled up, **250 mismatches**. 125 of those disagree on wins, losses, starts, or titles, and 123 of that 125 match the regular season and disagree on the playoff. Playoff `team_weeks` leave `opponent_owner` empty, including a `team_id` 0 bye scored at 0. Tuesday still runs `player_records.py` with the ESPN walk. `python scrapers/player_records.py --diff` repeats the comparison. `python scrapers/player_records.py --from-weeks` is the rollup, and it is not on the schedule.
