-- Commissioner's Report schema. Run in the Supabase SQL editor if the CLI is not linked.

create table if not exists public.reports (
  id text primary key,
  last_updated timestamptz not null default now(),
  season int,
  current_week int,
  through_season int,
  through_week int,
  titles_through_season int,
  min_starts int default 30
);

create table if not exists public.median_pulls (
  id uuid primary key default gen_random_uuid(),
  pulled_at timestamptz not null unique,
  season int not null,
  week int not null
);

create table if not exists public.median_standings (
  pull_id uuid not null references public.median_pulls (id) on delete cascade,
  team text not null,
  rank int not null,
  current numeric not null,
  projection numeric not null,
  median numeric not null,
  payout numeric not null,
  logo_path text,
  primary key (pull_id, team)
);

create table if not exists public.player_records (
  name text primary key,
  pos text not null,
  teams text[] not null default '{}',
  g int not null default 0,
  w int not null default 0,
  gs int not null default 0,
  ws int not null default 0,
  pg int not null default 0,
  pw int not null default 0,
  pgs int not null default 0,
  pws int not null default 0,
  titles int not null default 0
);

create index if not exists median_pulls_pulled_at_idx on public.median_pulls (pulled_at desc);

alter table public.reports enable row level security;
alter table public.median_pulls enable row level security;
alter table public.median_standings enable row level security;
alter table public.player_records enable row level security;

drop policy if exists reports_select_anon on public.reports;
create policy reports_select_anon on public.reports
  for select to anon, authenticated using (true);

drop policy if exists median_pulls_select_anon on public.median_pulls;
create policy median_pulls_select_anon on public.median_pulls
  for select to anon, authenticated using (true);

drop policy if exists median_standings_select_anon on public.median_standings;
create policy median_standings_select_anon on public.median_standings
  for select to anon, authenticated using (true);

drop policy if exists player_records_select_anon on public.player_records;
create policy player_records_select_anon on public.player_records
  for select to anon, authenticated using (true);

insert into storage.buckets (id, name, public)
values ('logos', 'logos', true)
on conflict (id) do update set public = true;

drop policy if exists logos_public_read on storage.objects;
create policy logos_public_read on storage.objects
  for select to anon, authenticated
  using (bucket_id = 'logos');
