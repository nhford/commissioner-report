-- ESPN's component projection (yards, receptions, touchdowns) for each snapshot.
-- The score model reads this live from ESPN; the column is the archive for backtests.

alter table public.player_projections
  add column if not exists projected_breakdown jsonb;
