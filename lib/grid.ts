import league from "@/data/league.json";
import { nflLogoUrl } from "@/lib/logos";

export const GUESSES = 9;
export const PRIOR_FILLS = 12;
export const ESTIMATE_UNDER = 8;

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const ISO_RE = /^\d{4}-\d{2}-\d{2}$/;

export const FRANCHISES: { abbrev: string; name: string }[] = [
  { abbrev: "ARI", name: "Cardinals" },
  { abbrev: "ATL", name: "Falcons" },
  { abbrev: "BAL", name: "Ravens" },
  { abbrev: "BUF", name: "Bills" },
  { abbrev: "CAR", name: "Panthers" },
  { abbrev: "CHI", name: "Bears" },
  { abbrev: "CIN", name: "Bengals" },
  { abbrev: "CLE", name: "Browns" },
  { abbrev: "DAL", name: "Cowboys" },
  { abbrev: "DEN", name: "Broncos" },
  { abbrev: "DET", name: "Lions" },
  { abbrev: "GB", name: "Packers" },
  { abbrev: "HOU", name: "Texans" },
  { abbrev: "IND", name: "Colts" },
  { abbrev: "JAX", name: "Jaguars" },
  { abbrev: "KC", name: "Chiefs" },
  { abbrev: "LAC", name: "Chargers" },
  { abbrev: "LAR", name: "Rams" },
  { abbrev: "LV", name: "Raiders" },
  { abbrev: "MIA", name: "Dolphins" },
  { abbrev: "MIN", name: "Vikings" },
  { abbrev: "NE", name: "Patriots" },
  { abbrev: "NO", name: "Saints" },
  { abbrev: "NYG", name: "Giants" },
  { abbrev: "NYJ", name: "Jets" },
  { abbrev: "PHI", name: "Eagles" },
  { abbrev: "PIT", name: "Steelers" },
  { abbrev: "SEA", name: "Seahawks" },
  { abbrev: "SF", name: "49ers" },
  { abbrev: "TB", name: "Buccaneers" },
  { abbrev: "TEN", name: "Titans" },
  { abbrev: "WSH", name: "Commanders" },
];

const FRANCHISE_NOTES: Record<string, string> = {
  TEN: "Played a game for the Titans, including the Oilers",
  LAC: "Played a game for the Chargers, including San Diego",
  LV: "Played a game for the Raiders, including Oakland and Los Angeles",
  LAR: "Played a game for the Rams, including St. Louis and Los Angeles",
};

const ACHIEVEMENTS: Record<string, { line1: string; line2: string; detail: string }> = {
  "season:qb:1": { line1: "#1", line2: "QB", detail: "Finished as the QB1" },
  "season:qb:top5": { line1: "Top 5", line2: "QB", detail: "Top 5 quarterback finish" },
  "season:qb:top12": { line1: "Top 12", line2: "QB", detail: "Top 12 quarterback finish" },
  "season:rb:1": { line1: "#1", line2: "RB", detail: "Finished as the RB1" },
  "season:rb:top10": { line1: "Top 10", line2: "RB", detail: "Top 10 running back finish" },
  "season:rb:top24": { line1: "Top 24", line2: "RB", detail: "Top 24 running back finish" },
  "season:wr:1": { line1: "#1", line2: "WR", detail: "Finished as the WR1" },
  "season:wr:top10": { line1: "Top 10", line2: "WR", detail: "Top 10 wide receiver finish" },
  "season:wr:top24": { line1: "Top 24", line2: "WR", detail: "Top 24 wide receiver finish" },
  "season:te:1": { line1: "#1", line2: "TE", detail: "Finished as the TE1" },
  "season:te:top5": { line1: "Top 5", line2: "TE", detail: "Top 5 tight end finish" },
  "season:te:top12": { line1: "Top 12", line2: "TE", detail: "Top 12 tight end finish" },
  "season:ppr300": { line1: "300+", line2: "season", detail: "300 or more PPR points in a season" },
  "season:ppr200": { line1: "200+", line2: "season", detail: "200 or more PPR points in a season" },
  "game:50": { line1: "50+", line2: "game", detail: "50 or more PPR points in a game" },
  "game:40": { line1: "40+", line2: "game", detail: "40 or more PPR points in a game" },
  "game:30": { line1: "30+", line2: "game", detail: "30 or more PPR points in a game" },
};

export type GridHeader = {
  label: string;
  line2: string;
  detail: string;
  logo: string | null;
};

export type GridGuess = {
  cell: number;
  playerId: string;
  name: string;
  pos: string;
  correct: boolean;
};

export type CellResult = {
  percent: number;
  estimated: boolean;
};

export type GridResults = {
  cells: (CellResult | null)[];
  score: number;
  others: number;
};

export type GridArchiveDay = {
  date: string;
  finished: boolean;
};

export type Board = {
  playable: boolean;
  date: string | null;
  today: string;
  start: string;
  end: string;
  nextDrop: string | null;
  throughSeason: number;
  offseason: boolean;
  rows: GridHeader[];
  cols: GridHeader[];
  guesses: GridGuess[];
  guessesLeft: number;
  finished: boolean;
  givenUp: boolean;
  results: GridResults | null;
  archive: GridArchiveDay[];
};

export type SearchHit = {
  id: string;
  name: string;
  pos: string;
  years: string;
};

export function isUuid(value: string) {
  return UUID_RE.test(value);
}

export function isIsoDate(value: string) {
  if (!ISO_RE.test(value)) return false;
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day
  );
}

export function todayET(now = new Date()) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

function utcDate(year: number, month: number, day: number) {
  return new Date(Date.UTC(year, month - 1, day));
}

function isoFromDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

/** Thursday of NFL week 1. Stored dates win. Later seasons use the Thursday after Labor Day. */
export function openingThursday(season: number) {
  const stored =
    league.week1_thursday?.[String(season) as keyof typeof league.week1_thursday];
  if (stored) return stored;
  const septemberFirst = utcDate(season, 9, 1).getUTCDay();
  const laborDay = 1 + ((1 - septemberFirst + 7) % 7);
  return isoFromDate(utcDate(season, 9, laborDay + 3));
}

export function seasonEnd(season: number) {
  const [year, month, day] = openingThursday(season).split("-").map(Number);
  return isoFromDate(utcDate(year, month, day + 122));
}

export function latestCompletedSeason(today: string) {
  const year = Number(today.slice(0, 4));
  for (const season of [year, year - 1, year - 2]) {
    if (today > seasonEnd(season)) return season;
  }
  return year - 2;
}

export function defaultGridDate(today: string, start: string, end: string) {
  if (today < start) return null;
  if (today > end) return end;
  return today;
}

export function isPlayableDate(date: string, today: string, start: string, end: string) {
  if (today < start) return false;
  const last = today < end ? today : end;
  return date >= start && date <= last;
}

export function nextGridDrop(today: string, start: string, end: string) {
  if (today < start) return start;
  if (today > end) return openingThursday(Number(start.slice(0, 4)) + 1);
  return null;
}

export function foldName(name: string) {
  return name
    .toLowerCase()
    .replace(/['’.]/g, "")
    .replace(/-/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function searchNeedle(query: string) {
  return foldName(query).replace(/[%_\\,]/g, "").trim();
}

export function careerYears(yearMin: number, yearMax: number) {
  return yearMin === yearMax ? String(yearMin) : `${yearMin}–${yearMax}`;
}

export function describeTag(tag: string, throughSeason: number): GridHeader {
  if (tag.startsWith("team:")) {
    const abbrev = tag.slice(5);
    const franchise = FRANCHISES.find((team) => team.abbrev === abbrev);
    const name = franchise?.name ?? abbrev;
    return {
      label: name,
      line2: "",
      detail: FRANCHISE_NOTES[abbrev] ?? `Played a regular-season or playoff game for the ${name}`,
      logo: nflLogoUrl(abbrev),
    };
  }
  const achievement = ACHIEVEMENTS[tag];
  if (!achievement) {
    return { label: tag, line2: "", detail: tag, logo: null };
  }
  return {
    label: achievement.line1,
    line2: achievement.line2,
    detail: `${achievement.detail}, 1999–${throughSeason}`,
    logo: null,
  };
}

export function fameWeight(value: number) {
  const fame = Number(value);
  if (!Number.isFinite(fame) || fame < 1) return 1;
  return fame;
}

/** Blends real picks with a career-points prior. Under 8 fills, it is an estimate. */
export function blendedRarity(input: {
  picks: number;
  fills: number;
  fame: number;
  fameTotal: number;
}) {
  const fame = fameWeight(input.fame);
  const total = input.fameTotal > 0 ? input.fameTotal : fame;
  const share = fame / total;
  const percent =
    ((input.picks + PRIOR_FILLS * share) / (input.fills + PRIOR_FILLS)) * 100;
  return {
    percent,
    estimated: input.fills < ESTIMATE_UNDER,
  };
}

export function rarityScore(percents: (number | null)[]) {
  return percents.reduce<number>((sum, value) => sum + (value ?? 100), 0);
}

export function formatPercent(percent: number, estimated: boolean) {
  const text = `${percent.toFixed(1)}%`;
  return estimated ? `${text} est.` : text;
}

export function formatScore(score: number) {
  return score.toFixed(1);
}

export function rarityClass(percent: number) {
  if (percent < 5) return "text-amber-700";
  if (percent < 20) return "text-emerald-800";
  return "text-neutral-500";
}

export function formatGridDate(iso: string, options: Intl.DateTimeFormatOptions) {
  const [year, month, day] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat("en-US", { ...options, timeZone: "UTC" }).format(
    new Date(Date.UTC(year, month - 1, day)),
  );
}
