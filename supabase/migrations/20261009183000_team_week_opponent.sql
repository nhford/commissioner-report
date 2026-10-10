alter table public.team_weeks
  add column if not exists opponent_owner text;
