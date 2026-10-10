-- Losers-bracket games can be stored without counting as regular season or winners-bracket weeks.
-- dst_points is the started defense total, used when those player lines are not stored.

alter table public.team_weeks
  add column if not exists is_consolation boolean not null default false;

alter table public.team_weeks
  add column if not exists dst_points numeric;
