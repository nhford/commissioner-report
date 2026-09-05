export type PlayerSeasonFantasy = {
  owner: string;
  team: string;
};

export type PlayerSeason = {
  year: number;
  fantasy: PlayerSeasonFantasy[];
  nfl: string[];
  gs: number;
  avgStarterPts: number | null;
};

export type PlayerRecord = {
  name: string;
  pos: string;
  teams: string[];
  g: number;
  w: number;
  gs: number;
  ws: number;
  pg: number;
  pw: number;
  pgs: number;
  pws: number;
  titles: number;
  winPct: number;
  seasons: PlayerSeason[];
};

export function formatFantasyTeam(entry: PlayerSeasonFantasy) {
  if (entry.owner && entry.team) return `${entry.owner} (${entry.team})`;
  return entry.owner || entry.team || "Unknown";
}

export function parseSeasons(raw: unknown): PlayerSeason[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => {
      const row = item as Partial<PlayerSeason>;
      const avg = row.avgStarterPts;
      return {
        year: Number(row.year),
        fantasy: Array.isArray(row.fantasy)
          ? row.fantasy.map((entry) => ({
              owner: String(entry.owner ?? ""),
              team: String(entry.team ?? ""),
            }))
          : [],
        nfl: Array.isArray(row.nfl) ? row.nfl.map(String) : [],
        gs: Number(row.gs) || 0,
        avgStarterPts:
          avg == null || Number.isNaN(Number(avg)) ? null : Number(avg),
      };
    })
    .filter((row) => Number.isFinite(row.year))
    .sort((a, b) => a.year - b.year);
}

export const DEFAULT_MIN_STARTS = 17;
export const SPECIAL_MIN_STARTS = {
  undefeated: 3,
  winless: 3,
} as const;
export const POSITION_ORDER = ["QB", "RB", "WR", "TE", "K", "D/ST"] as const;

export type SpecialRecordFilter = "undefeated" | "winless" | null;

export function starterWinPct(player: PlayerRecord) {
  return player.gs > 0 ? player.ws / player.gs : 0;
}

/** First-seen NFL teams, in order. The scrape is a trail, so a club can repeat. */
export function uniqueTeams(teams: string[]) {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const team of teams) {
    if (!team || seen.has(team)) continue;
    seen.add(team);
    out.push(team);
  }
  return out;
}

export function positionOptions(players: PlayerRecord[]) {
  const seen = new Set(players.map((player) => player.pos).filter(Boolean));
  const known = POSITION_ORDER.filter((pos) => seen.has(pos));
  const extra = [...seen]
    .filter((pos) => !POSITION_ORDER.includes(pos as (typeof POSITION_ORDER)[number]))
    .sort((a, b) => a.localeCompare(b));
  return ["All", ...known, ...extra];
}

export function filterPlayers(
  players: PlayerRecord[],
  query: string,
  pos: string,
  minStarts: number,
  special: SpecialRecordFilter = null,
) {
  const needle = query.trim().toLowerCase();
  return players.filter((player) => {
    if (player.gs < minStarts) return false;
    if (pos !== "All" && player.pos !== pos) return false;
    if (needle && !player.name.toLowerCase().includes(needle)) return false;
    if (special === "undefeated" && player.ws !== player.gs) return false;
    if (special === "winless" && player.ws !== 0) return false;
    return true;
  });
}
