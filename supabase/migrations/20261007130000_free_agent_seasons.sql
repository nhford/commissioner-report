-- Season fantasy points for players who were free agents or on waivers.
-- Rankings drop anyone who also appears in player_weeks or draft_picks.

create table if not exists public.free_agent_seasons (
  season int not null,
  player_id int not null,
  name text not null,
  pos text,
  nfl_team text,
  points numeric not null default 0,
  primary key (season, player_id)
);

create index if not exists free_agent_seasons_season_idx
  on public.free_agent_seasons (season);

alter table public.free_agent_seasons enable row level security;

drop policy if exists free_agent_seasons_select_anon on public.free_agent_seasons;
create policy free_agent_seasons_select_anon on public.free_agent_seasons
  for select to anon, authenticated using (true);
