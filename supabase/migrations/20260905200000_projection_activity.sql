-- Daily week-projection snapshots and current-season Recent Activity archive.
-- ESPN does not keep a projection time series or past-year Recent Activity.

create table if not exists public.player_projection_pulls (
  id uuid primary key default gen_random_uuid(),
  pulled_at timestamptz not null unique,
  season int not null,
  week int not null
);

create table if not exists public.player_projections (
  pull_id uuid not null references public.player_projection_pulls (id) on delete cascade,
  player_id int not null,
  name text not null,
  pos text,
  nfl_team text,
  injury_status text,
  owner text,
  fantasy_team text,
  lineup_slot text,
  projected_points numeric not null default 0,
  percent_owned numeric,
  rostered boolean not null default false,
  fa_top_projected boolean not null default false,
  fa_top_owned boolean not null default false,
  primary key (pull_id, player_id)
);

create index if not exists player_projection_pulls_pulled_at_idx
  on public.player_projection_pulls (pulled_at desc);

create table if not exists public.league_activity (
  id text primary key,
  season int not null,
  occurred_at timestamptz not null,
  actions jsonb not null default '[]'::jsonb,
  raw jsonb not null default '{}'::jsonb
);

create index if not exists league_activity_season_occurred_idx
  on public.league_activity (season, occurred_at desc);

alter table public.player_projection_pulls enable row level security;
alter table public.player_projections enable row level security;
alter table public.league_activity enable row level security;

drop policy if exists player_projection_pulls_select_anon on public.player_projection_pulls;
create policy player_projection_pulls_select_anon on public.player_projection_pulls
  for select to anon, authenticated using (true);

drop policy if exists player_projections_select_anon on public.player_projections;
create policy player_projections_select_anon on public.player_projections
  for select to anon, authenticated using (true);

drop policy if exists league_activity_select_anon on public.league_activity;
create policy league_activity_select_anon on public.league_activity
  for select to anon, authenticated using (true);

insert into public.reports (id, last_updated)
values
  ('player-projections', now()),
  ('league-activity', now())
on conflict (id) do nothing;
