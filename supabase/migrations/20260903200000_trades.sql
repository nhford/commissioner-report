-- Completed league trades for Trade-o-gami. Owners are nicknames from data/league.json.

create table if not exists public.trades (
  id text primary key,
  season int not null,
  week int not null default 0,
  owners text[] not null,
  constraint trades_owners_min check (cardinality(owners) >= 2)
);

create index if not exists trades_season_idx on public.trades (season);

alter table public.trades enable row level security;

drop policy if exists trades_select_anon on public.trades;
create policy trades_select_anon on public.trades
  for select to anon, authenticated using (true);

insert into public.reports (id, last_updated)
values ('trade-o-gami', now())
on conflict (id) do nothing;
