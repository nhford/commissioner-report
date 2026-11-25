-- Immaculate Grid answer key and saved guesses.
-- Anon and authenticated have no privileges. The public key must not be able
-- to read valid players for a square. The Next.js routes use the service role.

create table if not exists public.grid_players (
  id text primary key,
  name text not null,
  pos text not null,
  year_min int not null,
  year_max int not null,
  fame numeric not null default 0,
  search_name text not null
);

create index if not exists grid_players_search_idx on public.grid_players (search_name);

create table if not exists public.grid_tags (
  player_id text not null references public.grid_players (id),
  tag text not null,
  primary key (player_id, tag)
);

create index if not exists grid_tags_tag_idx on public.grid_tags (tag);

create table if not exists public.grids (
  played_on date primary key,
  rows text[] not null,
  cols text[] not null,
  season int not null,
  constraint grids_shape check (cardinality(rows) = 3 and cardinality(cols) = 3)
);

create table if not exists public.grid_sessions (
  played_on date not null references public.grids (played_on),
  anon_id uuid not null,
  given_up boolean not null default false,
  finished_at timestamptz,
  primary key (played_on, anon_id)
);

create table if not exists public.grid_guesses (
  played_on date not null references public.grids (played_on),
  anon_id uuid not null,
  cell smallint not null,
  player_id text not null references public.grid_players (id),
  correct boolean not null,
  created_at timestamptz not null default now(),
  primary key (played_on, anon_id, cell, player_id),
  constraint grid_guesses_cell check (cell between 0 and 8)
);

create index if not exists grid_guesses_anon_idx on public.grid_guesses (anon_id, played_on);
create index if not exists grid_guesses_correct_idx
  on public.grid_guesses (played_on, cell)
  where correct;

alter table public.grid_players enable row level security;
alter table public.grid_tags enable row level security;
alter table public.grids enable row level security;
alter table public.grid_sessions enable row level security;
alter table public.grid_guesses enable row level security;

revoke all on table public.grid_players from anon, authenticated;
revoke all on table public.grid_tags from anon, authenticated;
revoke all on table public.grids from anon, authenticated;
revoke all on table public.grid_sessions from anon, authenticated;
revoke all on table public.grid_guesses from anon, authenticated;
