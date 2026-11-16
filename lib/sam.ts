export type SamPlayerWeek = {
  season: number;
  week: number;
  teamId: number;
  playerId: number;
  pos: string | null;
  lineupSlot: string | null;
  started: boolean;
  points: number;
};

export type SamTeamWeek = {
  season: number;
  week: number;
  teamId: number;
  teamName: string;
  points: number;
  isRegular: boolean;
};

export type AccuracyBar = {
  teamId: number;
  teamName: string;
  actual: number;
  optimal: number;
  ratio: number;
  actualLabel: string;
  optimalLabel: string;
  percentLabel: string;
};

export type ExpectedRecordRow = {
  teamId: number;
  teamName: string;
  wins: number;
  losses: number;
  /** Expected wins for each week in SamSeasonView.weeks. Null if the team has no score. */
  weekly: (number | null)[];
};

export type SamSeasonView = {
  season: number;
  weeks: number[];
  accuracy: AccuracyBar[];
  expected: ExpectedRecordRow[];
};

const POSITION_SLOTS: [string, number][] = [
  ["QB", 1],
  ["RB", 2],
  ["WR", 2],
  ["TE", 1],
];
const FLEX_POSITIONS = new Set(["RB", "WR", "TE"]);
const FLEX_SLOTS = 2;

function isDefense(player: SamPlayerWeek): boolean {
  const slot = player.lineupSlot?.trim();
  if (slot) return slot === "D/ST" || slot === "DST";
  const pos = player.pos?.trim() ?? "";
  return pos === "D/ST" || pos === "DST";
}

function byPoints(a: SamPlayerWeek, b: SamPlayerWeek): number {
  return b.points - a.points || a.playerId - b.playerId;
}

export function actualPoints(players: SamPlayerWeek[]): number {
  let total = 0;
  for (const player of players) {
    if (player.started && !isDefense(player)) total += player.points;
  }
  return total;
}

/** Best QB/RB/WR/TE/flex lineup. Defense and kicker never fill a slot. */
export function optimalPoints(players: SamPlayerWeek[]): number {
  const used = new Set<number>();
  let total = 0;
  for (const [pos, slots] of POSITION_SLOTS) {
    const ranked = players
      .filter((player) => (player.pos?.trim() ?? "") === pos && !used.has(player.playerId))
      .sort(byPoints);
    for (const player of ranked.slice(0, slots)) {
      used.add(player.playerId);
      total += player.points;
    }
  }
  const flex = players
    .filter(
      (player) =>
        FLEX_POSITIONS.has(player.pos?.trim() ?? "") && !used.has(player.playerId),
    )
    .sort(byPoints)
    .slice(0, FLEX_SLOTS);
  for (const player of flex) total += player.points;
  return total;
}

export function formatSamPoints(value: number): string {
  return (Math.round(value * 10) / 10).toFixed(1);
}

function percentLabel(actual: number, optimal: number): string {
  if (optimal <= 0) return "";
  const rounded = Math.round((actual / optimal) * 100) / 100;
  return `${(rounded * 100).toFixed(1)}%`;
}

function rememberName(
  names: Map<number, { week: number; name: string }>,
  row: SamTeamWeek,
) {
  const current = names.get(row.teamId);
  const name = row.teamName.trim();
  if (!current || row.week > current.week) {
    names.set(row.teamId, { week: row.week, name: name || `Team ${row.teamId}` });
    return;
  }
  if (row.week === current.week && name) {
    names.set(row.teamId, { week: row.week, name });
  }
}

export function samSeason(
  season: number,
  players: SamPlayerWeek[],
  teams: SamTeamWeek[],
): { accuracy: AccuracyBar[]; weeks: number[]; expected: ExpectedRecordRow[] } {
  const regular = teams.filter((row) => row.season === season && row.isRegular);
  const regularKeys = new Set(regular.map((row) => `${row.week}:${row.teamId}`));
  const byTeamWeek = new Map<string, SamPlayerWeek[]>();
  for (const player of players) {
    if (player.season !== season) continue;
    const key = `${player.week}:${player.teamId}`;
    if (!regularKeys.has(key)) continue;
    const list = byTeamWeek.get(key) ?? [];
    list.push(player);
    byTeamWeek.set(key, list);
  }

  const names = new Map<number, { week: number; name: string }>();
  const sums = new Map<number, { actual: number; optimal: number }>();
  for (const row of regular) {
    rememberName(names, row);
    const roster = byTeamWeek.get(`${row.week}:${row.teamId}`) ?? [];
    const bucket = sums.get(row.teamId) ?? { actual: 0, optimal: 0 };
    bucket.actual += actualPoints(roster);
    bucket.optimal += optimalPoints(roster);
    sums.set(row.teamId, bucket);
  }

  const accuracy: AccuracyBar[] = [];
  for (const [teamId, bucket] of sums) {
    if (bucket.optimal <= 0 && bucket.actual <= 0) continue;
    const ratio = bucket.optimal > 0 ? bucket.actual / bucket.optimal : 0;
    accuracy.push({
      teamId,
      teamName: names.get(teamId)?.name ?? `Team ${teamId}`,
      actual: bucket.actual,
      optimal: bucket.optimal,
      ratio,
      actualLabel: formatSamPoints(bucket.actual),
      optimalLabel: formatSamPoints(bucket.optimal),
      percentLabel: percentLabel(bucket.actual, bucket.optimal),
    });
  }
  accuracy.sort(
    (a, b) => b.ratio - a.ratio || a.teamName.localeCompare(b.teamName),
  );

  const byWeek = new Map<number, SamTeamWeek[]>();
  for (const row of regular) {
    const list = byWeek.get(row.week) ?? [];
    list.push(row);
    byWeek.set(row.week, list);
  }
  const weeks = [...byWeek.keys()].sort((a, b) => a - b);
  const winSums = new Map<number, number>();
  const lossSums = new Map<number, number>();
  const weekShares = new Map<string, number>();
  for (const week of weeks) {
    const weekRows = byWeek.get(week) ?? [];
    const others = weekRows.length - 1;
    for (const row of weekRows) {
      let beaten = 0;
      let lost = 0;
      for (const other of weekRows) {
        if (other.teamId === row.teamId) continue;
        if (other.points < row.points) beaten += 1;
        else if (other.points > row.points) lost += 1;
      }
      const winShare = others > 0 ? beaten / others : 0;
      const lossShare = others > 0 ? lost / others : 0;
      winSums.set(row.teamId, (winSums.get(row.teamId) ?? 0) + winShare);
      lossSums.set(row.teamId, (lossSums.get(row.teamId) ?? 0) + lossShare);
      weekShares.set(`${row.teamId}:${week}`, winShare);
    }
  }
  const expected: ExpectedRecordRow[] = [...winSums.keys()].map((teamId) => ({
    teamId,
    teamName: names.get(teamId)?.name ?? `Team ${teamId}`,
    wins: winSums.get(teamId) ?? 0,
    losses: lossSums.get(teamId) ?? 0,
    weekly: weeks.map((week) => weekShares.get(`${teamId}:${week}`) ?? null),
  }));
  expected.sort(
    (a, b) => b.wins - a.wins || a.losses - b.losses || a.teamName.localeCompare(b.teamName),
  );

  return { accuracy, weeks, expected };
}

export function samViews(
  players: SamPlayerWeek[],
  teams: SamTeamWeek[],
): SamSeasonView[] {
  const seasons = new Set<number>();
  for (const row of teams) {
    if (row.isRegular) seasons.add(row.season);
  }
  return [...seasons]
    .sort((a, b) => b - a)
    .map((season) => ({ season, ...samSeason(season, players, teams) }));
}
