export type AwardGroup = "player" | "team";

export type SuperlativeDetail = {
  season?: number;
  week?: number;
  pos?: string | null;
  photo_path?: string | null;
  player_id?: number;
  player_name?: string | null;
  partner_id?: number;
  partner_name?: string | null;
  partner_pos?: string | null;
  partner_photo_path?: string | null;
  alternates?: SuperlativeCandidate[];
  logo_path?: string | null;
  partner_logo_path?: string | null;
  nfl_team?: string;
  start_season?: number;
  start_week?: number;
  end_season?: number;
  end_week?: number;
  active?: boolean;
  prizes_missing?: boolean;
  team_name?: string | null;
};

export type SuperlativeCandidate = {
  subject_type: string;
  subject_key: string;
  subject_name: string;
  value: number;
  display: string;
  detail: SuperlativeDetail;
};

export type SuperlativeRow = {
  category: string;
  scope: string;
  rank: number;
  subject_type: string;
  subject_key: string;
  subject_name: string;
  value: number;
  display: string;
  detail: SuperlativeDetail;
};

export type AwardDef = {
  id: string;
  label: string;
  group: AwardGroup;
  hint: string;
};

export const AWARDS: AwardDef[] = [
  {
    id: "most_fantasy_teams",
    label: "Most fantasy teams",
    group: "player",
    hint: "Distinct owners who rostered him.",
  },
  {
    id: "lowest_start",
    label: "Lowest started score",
    group: "player",
    hint: "Started weeks only. Defenses are left out. The same player can hold more than one spot.",
  },
  {
    id: "most_auction_dollars",
    label: "Most auction dollars",
    group: "player",
    hint: "Sum of draft prices, including keeper prices ESPN reports.",
  },
  {
    id: "most_added",
    label: "Most added",
    group: "player",
    hint: "Free-agent and waiver pickups. A move between league teams counts as a trade instead.",
  },
  {
    id: "most_dropped",
    label: "Most dropped",
    group: "player",
    hint: "Left every roster. A move onto another league team counts as a trade instead.",
  },
  {
    id: "most_traded_player",
    label: "Most traded",
    group: "player",
    hint: "Times he changed fantasy teams between weeks.",
  },
  {
    id: "player_duo_starts",
    label: "Duo started most together",
    group: "player",
    hint: "Weeks two teammates both started.",
  },
  {
    id: "lowest_team_week",
    label: "Lowest team week",
    group: "team",
    hint: "Single-week score, including the winners bracket. The same team can hold more than one spot.",
  },
  {
    id: "highest_team_week",
    label: "Highest team week",
    group: "team",
    hint: "Single-week score, including the winners bracket. The same team can hold more than one spot.",
  },
  {
    id: "payout_wins",
    label: "Payout wins",
    group: "team",
    hint: "Regular-season weeks as the top scorer since 2024. A tie counts for both teams.",
  },
  {
    id: "total_earnings",
    label: "Total earnings",
    group: "team",
    hint: "2022–2023 champion and runner-up prizes, plus weekly top-scorer pay from 2024 on.",
  },
  {
    id: "median_streak",
    label: "Median streak",
    group: "team",
    hint: "Regular-season weeks in a row in the top 6. Playoff weeks are skipped and do not break it.",
  },
  {
    id: "median_misses",
    label: "Median misses",
    group: "team",
    hint: "Regular-season weeks in a row outside the top 6. Playoff weeks are skipped.",
  },
  {
    id: "team_duo_trades",
    label: "Most trades together",
    group: "team",
    hint: "Completed deals between two owners.",
  },
  {
    id: "most_trades",
    label: "Most trades",
    group: "team",
    hint: "Deals an owner was part of. A three-team trade counts once.",
  },
  {
    id: "projection_beater",
    label: "Projection beater",
    group: "team",
    hint: "Starter points divided by the actual points of the lineup projections would have started. Weeks are summed first.",
  },
  {
    id: "lineup_efficiency",
    label: "Lineup efficiency",
    group: "team",
    hint: "Starter points divided by the best possible lineup’s actual points. Weeks are summed first.",
  },
  {
    id: "anti_projection_starts",
    label: "Anti-projection starts",
    group: "team",
    hint: "Starts that were outside the projection-optimal lineup.",
  },
  {
    id: "nfl_starter_week",
    label: "Most fantasy starters",
    group: "team",
    hint: "NFL team with the most players started in this league in a single week.",
  },
];

const AWARD_BY_ID = new Map(AWARDS.map((award) => [award.id, award]));

export function awardDef(id: string) {
  return AWARD_BY_ID.get(id) ?? null;
}

export type SeasonScope = "all_time" | "season";

export type SuperlativeFilters = {
  scope: SeasonScope;
  players: boolean;
  teams: boolean;
  hideDefense: boolean;
};

function lastParam(value: string | string[] | undefined) {
  if (Array.isArray(value)) return value[value.length - 1];
  return value;
}

function flag(value: string | string[] | undefined, fallback: boolean) {
  const last = lastParam(value);
  if (last === "1") return true;
  if (last === "0") return false;
  return fallback;
}

export function readFilters(search: {
  scope?: string | string[];
  players?: string | string[];
  teams?: string | string[];
  dst?: string | string[];
}): SuperlativeFilters {
  const scope = lastParam(search.scope) === "season" ? "season" : "all_time";
  return {
    scope,
    players: flag(search.players, true),
    teams: flag(search.teams, true),
    hideDefense: flag(search.dst, false),
  };
}

export function filterHref(
  current: SuperlativeFilters,
  next: Partial<SuperlativeFilters> = {},
) {
  const scope = next.scope ?? current.scope;
  const players = next.players ?? current.players;
  const teams = next.teams ?? current.teams;
  const hideDefense = next.hideDefense ?? current.hideDefense;
  const params = new URLSearchParams();
  if (scope === "season") params.set("scope", "season");
  if (!players) params.set("players", "0");
  if (!teams) params.set("teams", "0");
  if (hideDefense) params.set("dst", "1");
  const query = params.toString();
  return query ? `/superlatives?${query}` : "/superlatives";
}

const DEFENSE_POS = new Set(["D/ST", "DST"]);

export function isDefenseSubject(
  name: string,
  detail?: SuperlativeDetail | null,
) {
  if (detail?.pos && DEFENSE_POS.has(detail.pos)) return true;
  if (detail?.partner_pos && DEFENSE_POS.has(detail.partner_pos)) return true;
  if (detail?.player_name && /\bD\/ST\b/.test(detail.player_name)) return true;
  if (detail?.partner_name && /\bD\/ST\b/.test(detail.partner_name)) return true;
  return /\bD\/ST\b/.test(name);
}

export function podiumRows(rows: SuperlativeRow[], hideDefense: boolean) {
  const ranked = [...rows].sort((left, right) => left.rank - right.rank);
  if (!hideDefense) return ranked.slice(0, 3);
  const leader = ranked[0];
  const alternates = (leader?.detail.alternates ?? []).map((alt, index) => ({
    category: leader.category,
    scope: leader.scope,
    rank: ranked.length + index + 1,
    subject_type: alt.subject_type,
    subject_key: String(alt.subject_key),
    subject_name: alt.subject_name,
    value: Number(alt.value),
    display: alt.display,
    detail: alt.detail ?? {},
  }));
  return [...ranked, ...alternates]
    .filter((row) => !isDefenseSubject(row.subject_name, row.detail))
    .slice(0, 3)
    .map((row, index) => ({ ...row, rank: index + 1 }));
}
