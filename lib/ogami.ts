export type TeamWeekSide = {
  season: number;
  week: number;
  owner: string;
  opponent: string;
  points: number;
  isRegular: boolean;
  isConsolation: boolean;
};

export type OwnerGame = {
  season: number;
  week: number;
  a: string;
  b: string;
  winner: string | null;
  playoff: boolean;
};

export type RecordCell = {
  w: number;
  l: number;
  t: number;
};

function pairKey(a: string, b: string): [string, string] {
  return a < b ? [a, b] : [b, a];
}

function usableName(name: string) {
  return Boolean(name) && name !== "N/A" && name !== "Unknown";
}

/** One game per week. A side stored without its opponent is skipped. */
export function pairGames(rows: TeamWeekSide[]): OwnerGame[] {
  const grouped = new Map<string, TeamWeekSide[]>();
  for (const row of rows) {
    if (row.isConsolation) continue;
    if (!usableName(row.owner) || !usableName(row.opponent)) continue;
    if (row.owner === row.opponent) continue;
    if (!Number.isFinite(row.points)) continue;
    const [a, b] = pairKey(row.owner, row.opponent);
    const key = `${row.season}\0${row.week}\0${a}\0${b}`;
    const sides = grouped.get(key) ?? [];
    sides.push(row);
    grouped.set(key, sides);
  }

  const games: OwnerGame[] = [];
  for (const [key, sides] of grouped) {
    const [season, week, a, b] = key.split("\0");
    const sideA = sides.find((side) => side.owner === a);
    const sideB = sides.find((side) => side.owner === b);
    if (!sideA || !sideB) continue;
    let winner: string | null = null;
    if (sideA.points > sideB.points) winner = a;
    else if (sideB.points > sideA.points) winner = b;
    games.push({
      season: Number(season),
      week: Number(week),
      a,
      b,
      winner,
      playoff: !sideA.isRegular && !sideB.isRegular,
    });
  }
  return games;
}

export function countMatrix(
  owners: string[],
  pairs: { a: string; b: string; count: number }[],
): number[][] {
  const index = new Map(owners.map((name, i) => [name, i]));
  const matrix = owners.map(() => owners.map(() => 0));
  for (const pair of pairs) {
    const i = index.get(pair.a);
    const j = index.get(pair.b);
    if (i == null || j == null) continue;
    matrix[i][j] = pair.count;
    matrix[j][i] = pair.count;
  }
  return matrix;
}

export function h2hMatrix(
  owners: string[],
  games: OwnerGame[],
  ownerSet: Set<string>,
): RecordCell[][] {
  const index = new Map(owners.map((name, i) => [name, i]));
  const matrix = owners.map(() => owners.map(() => ({ w: 0, l: 0, t: 0 })));
  for (const game of games) {
    if (!ownerSet.has(game.a) || !ownerSet.has(game.b)) continue;
    const i = index.get(game.a);
    const j = index.get(game.b);
    if (i == null || j == null) continue;
    if (game.winner === game.a) {
      matrix[i][j].w += 1;
      matrix[j][i].l += 1;
    } else if (game.winner === game.b) {
      matrix[j][i].w += 1;
      matrix[i][j].l += 1;
    } else {
      matrix[i][j].t += 1;
      matrix[j][i].t += 1;
    }
  }
  return matrix;
}

/** Winners-bracket games only. Both triangles hold the same count. */
export function playoffMatrix(
  owners: string[],
  games: OwnerGame[],
  ownerSet: Set<string>,
): number[][] {
  const index = new Map(owners.map((name, i) => [name, i]));
  const matrix = owners.map(() => owners.map(() => 0));
  for (const game of games) {
    if (!game.playoff) continue;
    if (!ownerSet.has(game.a) || !ownerSet.has(game.b)) continue;
    const i = index.get(game.a);
    const j = index.get(game.b);
    if (i == null || j == null) continue;
    matrix[i][j] += 1;
    matrix[j][i] += 1;
  }
  return matrix;
}

export function gamesPlayed(cell: RecordCell) {
  return cell.w + cell.l + cell.t;
}

export function recordLabel(cell: RecordCell) {
  if (cell.t > 0) return `${cell.w}-${cell.l}-${cell.t}`;
  return `${cell.w}-${cell.l}`;
}
