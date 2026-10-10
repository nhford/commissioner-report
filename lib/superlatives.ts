import league from "@/data/league.json";
import { allOwners } from "@/lib/owners";

export const FIRST_SEASON = Math.min(
  ...Object.keys(league.owners_by_year).map((year) => Number(year)),
);

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
  partner_nfl_team?: string | null;
  partner_photo_path?: string | null;
  alternates?: SuperlativeCandidate[];
  logo_path?: string | null;
  partner_logo_path?: string | null;
  nfl_team?: string;
  owner?: string | null;
  owners?: string[];
  seasons?: { season: number; amount: number; games?: number }[];
  opponent_owner?: string | null;
  lines?: { label: string; amount: number }[];
  payments?: { label: string; amount: number; season: number; week: number }[];
  winners?: { owner: string; logo_path?: string | null }[];
  starters?: {
    name?: string | null;
    pos?: string | null;
    owner?: string | null;
    points?: number;
  }[];
  start_season?: number;
  start_week?: number;
  end_season?: number;
  end_week?: number;
  active?: boolean;
  weeks?: { season: number; week: number; points?: number; projected?: number; bye?: boolean }[];
  prizes_missing?: boolean;
  team_name?: string | null;
  consolation?: boolean;
  boards?: Record<string, SuperlativeCandidate[]>;
  changed_season?: number;
  changed_week?: number;
  changed_from?: number;
  hide_changed_season?: number;
  hide_changed_week?: number;
  hide_changed_from?: number;
  board_season?: number;
  board_week?: number;
  hide_board_season?: number;
  hide_board_week?: number;
  as_of_season?: number;
  as_of_week?: number;
  departed?: DepartedPlace[];
  hide_departed?: DepartedPlace[];
};

export type DepartedPlace = {
  rank: number;
  subject_key: string;
  subject_name: string;
  value: number;
  display: string;
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
  ownerHint?: string;
};

export const AWARDS: AwardDef[] = [
  {
    id: "highest_team_week",
    label: "Highest team week",
    group: "team",
    hint: "Single-week score from 2022 on, including the winners bracket. Exclude D/ST leaves out the started defense, so this will not match the ESPN total. Exclude consolation leaves out weeks 15–17 for eliminated teams. The same team can hold more than one spot.",
  },
  {
    id: "lowest_team_week",
    label: "Lowest team week",
    group: "team",
    hint: "Single-week score from 2022 on, including the winners bracket. Exclude D/ST leaves out the started defense, so this will not match the ESPN total. Exclude consolation leaves out weeks 15–17 for eliminated teams. The same team can hold more than one spot.",
  },
  {
    id: "highest_median",
    label: "Highest median",
    group: "team",
    hint: "Regular-season week since 2024 when the top-half line was highest. In a 12-team week that is 6th place.",
  },
  {
    id: "lowest_median",
    label: "Lowest median",
    group: "team",
    hint: "Regular-season week since 2024 when the top-half line was lowest.",
  },
  {
    id: "total_earnings",
    label: "Total earnings",
    group: "team",
    hint: "2022–2023 champion and runner-up prizes, plus weekly top-scorer pay from 2024 on.",
  },
  {
    id: "payout_wins",
    label: "Payout wins",
    group: "team",
    hint: "Regular-season weeks as the top scorer since 2024. A tie counts for both teams.",
  },
  {
    id: "lowest_payout",
    label: "Lowest payout",
    group: "team",
    hint: "Regular-season week since 2024 when the top score was the smallest, so the weekly pot was easiest to win.",
  },
  {
    id: "player_duo_starts",
    label: "Duo started most together",
    group: "player",
    hint: "Weeks two teammates both started.",
    ownerHint: "Weeks this owner started both.",
  },
  {
    id: "projection_over_streak",
    label: "Overperforming projection",
    group: "player",
    hint: "Consecutive rostered weeks scoring above his projection. A bye is skipped. A tie or a week off the roster ends it.",
    ownerHint: "Consecutive weeks on this roster scoring above his projection. A bye is skipped. A week on another team ends it.",
  },
  {
    id: "projection_under_streak",
    label: "Underperforming projection",
    group: "player",
    hint: "Consecutive rostered weeks scoring below his projection. A bye is skipped. A tie or a week off the roster ends it.",
    ownerHint: "Consecutive weeks on this roster scoring below his projection. A bye is skipped. A week on another team ends it.",
  },
  {
    id: "median_streak",
    label: "Median streak",
    group: "team",
    hint: "Regular-season weeks in a row in the top half. In 2022 that is the top 5. Playoff weeks are skipped and do not break it.",
  },
  {
    id: "median_misses",
    label: "Median misses",
    group: "team",
    hint: "Regular-season weeks in a row outside the top half. In 2022 that is outside the top 5. Playoff weeks are skipped.",
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
    hint: "NFL team with the most players started in this league in a single week. Hide D/ST leaves defenses out of that count.",
    ownerHint: "NFL team with the most players this owner started in a single week. Hide D/ST leaves defenses out of that count.",
  },
  {
    id: "highest_start",
    label: "Highest started score",
    group: "player",
    hint: "Started weeks only. Defenses are left out. The same player can hold more than one spot.",
  },
  {
    id: "lowest_start",
    label: "Lowest started score",
    group: "player",
    hint: "Started weeks only. Defenses are left out. The same player can hold more than one spot.",
  },
  {
    id: "most_fantasy_teams",
    label: "Most fantasy teams",
    group: "player",
    hint: "Distinct owners who rostered him.",
    ownerHint: "Seasons he played a game on this roster. Bench weeks count, a bye does not, and ties break on games played.",
  },
  {
    id: "least_fantasy_teams",
    label: "Least fantasy teams",
    group: "player",
    hint: "Most fantasy points from a player who was never rostered.",
  },
  {
    id: "most_auction_dollars",
    label: "Most auction dollars",
    group: "player",
    hint: "Sum of draft prices, including keeper prices ESPN reports.",
    ownerHint: "Draft dollars this owner spent on him, including keeper prices.",
  },
  {
    id: "most_traded_player",
    label: "Most traded",
    group: "player",
    hint: "Moved in a deal between league teams. A drop followed by a waiver or free-agent add counts as those instead.",
    ownerHint: "Times this owner traded him.",
  },
  {
    id: "most_added",
    label: "Most added",
    group: "player",
    hint: "Free-agent and waiver pickups, including a player another owner dropped.",
    ownerHint: "Times this owner added him.",
  },
  {
    id: "most_dropped",
    label: "Most dropped",
    group: "player",
    hint: "Left a roster, including a player another owner then added.",
    ownerHint: "Times this owner dropped him.",
  },
];

const AWARD_BY_ID = new Map(AWARDS.map((award) => [award.id, award]));

export function awardDef(id: string) {
  return AWARD_BY_ID.get(id) ?? null;
}

export type SuperlativeFilters = {
  fromYear: number;
  toYear: number;
  owner: string | null;
  players: boolean;
  teams: boolean;
  hideDefense: boolean;
  sortLatest: boolean;
  /** Tile filters keyed by `TileFilter.param`. A new entry in `TILE_FILTERS` is read and written with the rest. */
  tiles: Record<string, boolean>;
};

export const HIDDEN_ON_OWNER = new Set([
  "least_fantasy_teams",
  "highest_median",
  "lowest_median",
  "lowest_payout",
]);

export const OWNER_AWARDS = new Set([
  "lowest_start",
  "highest_start",
  "lowest_team_week",
  "highest_team_week",
  "payout_wins",
  "total_earnings",
  "median_streak",
  "median_misses",
  "most_trades",
  "projection_beater",
  "lineup_efficiency",
  "anti_projection_starts",
  "team_duo_trades",
]);

export type TileFilter = {
  awardId: string;
  param: string;
  label: string;
  /** League-wide control, which refills the list from the next rows. */
  title: string;
  /** Shown when this owner's own board empties in place. */
  localTitle?: string;
  owner: string | null;
  /** Checked when the URL does not mention this filter. */
  defaultOn?: boolean;
};

export const TILE_FILTERS: TileFilter[] = [
  {
    awardId: "least_fantasy_teams",
    param: "inactive",
    label: "Hide inactive",
    title: "Players with no fantasy points in the current season or the one before it",
    owner: null,
    defaultOn: true,
  },
  {
    awardId: "team_duo_trades",
    param: "ajay",
    label: "Hide Ajay",
    title: "Pairs that include Ajay drop out, and the next pairs fill the top 10",
    localTitle: "Pairs that include Ajay drop out",
    owner: "Ajay",
  },
  {
    awardId: "total_earnings",
    param: "keshav",
    label: "Hide Keshav",
    title: "Keshav drops out, and the next owner fills the top 10",
    localTitle: "Keshav drops out",
    owner: "Keshav",
  },
  ...(["highest_team_week", "lowest_team_week"] as const).flatMap((awardId) => [
    {
      awardId,
      param: "teamdst",
      label: "Exclude D/ST",
      title: "Leaves out the started defense. Uncheck for the full score, including 2022 and 2023.",
      owner: null,
      defaultOn: true,
    },
    {
      awardId,
      param: "consolation",
      label: "Exclude consolation",
      title: "Leaves out weeks 15–17 for eliminated teams. Uncheck to let those games count.",
      owner: null,
      defaultOn: true,
    },
  ]),
];

/** One entry per URL param. Highest and lowest team week share two of them. */
export function tileParams() {
  const seen = new Set<string>();
  return TILE_FILTERS.filter((filter) => {
    if (seen.has(filter.param)) return false;
    seen.add(filter.param);
    return true;
  });
}

export function tileApplies(filter: TileFilter, owner: string | null) {
  if (!filter.owner) return true;
  return owner === null || owner === filter.owner;
}

/** On this owner's own board the checkbox empties the tile in the browser. */
export function tileEmptiesLocally(filter: TileFilter, owner: string | null) {
  return Boolean(filter.owner && owner === filter.owner);
}

export function tileChecked(filters: SuperlativeFilters, param: string) {
  return Boolean(filters.tiles[param]);
}

export function scopeKey(fromYear: number, toYear: number, owner: string | null) {
  const span = `${fromYear}-${toYear}`;
  return owner ? `${span}@${owner}` : span;
}

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

function yearParam(
  value: string | string[] | undefined,
  fallback: number,
  currentSeason: number,
) {
  const parsed = Number(lastParam(value));
  if (!Number.isInteger(parsed)) return fallback;
  return Math.min(currentSeason, Math.max(FIRST_SEASON, parsed));
}

export function readFilters(
  search: {
    scope?: string | string[];
    from?: string | string[];
    to?: string | string[];
    owner?: string | string[];
    players?: string | string[];
    teams?: string | string[];
    dst?: string | string[];
    latest?: string | string[];
    [param: string]: string | string[] | undefined;
  },
  currentSeason: number,
): SuperlativeFilters {
  const legacy = lastParam(search.scope);
  const defaultFrom = legacy === "season" ? currentSeason : FIRST_SEASON;
  const defaultTo = currentSeason;
  let fromYear = yearParam(search.from, defaultFrom, currentSeason);
  let toYear = yearParam(search.to, defaultTo, currentSeason);
  if (fromYear > toYear) [fromYear, toYear] = [toYear, fromYear];
  const ownerName = lastParam(search.owner);
  const owner = ownerName && allOwners().includes(ownerName) ? ownerName : null;
  return {
    fromYear,
    toYear,
    owner,
    players: flag(search.players, true),
    teams: flag(search.teams, true),
    hideDefense: flag(search.dst, true),
    sortLatest: flag(search.latest, false),
    tiles: Object.fromEntries(
      TILE_FILTERS.map((filter) => [
        filter.param,
        flag(search[filter.param], Boolean(filter.defaultOn)),
      ]),
    ),
  };
}

export function filterHref(
  current: SuperlativeFilters,
  currentSeason: number,
  next: Partial<SuperlativeFilters> = {},
) {
  const fromYear = next.fromYear ?? current.fromYear;
  const toYear = next.toYear ?? current.toYear;
  const owner = next.owner === undefined ? current.owner : next.owner;
  const players = next.players ?? current.players;
  const teams = next.teams ?? current.teams;
  const hideDefense = next.hideDefense ?? current.hideDefense;
  const sortLatest = next.sortLatest ?? current.sortLatest;
  const tiles = { ...current.tiles, ...next.tiles };
  const params = new URLSearchParams();
  if (!(fromYear === FIRST_SEASON && toYear === currentSeason)) {
    params.set("from", String(fromYear));
    params.set("to", String(toYear));
  }
  if (owner) params.set("owner", owner);
  if (!players) params.set("players", "0");
  if (!teams) params.set("teams", "0");
  if (!hideDefense) params.set("dst", "0");
  if (sortLatest) params.set("latest", "1");
  for (const filter of TILE_FILTERS) {
    const on = Boolean(tiles[filter.param]);
    if (filter.defaultOn) {
      if (!on) params.set(filter.param, "0");
    } else if (on) {
      params.set(filter.param, "1");
    }
  }
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

const RATE_AWARDS = new Set(["lineup_efficiency", "projection_beater"]);

/** Movement since the previous week, for a percentage award that just changed. */
export function rateChange(place: SuperlativeRow, hideDefense: boolean): string | null {
  if (!RATE_AWARDS.has(place.category)) return null;
  const from =
    hideDefense && place.detail.hide_changed_from != null
      ? place.detail.hide_changed_from
      : place.detail.changed_from;
  if (from == null) return null;
  const delta = Math.round((place.value - from) * 10) / 10;
  if (delta === 0) return null;
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(1)}%`;
}

export function changedAt(place: SuperlativeRow, hideDefense: boolean): [number, number] {
  const detail = place.detail;
  if (
    hideDefense &&
    detail.hide_changed_season != null &&
    detail.hide_changed_week != null
  ) {
    return [detail.hide_changed_season, detail.hide_changed_week];
  }
  return [detail.changed_season ?? 0, detail.changed_week ?? 0];
}

export function boardChangedAt(
  places: SuperlativeRow[],
  hideDefense: boolean,
): [number, number] {
  for (const place of places) {
    const detail = place.detail;
    if (
      hideDefense &&
      detail.hide_board_season != null &&
      detail.hide_board_week != null
    ) {
      return [detail.hide_board_season, detail.hide_board_week];
    }
    if (!hideDefense && detail.board_season != null && detail.board_week != null) {
      return [detail.board_season, detail.board_week];
    }
  }
  return places.reduce(
    (best, place) => {
      const key = changedAt(place, hideDefense);
      if (key[0] > best[0] || (key[0] === best[0] && key[1] > best[1])) return key;
      return best;
    },
    [0, 0] as [number, number],
  );
}

export function boardAsOf(rows: SuperlativeRow[]): [number, number] {
  for (const row of rows) {
    if (row.detail.as_of_season != null && row.detail.as_of_week != null) {
      return [row.detail.as_of_season, row.detail.as_of_week];
    }
  }
  return [0, 0];
}

function isDefensePlayer(name?: string | null, pos?: string | null) {
  if (pos && DEFENSE_POS.has(pos)) return true;
  return Boolean(name && /\bD\/ST\b/.test(name));
}

function withAlternates(rows: SuperlativeRow[]) {
  const ranked = [...rows].sort((left, right) => left.rank - right.rank);
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
  return [...ranked, ...alternates];
}

export function starterRows(
  rows: SuperlativeRow[],
  hideDefense: boolean,
  limit = 10,
) {
  const pool = hideDefense ? withAlternates(rows) : [...rows].sort((left, right) => left.rank - right.rank);
  const adjusted = pool.flatMap((row) => {
    const starters = (row.detail.starters ?? []).filter(
      (starter) => !hideDefense || !isDefensePlayer(starter.name, starter.pos),
    );
    if (hideDefense && starters.length === 0) return [];
    const count = hideDefense ? starters.length : row.value;
    const noun = count === 1 ? "starter" : "starters";
    const { alternates: _alternates, ...detail } = row.detail;
    return [
      {
        ...row,
        value: count,
        display: hideDefense
          ? `${count} ${noun} · ${detail.season} Wk ${detail.week}`
          : row.display,
        detail: { ...detail, starters },
      },
    ];
  });
  if (hideDefense) {
    adjusted.sort(
      (left, right) =>
        right.value - left.value ||
        (left.detail.season ?? 0) - (right.detail.season ?? 0) ||
        (left.detail.week ?? 0) - (right.detail.week ?? 0) ||
        left.subject_name.localeCompare(right.subject_name),
    );
  }
  return adjusted.slice(0, limit).map((row, index) => ({ ...row, rank: index + 1 }));
}

function lastPointsSeason(detail: SuperlativeDetail) {
  return (detail.seasons ?? []).reduce((latest, season) => Math.max(latest, season.season), 0);
}

/** Scored in the current season or the one before it. Older totals are treated as inactive. */
export function isActiveFantasyPlayer(detail: SuperlativeDetail, currentSeason: number) {
  const last = lastPointsSeason(detail);
  if (last <= 0) return true;
  return last >= currentSeason - 1;
}

function pairIncludes(row: SuperlativeRow, owner: string) {
  if (row.detail.player_name === owner || row.detail.partner_name === owner) return true;
  if (row.subject_key.split("|").includes(owner)) return true;
  return row.subject_name.split(" & ").includes(owner);
}

/** Top pairs, with Ajay's deals removed and the next pairs moved up. */
export function duoTradeRows(rows: SuperlativeRow[], hideAjay: boolean, limit = 10) {
  const ranked = [...rows].sort((left, right) => left.rank - right.rank);
  if (!hideAjay) return ranked.slice(0, limit);
  const pool = withAlternates(ranked).filter((row) => !pairIncludes(row, "Ajay"));
  return pool.slice(0, limit).map((row, index) => {
    const { alternates: _alternates, ...detail } = row.detail;
    return { ...row, rank: index + 1, detail };
  });
}

export function leastTeamRows(
  rows: SuperlativeRow[],
  hideInactive: boolean,
  currentSeason: number,
  limit = 10,
) {
  const ranked = [...rows].sort((left, right) => left.rank - right.rank);
  const pool = hideInactive
    ? withAlternates(ranked).filter((row) => isActiveFantasyPlayer(row.detail, currentSeason))
    : ranked;
  return pool.slice(0, limit).map((row, index) => {
    const { alternates: _alternates, ...detail } = row.detail;
    return { ...row, rank: index + 1, detail };
  });
}

function teamWeekBoardKey(excludeDst: boolean, excludeConsolation: boolean) {
  if (excludeDst && excludeConsolation) return null;
  if (!excludeDst && excludeConsolation) return "full_scores";
  if (excludeDst && !excludeConsolation) return "with_consolation";
  return "full_with_consolation";
}

/** Highest and lowest team week. The stored list excludes D/ST and consolation. */
export function teamWeekRows(
  rows: SuperlativeRow[],
  excludeDst: boolean,
  excludeConsolation: boolean,
  limit = 10,
) {
  const ranked = [...rows].sort((left, right) => left.rank - right.rank);
  const leader = ranked[0];
  if (!leader) return [];
  const stored = ranked.slice(0, limit).map((row, index) => {
    const { boards: _boards, alternates: _alternates, ...detail } = row.detail;
    return { ...row, rank: index + 1, detail };
  });
  const key = teamWeekBoardKey(excludeDst, excludeConsolation);
  const board = key ? leader.detail.boards?.[key] : null;
  if (!key || !board) return stored;
  return board.slice(0, limit).map((alt, index) => ({
    category: leader.category,
    scope: leader.scope,
    rank: index + 1,
    subject_type: alt.subject_type,
    subject_key: String(alt.subject_key),
    subject_name: alt.subject_name,
    value: Number(alt.value),
    display: alt.display,
    detail: alt.detail ?? {},
  }));
}

export function podiumRows(
  rows: SuperlativeRow[],
  hideDefense: boolean,
  limit = 3,
) {
  const ranked = [...rows].sort((left, right) => left.rank - right.rank);
  const leader = ranked[0];
  const alternates =
    hideDefense && leader
      ? (leader.detail.alternates ?? []).map((alt, index) => ({
          category: leader.category,
          scope: leader.scope,
          rank: ranked.length + index + 1,
          subject_type: alt.subject_type,
          subject_key: String(alt.subject_key),
          subject_name: alt.subject_name,
          value: Number(alt.value),
          display: alt.display,
          detail: alt.detail ?? {},
        }))
      : [];
  const pool = hideDefense
    ? [...ranked, ...alternates].filter(
        (row) => !isDefenseSubject(row.subject_name, row.detail),
      )
    : ranked;
  return pool.slice(0, limit).map((row, index) => ({ ...row, rank: index + 1 }));
}
