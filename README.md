# Commissioner’s Report

Unified front-end for this league’s coding projects. Live sections are **Median Watch**, **Player Records**, and **Superlatives**. Immaculate Grid is built and marked coming soon.

Numbers live in Supabase Postgres. Team logos live in a public `logos` bucket. The Next.js site is read-only and statically cached; scrapers refresh the cache after they write.

Project URL: `https://jdfdpbgqiigkjatzudle.supabase.co`

## Local site

```bash
cp .env.example .env
# fill NEXT_PUBLIC_SUPABASE_ANON_KEY (and ESPN cookies if you will scrape)
npm install
npm run dev
```

## One-time Supabase setup

1. Run the files in [`supabase/migrations/`](supabase/migrations/) in the Supabase SQL editor (start with `20260830200000_init.sql`).
2. Add `SUPABASE_SERVICE_ROLE_KEY` to `.env`.
3. Seed the first Median Watch pull and NFL logos:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r scrapers/requirements.txt
python scrapers/seed_median.py
python scrapers/seed_nfl_logos.py
```

4. Backfill player records (required once; the old JSON seed is incomplete):

```bash
python scrapers/player_records.py --full
python scrapers/fantasy_logos.py
```

5. Backfill Superlatives once. If this database was created before the latest migrations, run `20261007130000_free_agent_seasons.sql` and `20261009183000_team_week_opponent.sql` in the SQL editor first. The opponent column is what lets high and low team weeks say who they played.

```bash
python scrapers/superlatives.py --full
```

## Scrapers

```bash
python scrapers/median_monday.py
python scrapers/player_records.py
python scrapers/fantasy_logos.py
python scrapers/player_projections.py
python scrapers/recent_activity.py
python scrapers/trades.py
python scrapers/superlatives.py
python scrapers/immaculate_grid.py
```

Median Watch **inserts** a new dated pull each run (history is kept). Player records increment from the table. Daily projections insert a new snapshot; Recent Activity upserts the current-season feed.

Superlatives refreshes the current season, then rebuilds every year window and one-owner board. `python scrapers/superlatives.py --full` rebuilds 2022 through the current season. `python scrapers/superlatives.py --ingest-only` writes weeks and stops before rankings. `python scrapers/superlatives.py --ranks-only` recomputes rankings from tables already stored.

Immaculate Grid needs `supabase/migrations/20261029180000_immaculate_grid.sql` applied first. Those tables stay service-role only, so the public key cannot read valid answers. `python scrapers/immaculate_grid.py` rebuilds the nflverse answer key and inserts any missing daily puzzles from the `grid` window in `data/league.json`. `python scrapers/immaculate_grid.py --grids-only` only inserts missing days.

## Schedules

One workflow, [`.github/workflows/scrape.yml`](.github/workflows/scrape.yml), runs every group. Dispatch it with a `group` input (`tuesday`, `daily`, `median`, `logos`, `grid`, `backfill`).

| Group | Cadence | Steps |
| --- | --- | --- |
| Tuesday | Tuesday 3:30am EST | weeks and waiver bids, then trades, then player records, then ranks |
| Daily | Daily 12pm EST | projections, recent activity, revalidate |
| Median Watch | Wed–Mon 8pm EST, plus Sun/Thu 11:30pm EST | `median_monday.py` |
| Logos | Manual | `fantasy_logos.py` |
| Immaculate Grid | Manual until the section leaves coming soon | `immaculate_grid.py` |
| Backfill | Manual | full week ingest, trades, records, then ranks |

Tuesday writes `player_weeks`, `team_weeks`, `draft_picks`, `free_agent_seasons`, `waiver_bids`, `league_activity`, `trades`, `player_records`, and `superlatives`. Daily writes `player_projection_pulls`, `player_projections`, and `league_activity`. Median Watch writes `median_pulls`, `median_standings`, and fantasy logos.

GitHub / Vercel secrets: `ESPN_S2`, `ESPN_SWID`, `SUPABASE_SERVICE_ROLE_KEY`, `REVALIDATE_SECRET`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`. Optional variables: `ESPN_LEAGUE_ID`, `ESPN_SEASON_ID`, `VERCEL_REVALIDATE_URL`.

## Adding another project

1. Add a table (and RLS select-for-anon) in `supabase/migrations/`.
2. Write a scraper that upserts via `scrapers/supabase_client.py`, and add it to an existing group in `.github/workflows/scrape.yml`.
3. Add a row in `lib/features.ts`. The nav, the home hub, and the revalidate route read that list.
4. Fetch in `lib/data.ts` and add a page. Use `components/ReportPage.tsx` for the title and the how-it-works paragraph.
