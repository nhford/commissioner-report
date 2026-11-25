-- Starter touchdowns for a fantasy week, excluding the D/ST.
-- Passing, rushing, receiving, and return scores. A quarterback and his
-- receiver each count when both start. Yardage bonuses are not extra scores.

alter table public.team_weeks
  add column if not exists touchdowns int;
