const SUPABASE_URL =
  process.env.NEXT_PUBLIC_SUPABASE_URL ??
  "https://jdfdpbgqiigkjatzudle.supabase.co";

export function logoPublicUrl(path: string | null | undefined) {
  if (!path) return null;
  return `${SUPABASE_URL}/storage/v1/object/public/logos/${path}`;
}

export const PLAYER_SEASONS_URL = logoPublicUrl("player-records/seasons.json");

const ESPN_TO_PFR: Record<string, string> = {
  NE: "nwe",
  BAL: "rav",
  HOU: "htx",
  IND: "clt",
  TEN: "oti",
  KC: "kan",
  LAC: "sdg",
  LV: "rai",
  WSH: "was",
  WAS: "was",
  GB: "gnb",
  TB: "tam",
  NO: "nor",
  ARI: "crd",
  LAR: "ram",
  SF: "sfo",
};

function nflLogoPath(espnAbbrev: string) {
  const upper = espnAbbrev.toUpperCase();
  const slug = ESPN_TO_PFR[upper] ?? upper.toLowerCase();
  return `nfl/${slug}.png`;
}

export function nflLogoUrl(espnAbbrev: string) {
  return logoPublicUrl(nflLogoPath(espnAbbrev));
}

export function teamNameKey(name: string) {
  return name.trim().replace(/\s+/g, " ").toLowerCase();
}

export type FantasyLogoRow = {
  season: number;
  team_name: string;
  logo_path: string | null;
};

/** Prefer a stored path, then the catalog row for that season + team name. */
export function resolveTeamLogoPath(
  team: string,
  season: number | undefined,
  catalog: FantasyLogoRow[],
  stored?: string | null,
) {
  if (stored) return stored;
  if (season == null) return null;
  const key = teamNameKey(team);
  const match = catalog.find(
    (row) =>
      row.season === season &&
      row.logo_path &&
      teamNameKey(row.team_name) === key,
  );
  return match?.logo_path ?? null;
}
