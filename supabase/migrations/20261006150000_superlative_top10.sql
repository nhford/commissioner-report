-- Store a real top 10, and let week records (median line, lowest payout) use their own subject type.

alter table public.superlatives drop constraint if exists superlatives_rank;

alter table public.superlatives
  add constraint superlatives_rank check (rank between 1 and 10);

alter table public.superlatives drop constraint if exists superlatives_subject_type;

alter table public.superlatives
  add constraint superlatives_subject_type check (
    subject_type in ('player', 'team', 'duo', 'nfl', 'week')
  );
