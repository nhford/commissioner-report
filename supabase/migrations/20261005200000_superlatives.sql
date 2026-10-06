-- Shared facts for Superlatives. Awards are queries over these rows, not new tables.
-- is_regular is true only for a regular-season week. Winners-bracket weeks are stored
-- with is_regular false. Consolation weeks are not stored.
-- scope is all_time or a season year. "window" is reserved in Postgres.

create table if not exists public.player_weeks (
  season int not null,
  week int not null,
  player_id int not null,
  name text not null,
  pos text,
  nfl_team text,
  team_id int not null,
  owner text,
  lineup_slot text,
  started boolean not null default false,
  points numeric not null default 0,
  projected_points numeric,
  primary key (season, week, player_id)
);

create index if not exists player_weeks_season_idx on public.player_weeks (season, week);

create table if not exists public.team_weeks (
  season int not null,
  week int not null,
  team_id int not null,
  owner text,
  team_name text,
  points numeric not null default 0,
  is_regular boolean not null default true,
  starter_points numeric,
  optimal_points numeric,
  projection_lineup_points numeric,
  anti_projection_starts int,
  projections_ok boolean not null default false,
  primary key (season, week, team_id)
);

create index if not exists team_weeks_season_idx on public.team_weeks (season, week);

create table if not exists public.draft_picks (
  season int not null,
  player_id int not null,
  name text not null,
  pos text,
  team_id int,
  owner text,
  bid numeric not null default 0,
  primary key (season, player_id)
);

create table if not exists public.player_photos (
  player_id int primary key,
  name text not null,
  photo_path text
);

create table if not exists public.superlatives (
  category text not null,
  scope text not null,
  rank int not null,
  subject_type text not null,
  subject_key text not null,
  subject_name text not null,
  value numeric not null,
  display text not null,
  detail jsonb not null default '{}'::jsonb,
  primary key (category, scope, rank),
  constraint superlatives_rank check (rank between 1 and 3),
  constraint superlatives_subject_type check (
    subject_type in ('player', 'team', 'duo', 'nfl')
  )
);

alter table public.player_weeks enable row level security;
alter table public.team_weeks enable row level security;
alter table public.draft_picks enable row level security;
alter table public.player_photos enable row level security;
alter table public.superlatives enable row level security;

drop policy if exists player_weeks_select_anon on public.player_weeks;
create policy player_weeks_select_anon on public.player_weeks
  for select to anon, authenticated using (true);

drop policy if exists team_weeks_select_anon on public.team_weeks;
create policy team_weeks_select_anon on public.team_weeks
  for select to anon, authenticated using (true);

drop policy if exists draft_picks_select_anon on public.draft_picks;
create policy draft_picks_select_anon on public.draft_picks
  for select to anon, authenticated using (true);

drop policy if exists player_photos_select_anon on public.player_photos;
create policy player_photos_select_anon on public.player_photos
  for select to anon, authenticated using (true);

drop policy if exists superlatives_select_anon on public.superlatives;
create policy superlatives_select_anon on public.superlatives
  for select to anon, authenticated using (true);

insert into public.reports (id, last_updated)
values ('superlatives', now())
on conflict (id) do nothing;
