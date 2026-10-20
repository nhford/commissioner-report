-- FAAB claims, including ones that lost or never processed.
-- result is added (won), lost (outbid), or conditional (ESPN skipped it).

create table if not exists public.waiver_bids (
  season int not null,
  id text not null,
  week int not null,
  team_id int not null,
  owner text,
  player_id int not null,
  player_name text,
  bid numeric not null default 0,
  result text not null,
  primary key (season, id),
  constraint waiver_bids_result check (result in ('added', 'lost', 'conditional'))
);

create index if not exists waiver_bids_season_idx on public.waiver_bids (season);

alter table public.waiver_bids enable row level security;

drop policy if exists waiver_bids_select_anon on public.waiver_bids;
create policy waiver_bids_select_anon on public.waiver_bids
  for select to anon, authenticated using (true);
