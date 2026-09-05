-- Historical ESPN fantasy team logos. Files live in the public logos bucket
-- at fantasy/{season}/{team_id}.jpg (or .svg). This table is the catalog.

create table if not exists public.fantasy_logos (
  season int not null,
  team_id int not null,
  owner text,
  team_name text not null,
  logo_path text,
  source_url text,
  primary key (season, team_id)
);

create index if not exists fantasy_logos_owner_idx
  on public.fantasy_logos (owner, season desc);

alter table public.fantasy_logos enable row level security;

drop policy if exists fantasy_logos_select_anon on public.fantasy_logos;
create policy fantasy_logos_select_anon on public.fantasy_logos
  for select to anon, authenticated using (true);
