# Commissioner’s Report

Unified front-end for this league’s coding projects. v1 includes **Median Monday** and **Player Records**.

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
3. Seed the first Median Monday pull and NFL logos:

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

## Scrapers

```bash
python scrapers/median_monday.py
python scrapers/player_records.py
python scrapers/fantasy_logos.py
python scrapers/player_projections.py
python scrapers/recent_activity.py
```

Median Monday **inserts** a new dated pull each run (history is kept). Player records increment from the table. Daily projections insert a new snapshot; Recent Activity upserts the current-season feed.

## Schedules

| Job | Cadence | Writes |
| --- | --- | --- |
| Median Monday | Daily Wed–Mon 8pm ET, plus Sun/Thu 11:30pm ET | `median_pulls`, `median_standings`, `fantasy_logos`, `logos/fantasy/` |
| Player records | Tuesday 12pm ET | `player_records` |
| Daily archives | Daily 12pm ET | `player_projection_pulls`, `player_projections`, `league_activity` |
| Fantasy logos | Manual (`workflow_dispatch` or `python scrapers/fantasy_logos.py`) | `fantasy_logos`, `logos/fantasy/{season}/{team_id}`, `logos/fantasy/catalog.json` |

GitHub / Vercel secrets: `ESPN_S2`, `ESPN_SWID`, `SUPABASE_SERVICE_ROLE_KEY`, `REVALIDATE_SECRET`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`. Optional variables: `ESPN_LEAGUE_ID`, `ESPN_SEASON_ID`, `VERCEL_REVALIDATE_URL`.

## Adding a third project

1. Add a table (and RLS select-for-anon) in `supabase/migrations/`.
2. Write a scraper that upserts via `scrapers/supabase_client.py`.
3. Fetch in `lib/data.ts` and add a page + `lib/nav.ts` row.
4. Add a GitHub Action cron and include the path in `app/api/revalidate/route.ts`.
