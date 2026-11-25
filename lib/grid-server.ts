import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import league from "@/data/league.json";
import {
  GUESSES,
  type Board,
  type CellResult,
  type GridGuess,
  type GridHeader,
  type SearchHit,
  blendedRarity,
  careerYears,
  defaultGridDate,
  describeTag,
  fameWeight,
  isIsoDate,
  isPlayableDate,
  isUuid,
  latestCompletedSeason,
  nextGridDrop,
  rarityScore,
  searchNeedle,
  todayET,
} from "@/lib/grid";

export class GridError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

type StoredGuess = {
  cell: number;
  player_id: string;
  correct: boolean;
  created_at: string;
};

type PlayerRow = {
  id: string;
  name: string;
  pos: string;
  year_min?: number;
  year_max?: number;
  fame?: number;
};

function database() {
  const url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new GridError("The grid is not configured.", 503);
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

function unwrap<T>(result: { data: T; error: { message: string } | null }) {
  if (result.error) {
    console.error(result.error.message);
    if (result.error.message.includes("schema cache")) {
      throw new GridError("The grid tables are not in the database yet.", 503);
    }
    throw new GridError("The grid is unavailable.", 500);
  }
  return result.data;
}

function requireAnon(anonId: string | null) {
  if (!anonId || !isUuid(anonId)) {
    throw new GridError("Missing a player id for this browser.", 400);
  }
  return anonId;
}

function windowFor(today: string) {
  const start = league.grid.start;
  const end = league.grid.end;
  return {
    start,
    end,
    today,
    throughSeason: latestCompletedSeason(today),
    nextDrop: nextGridDrop(today, start, end),
    offseason: today < start || today > end,
  };
}

function emptyBoard(anonToday = todayET()): Board {
  const season = windowFor(anonToday);
  return {
    playable: false,
    date: null,
    today: season.today,
    start: season.start,
    end: season.end,
    nextDrop: season.nextDrop,
    throughSeason: season.throughSeason,
    offseason: season.offseason,
    rows: [],
    cols: [],
    guesses: [],
    guessesLeft: GUESSES,
    finished: false,
    givenUp: false,
    results: null,
    archive: [],
  };
}

async function pageRows<T>(
  load: (from: number, to: number) => PromiseLike<{ data: T[] | null; error: { message: string } | null }>,
) {
  const rows: T[] = [];
  const page = 1000;
  for (let from = 0; ; from += page) {
    const data = unwrap(await load(from, from + page - 1));
    rows.push(...(data ?? []));
    if (!data || data.length < page) break;
  }
  return rows;
}

async function playersById(db: SupabaseClient, ids: string[]) {
  const found = new Map<string, PlayerRow>();
  for (let index = 0; index < ids.length; index += 200) {
    const slice = ids.slice(index, index + 200);
    if (!slice.length) continue;
    const data = unwrap(
      await db.from("grid_players").select("id, name, pos, fame").in("id", slice),
    ) as PlayerRow[];
    for (const row of data ?? []) found.set(row.id, row);
  }
  return found;
}

async function tagIds(db: SupabaseClient, tag: string) {
  const rows = await pageRows<{ player_id: string }>((from, to) =>
    db
      .from("grid_tags")
      .select("player_id")
      .eq("tag", tag)
      .order("player_id")
      .range(from, to),
  );
  return new Set(rows.map((row) => row.player_id));
}

async function correctPicks(db: SupabaseClient, date: string) {
  const rows = await pageRows<{ cell: number; player_id: string }>((from, to) =>
    db
      .from("grid_guesses")
      .select("cell, player_id")
      .eq("played_on", date)
      .eq("correct", true)
      .order("cell")
      .order("player_id")
      .range(from, to),
  );
  const picks = new Map<number, Map<string, number>>();
  for (const row of rows) {
    const cell = Number(row.cell);
    const players = picks.get(cell) ?? new Map<string, number>();
    players.set(row.player_id, (players.get(row.player_id) ?? 0) + 1);
    picks.set(cell, players);
  }
  return picks;
}

async function resultsFor(
  db: SupabaseClient,
  date: string,
  anonId: string,
  rowTags: string[],
  colTags: string[],
  guesses: GridGuess[],
): Promise<Board["results"]> {
  const picks = await correctPicks(db, date);
  const tagCache = new Map<string, Set<string>>();
  const tags = [...new Set([...rowTags, ...colTags])];
  await Promise.all(
    tags.map(async (tag) => {
      tagCache.set(tag, await tagIds(db, tag));
    }),
  );

  const pools = new Map<number, string[]>();
  for (let cell = 0; cell < GUESSES; cell += 1) {
    const correct = guesses.find((guess) => guess.cell === cell && guess.correct);
    if (!correct) continue;
    const row = tagCache.get(rowTags[Math.floor(cell / 3)]) ?? new Set<string>();
    const col = tagCache.get(colTags[cell % 3]) ?? new Set<string>();
    const pool = [...row].filter((id) => col.has(id));
    pools.set(cell, pool);
  }

  const fameIds = [...new Set([...pools.values()].flat())];
  const fameRows = await playersById(db, fameIds);
  const cells: (CellResult | null)[] = Array.from({ length: GUESSES }, () => null);
  const percents: (number | null)[] = Array.from({ length: GUESSES }, () => null);

  for (const [cell, pool] of pools) {
    const correct = guesses.find((guess) => guess.cell === cell && guess.correct);
    if (!correct) continue;
    const weights = pool.map((id) => fameWeight(Number(fameRows.get(id)?.fame)));
    const fameTotal = weights.reduce((sum, value) => sum + value, 0);
    const cellPicks = picks.get(cell) ?? new Map<string, number>();
    const fills = [...cellPicks.values()].reduce((sum, count) => sum + count, 0);
    const rarity = blendedRarity({
      picks: cellPicks.get(correct.playerId) ?? 1,
      fills: Math.max(fills, 1),
      fame: Number(fameRows.get(correct.playerId)?.fame),
      fameTotal,
    });
    cells[cell] = rarity;
    percents[cell] = rarity.percent;
  }

  const others = await db
    .from("grid_sessions")
    .select("anon_id", { count: "exact", head: true })
    .eq("played_on", date)
    .neq("anon_id", anonId);
  if (others.error) {
    console.error(others.error.message);
    throw new GridError("The grid is unavailable.", 500);
  }
  return {
    cells,
    score: rarityScore(percents),
    others: others.count ?? 0,
  };
}

function headersFor(tags: string[], throughSeason: number): GridHeader[] {
  return tags.map((tag) => describeTag(tag, throughSeason));
}

async function archiveFor(db: SupabaseClient, anonId: string, start: string, last: string) {
  const grids = unwrap(
    await db
      .from("grids")
      .select("played_on")
      .gte("played_on", start)
      .lte("played_on", last)
      .order("played_on"),
  ) as { played_on: string }[];
  const sessions = unwrap(
    await db
      .from("grid_sessions")
      .select("played_on, finished_at, given_up")
      .eq("anon_id", anonId)
      .gte("played_on", start)
      .lte("played_on", last),
  ) as { played_on: string; finished_at: string | null; given_up: boolean }[];
  const finished = new Set(
    sessions.filter((session) => session.finished_at || session.given_up).map((session) => session.played_on),
  );
  const counts = new Map<string, number>();
  const guessDays = await pageRows<{ played_on: string }>((from, to) =>
    db
      .from("grid_guesses")
      .select("played_on")
      .eq("anon_id", anonId)
      .gte("played_on", start)
      .lte("played_on", last)
      .order("played_on")
      .range(from, to),
  );
  for (const row of guessDays) {
    counts.set(row.played_on, (counts.get(row.played_on) ?? 0) + 1);
  }
  return (grids ?? []).map((grid) => ({
    date: grid.played_on,
    finished: finished.has(grid.played_on) || (counts.get(grid.played_on) ?? 0) >= GUESSES,
  }));
}

async function guessesFor(db: SupabaseClient, date: string, anonId: string) {
  const stored = unwrap(
    await db
      .from("grid_guesses")
      .select("cell, player_id, correct, created_at")
      .eq("played_on", date)
      .eq("anon_id", anonId)
      .order("created_at"),
  ) as StoredGuess[];
  const ids = [...new Set(stored.map((guess) => guess.player_id))];
  const players = await playersById(db, ids);
  const guesses: GridGuess[] = stored.map((guess) => {
    const player = players.get(guess.player_id);
    return {
      cell: Number(guess.cell),
      playerId: guess.player_id,
      name: player?.name ?? "Unknown",
      pos: player?.pos ?? "",
      correct: Boolean(guess.correct),
    };
  });
  return guesses;
}

export async function loadBoard(requested: string | null, anonId: string | null): Promise<Board> {
  const anon = requireAnon(anonId);
  const today = todayET();
  const season = windowFor(today);
  const date = requested && requested.length > 0 ? requested : defaultGridDate(today, season.start, season.end);
  if (!date) return emptyBoard(today);
  if (!isIsoDate(date) || !isPlayableDate(date, today, season.start, season.end)) {
    throw new GridError("That grid is not available.", 400);
  }

  const db = database();
  const grid = unwrap(
    await db.from("grids").select("played_on, rows, cols").eq("played_on", date).maybeSingle(),
  ) as { played_on: string; rows: string[]; cols: string[] } | null;
  if (!grid) throw new GridError("That grid is not ready yet.", 404);

  const last = today < season.end ? today : season.end;
  const [guesses, session, archive] = await Promise.all([
    guessesFor(db, date, anon),
    db
      .from("grid_sessions")
      .select("given_up, finished_at")
      .eq("played_on", date)
      .eq("anon_id", anon)
      .maybeSingle()
      .then((result) => unwrap(result) as { given_up: boolean; finished_at: string | null } | null),
    archiveFor(db, anon, season.start, last),
  ]);

  const givenUp = Boolean(session?.given_up);
  const finished = Boolean(session?.finished_at) || givenUp || guesses.length >= GUESSES;
  const rowTags = grid.rows ?? [];
  const colTags = grid.cols ?? [];
  return {
    playable: true,
    date,
    today,
    start: season.start,
    end: season.end,
    nextDrop: season.nextDrop,
    throughSeason: season.throughSeason,
    offseason: season.offseason,
    rows: headersFor(rowTags, season.throughSeason),
    cols: headersFor(colTags, season.throughSeason),
    guesses,
    guessesLeft: Math.max(GUESSES - guesses.length, 0),
    finished,
    givenUp,
    results: finished
      ? await resultsFor(db, date, anon, rowTags, colTags, guesses)
      : null,
    archive,
  };
}

async function puzzleTags(db: SupabaseClient, date: string) {
  const grid = unwrap(
    await db.from("grids").select("rows, cols").eq("played_on", date).maybeSingle(),
  ) as { rows: string[]; cols: string[] } | null;
  if (!grid) throw new GridError("That grid is not ready yet.", 404);
  return grid;
}

export async function submitGuess(input: {
  date: string | null;
  anonId: string | null;
  cell: number;
  playerId: string;
}) {
  const anon = requireAnon(input.anonId);
  if (!input.date || !isIsoDate(input.date)) {
    throw new GridError("That grid is not available.", 400);
  }
  if (!Number.isInteger(input.cell) || input.cell < 0 || input.cell > 8) {
    throw new GridError("That square is not on the grid.", 400);
  }
  if (!/^[A-Za-z0-9.-]{1,40}$/.test(input.playerId)) {
    throw new GridError("That player is not in the grid.", 400);
  }

  const today = todayET();
  const season = windowFor(today);
  if (!isPlayableDate(input.date, today, season.start, season.end)) {
    throw new GridError("That grid is not available.", 400);
  }

  const db = database();
  const grid = await puzzleTags(db, input.date);
  const guesses = await guessesFor(db, input.date, anon);
  const session = unwrap(
    await db
      .from("grid_sessions")
      .select("given_up, finished_at")
      .eq("played_on", input.date)
      .eq("anon_id", anon)
      .maybeSingle(),
  ) as { given_up: boolean; finished_at: string | null } | null;
  const finished = Boolean(session?.finished_at) || Boolean(session?.given_up) || guesses.length >= GUESSES;
  if (finished) throw new GridError("This grid is already finished.", 409);
  if (guesses.some((guess) => guess.cell === input.cell && guess.correct)) {
    throw new GridError("That square is filled.", 409);
  }

  const prior = guesses.find((guess) => guess.cell === input.cell && guess.playerId === input.playerId);
  if (prior) {
    return {
      board: await loadBoard(input.date, anon),
      correct: prior.correct,
      duplicate: true,
    };
  }

  const player = unwrap(
    await db.from("grid_players").select("id").eq("id", input.playerId).maybeSingle(),
  ) as { id: string } | null;
  if (!player) throw new GridError("That player is not in the grid.", 400);

  const rowTag = grid.rows[Math.floor(input.cell / 3)];
  const colTag = grid.cols[input.cell % 3];
  const tagged = unwrap(
    await db.from("grid_tags").select("tag").eq("player_id", input.playerId).in("tag", [rowTag, colTag]),
  ) as { tag: string }[];
  const found = new Set((tagged ?? []).map((row) => row.tag));
  const correct = found.has(rowTag) && found.has(colTag);

  unwrap(
    await db.from("grid_sessions").upsert(
      { played_on: input.date, anon_id: anon, given_up: false },
      { onConflict: "played_on,anon_id", ignoreDuplicates: true },
    ),
  );
  unwrap(
    await db.from("grid_guesses").insert({
      played_on: input.date,
      anon_id: anon,
      cell: input.cell,
      player_id: input.playerId,
      correct,
    }),
  );
  if (guesses.length + 1 >= GUESSES) {
    unwrap(
      await db
        .from("grid_sessions")
        .update({ finished_at: new Date().toISOString() })
        .eq("played_on", input.date)
        .eq("anon_id", anon)
        .is("finished_at", null),
    );
  }

  return {
    board: await loadBoard(input.date, anon),
    correct,
    duplicate: false,
  };
}

export async function giveUp(date: string | null, anonId: string | null) {
  const anon = requireAnon(anonId);
  if (!date || !isIsoDate(date)) throw new GridError("That grid is not available.", 400);
  const today = todayET();
  const season = windowFor(today);
  if (!isPlayableDate(date, today, season.start, season.end)) {
    throw new GridError("That grid is not available.", 400);
  }
  const db = database();
  await puzzleTags(db, date);
  const board = await loadBoard(date, anon);
  if (board.finished) return { board };
  unwrap(
    await db.from("grid_sessions").upsert(
      {
        played_on: date,
        anon_id: anon,
        given_up: true,
        finished_at: new Date().toISOString(),
      },
      { onConflict: "played_on,anon_id" },
    ),
  );
  return { board: await loadBoard(date, anon) };
}

export async function searchPlayers(query: string | null): Promise<SearchHit[]> {
  const needle = searchNeedle(query ?? "");
  if (needle.length < 2) return [];
  const db = database();
  const rows = unwrap(
    await db
      .from("grid_players")
      .select("id, name, pos, year_min, year_max")
      .ilike("search_name", `%${needle}%`)
      .order("fame", { ascending: false })
      .order("name")
      .limit(8),
  ) as PlayerRow[];
  return (rows ?? []).map((row) => ({
    id: row.id,
    name: row.name,
    pos: row.pos,
    years: careerYears(Number(row.year_min), Number(row.year_max)),
  }));
}

export function gridJson(body: unknown, status = 200) {
  return NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

export function gridErrorResponse(error: unknown) {
  if (error instanceof GridError) return gridJson({ error: error.message }, error.status);
  console.error(error);
  return gridJson({ error: "The grid is unavailable." }, 500);
}
