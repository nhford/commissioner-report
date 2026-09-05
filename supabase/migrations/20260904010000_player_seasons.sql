-- Year-by-year roster/points detail for expandable player rows.

alter table public.player_records
  add column if not exists seasons jsonb not null default '[]';
