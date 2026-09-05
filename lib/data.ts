import { cache } from "react";
import { getSupabase } from "./supabase";
import {
  PLAYER_SEASONS_URL,
  resolveTeamLogoPath,
  type FantasyLogoRow,
} from "./logos";
import { parseSeasons, type PlayerRecord, type PlayerSeason } from "./player-records";
import type { TradeRow } from "./trades";

export type ReportRow = {
  id: string;
  last_updated: string;
  season: number | null;
  current_week: number | null;
  through_season: number | null;
  through_week: number | null;
  titles_through_season: number | null;
  min_starts: number | null;
};

export type MedianPull = {
  id: string;
  pulled_at: string;
  season: number;
  week: number;
};

export type MedianStanding = {
  pull_id: string;
  team: string;
  rank: number;
  current: number;
  projection: number;
  median: number;
  payout: number;
  logo_path: string | null;
};

export const getReport = cache(async (id: string): Promise<ReportRow | null> => {
  const supabase = getSupabase();
  if (!supabase) return null;
  const { data, error } = await supabase
    .from("reports")
    .select("*")
    .eq("id", id)
    .maybeSingle();
  if (error) {
    console.error(error.message);
    return null;
  }
  return data as ReportRow | null;
});

export async function getMedianHistory(): Promise<{
  pulls: MedianPull[];
  standings: MedianStanding[];
}> {
  const supabase = getSupabase();
  if (!supabase) return { pulls: [], standings: [] };

  const pullsRes = await supabase
    .from("median_pulls")
    .select("id, pulled_at, season, week")
    .order("pulled_at", { ascending: false });
  if (pullsRes.error) {
    console.error(pullsRes.error.message);
    return { pulls: [], standings: [] };
  }
  const pulls = (pullsRes.data ?? []) as MedianPull[];
  if (!pulls.length) return { pulls: [], standings: [] };

  const [standingsRes, logosRes] = await Promise.all([
    supabase
      .from("median_standings")
      .select("pull_id, team, rank, current, projection, median, payout, logo_path"),
    supabase.from("fantasy_logos").select("season, team_name, logo_path"),
  ]);
  if (standingsRes.error) {
    console.error(standingsRes.error.message);
    return { pulls, standings: [] };
  }
  if (logosRes.error) console.error(logosRes.error.message);

  const catalog = (logosRes.data ?? []) as FantasyLogoRow[];
  const seasonByPull = new Map(pulls.map((pull) => [pull.id, pull.season]));
  const standings = ((standingsRes.data ?? []) as MedianStanding[]).map((row) => ({
    ...row,
    logo_path: resolveTeamLogoPath(
      row.team,
      seasonByPull.get(row.pull_id),
      catalog,
      row.logo_path,
    ),
  }));
  return { pulls, standings };
}

async function getSeasonMap(): Promise<Record<string, PlayerSeason[]>> {
  if (!PLAYER_SEASONS_URL) return {};
  try {
    const res = await fetch(PLAYER_SEASONS_URL, { next: { revalidate: 86400 } });
    if (!res.ok) return {};
    const raw = (await res.json()) as Record<string, unknown>;
    const out: Record<string, PlayerSeason[]> = {};
    for (const [name, seasons] of Object.entries(raw)) {
      out[name] = parseSeasons(seasons);
    }
    return out;
  } catch (error) {
    console.error(error);
    return {};
  }
}

export async function getPlayerRecords(): Promise<{
  report: ReportRow | null;
  players: PlayerRecord[];
}> {
  const supabase = getSupabase();
  if (!supabase) return { report: null, players: [] };

  const [report, playersRes, seasonMap] = await Promise.all([
    getReport("player-records"),
    supabase.from("player_records").select("*"),
    getSeasonMap(),
  ]);
  if (playersRes.error) {
    console.error(playersRes.error.message);
    return { report, players: [] };
  }
  const players = (playersRes.data ?? []).map((row) => {
    const fromColumn = parseSeasons(row.seasons);
    return {
      name: row.name as string,
      pos: row.pos as string,
      teams: (row.teams ?? []) as string[],
      g: Number(row.g),
      w: Number(row.w),
      gs: Number(row.gs),
      ws: Number(row.ws),
      pg: Number(row.pg),
      pw: Number(row.pw),
      pgs: Number(row.pgs),
      pws: Number(row.pws),
      titles: Number(row.titles),
      winPct: Number(row.g) > 0 ? Number(row.w) / Number(row.g) : 0,
      seasons: fromColumn.length ? fromColumn : (seasonMap[row.name as string] ?? []),
    };
  });
  return { report, players };
}

export async function getTrades(): Promise<{
  report: ReportRow | null;
  trades: TradeRow[];
}> {
  const supabase = getSupabase();
  if (!supabase) return { report: null, trades: [] };

  const [report, tradesRes] = await Promise.all([
    getReport("trade-o-gami"),
    supabase.from("trades").select("id, season, week, owners").order("season"),
  ]);
  if (tradesRes.error) {
    console.error(tradesRes.error.message);
    return { report, trades: [] };
  }
  const trades = (tradesRes.data ?? []).map((row) => ({
    id: row.id as string,
    season: Number(row.season),
    week: Number(row.week),
    owners: (row.owners ?? []) as string[],
  }));
  return { report, trades };
}
