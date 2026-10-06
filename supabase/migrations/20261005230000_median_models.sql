-- Both Median Watch formulas on pulls from this migration forward.
-- Older rows leave these null, and the site disables the M1/M2 toggle.

alter table public.median_standings
  add column if not exists median_m1 numeric,
  add column if not exists payout_m1 numeric,
  add column if not exists median_m2 numeric,
  add column if not exists payout_m2 numeric;
